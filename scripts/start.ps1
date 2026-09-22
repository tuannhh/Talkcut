# TalkCut Studio - trinh khoi dong cho Windows.
# Tuong duong scripts/start.sh nhung chay bang PowerShell: tu bat Docker Desktop,
# tao .env neu chua co, nap image dung san (neu co file tar), tu phat hien GPU
# NVIDIA, roi khoi dong bang docker compose. Chay qua start.bat (o thu muc goc).
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# Luon chay tu thu muc goc cua du an (script nay nam trong scripts\).
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Info($m) { Write-Host $m -ForegroundColor Cyan }
function Ok($m)   { Write-Host $m -ForegroundColor Green }
function Warn($m) { Write-Host $m -ForegroundColor Yellow }
function Fail($m) { Write-Host $m -ForegroundColor Red }

function Test-Docker {
  docker version --format '{{.Server.Version}}' 2>$null | Out-Null
  return ($LASTEXITCODE -eq 0)
}
function Have-Image($name) {
  docker image inspect $name 2>$null | Out-Null
  return ($LASTEXITCODE -eq 0)
}

# --- 1. Docker Desktop: da cai + dang chay --------------------------------
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
  Fail 'Chua cai Docker Desktop.'
  Fail 'Tai va cai tai: https://www.docker.com/products/docker-desktop/'
  Read-Host 'Nhan Enter de thoat'; exit 1
}
if (-not (Test-Docker)) {
  Info 'Docker Desktop chua chay - dang khoi dong (co the mat 1-2 phut)...'
  $exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
  if (Test-Path $exe) { Start-Process $exe } else { Warn "Khong tim thay $exe - hay mo Docker Desktop thu cong." }
  $deadline = (Get-Date).AddSeconds(180)
  while ((Get-Date) -lt $deadline -and -not (Test-Docker)) { Start-Sleep -Seconds 5 }
  if (-not (Test-Docker)) {
    Fail 'Docker Desktop van chua san sang sau 3 phut. Hay mo Docker Desktop, doi bao "Engine running" roi chay lai.'
    Read-Host 'Nhan Enter de thoat'; exit 1
  }
}
Ok ('Docker OK (engine ' + (docker version --format '{{.Server.Version}}') + ').')

# --- 2. File cau hinh .env ------------------------------------------------
if (-not (Test-Path .env)) {
  Copy-Item .env.example .env
  Warn 'Da tao file .env tu mau. Dan GEMINI_API_KEY cua ban vao (va sua SOURCE_DIR neu can).'
  Start-Process notepad (Join-Path $root '.env')
  Read-Host 'Sau khi da luu .env, nhan Enter de tiep tuc'
}
$hasKey = Select-String -Path .env -Pattern '^\s*GEMINI_API_KEY\s*=\s*\S' -ErrorAction SilentlyContinue
if (-not $hasKey) { Warn 'Canh bao: .env chua co GEMINI_API_KEY - cac tinh nang AI (STT/TTS/noi dung) se khong hoat dong cho toi khi ban dien khoa.' }

# --- 3. Nap image dung san neu co file tar va may chua co image -----------
$studioImg = 'talkcut-studio-studio:latest'
$faceImg   = 'talkcut-face-engine:latest'
if (-not (Have-Image $studioImg) -or -not (Have-Image $faceImg)) {
  $tar = Get-ChildItem -Path $root -Filter 'talkcut-images*.tar*' -File -ErrorAction SilentlyContinue |
         Sort-Object Length -Descending | Select-Object -First 1
  if ($tar) {
    Info ('Dang nap image tu ' + $tar.Name + ' (~2GB, co the mat vai phut)...')
    docker load -i $tar.FullName
    if ($LASTEXITCODE -ne 0) { Fail 'Nap image that bai.'; Read-Host 'Nhan Enter de thoat'; exit 1 }
  }
}

# --- 4. Tu phat hien GPU NVIDIA -------------------------------------------
# Ca hai image luon mang san ho tro GPU nhung chi dung GPU khi container thuc
# su duoc cap GPU (qua compose.gpu.yaml). Chi bat overlay khi vua thay card
# NVIDIA (nvidia-smi) vua thay Docker da bat runtime nvidia.
$useGpu = $false
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
  nvidia-smi *> $null
  if ($LASTEXITCODE -eq 0) {
    $info = (docker info 2>$null | Out-String)
    if ($info -match 'nvidia') { $useGpu = $true }
  }
}
$files = @('-f', 'compose.yaml')
if ($useGpu) {
  $files += @('-f', 'compose.gpu.yaml')
  Ok 'Da phat hien GPU NVIDIA - bat tang toc GPU (render + nhan dien khuon mat).'
} else {
  Warn 'Khong thay GPU NVIDIA (hoac Docker chua bat GPU) - chay che do CPU. Van dung binh thuong, chi cham hon.'
}

# --- 5. Dung image (neu chua co) hoac chay tu image co san ----------------
$haveBoth = (Have-Image $studioImg) -and (Have-Image $faceImg)
if ($haveBoth) {
  $mode = '--no-build'
  Info 'Dang khoi dong tu image co san...'
} else {
  if (-not (Test-Path (Join-Path $root 'Dockerfile'))) {
    Fail 'Chua co image san va cung khong co ma nguon de build.'
    Fail 'Hay dat file talkcut-images*.tar.gz vao thu muc nay, HOAC dung ban co day du ma nguon.'
    Read-Host 'Nhan Enter de thoat'; exit 1
  }
  $mode = '--build'
  Info 'Chua co image san - se DUNG image tu ma nguon. Lan dau co the mat ~15-20 phut...'
}

docker compose @files up -d $mode
if ($LASTEXITCODE -ne 0 -and $useGpu) {
  Warn 'Khoi dong voi GPU that bai - thu lai o che do CPU...'
  docker compose -f compose.yaml up -d $mode
}
if ($LASTEXITCODE -ne 0) {
  Fail 'Khoi dong that bai. Xem log: docker compose logs -f'
  Read-Host 'Nhan Enter de thoat'; exit 1
}

# --- 6. Doi dich vu san sang roi mo trinh duyet ---------------------------
$port = 8092
$m = Select-String -Path .env -Pattern '^\s*PORT\s*=\s*(\d+)' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($m) { $port = $m.Matches[0].Groups[1].Value }
$url = "http://localhost:$port"

Info "Dang cho dich vu san sang tai $url ..."
$deadline = (Get-Date).AddSeconds(150)
$up = $false
while ((Get-Date) -lt $deadline) {
  try {
    $r = Invoke-WebRequest -UseBasicParsing "$url/api/health" -TimeoutSec 3
    if ($r.StatusCode -eq 200) { $up = $true; break }
  } catch {}
  Start-Sleep -Seconds 3
}
if ($up) {
  Ok "TalkCut Studio da san sang: $url"
  Start-Process $url
} else {
  Warn "Dich vu chua phan hoi (co the con dang khoi dong). Mo $url sau it phut."
  Warn 'Xem log neu can: docker compose logs -f'
}
