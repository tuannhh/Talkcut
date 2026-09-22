# TalkCut Studio - cong cu dong goi bo cai Windows (danh cho nguoi build, KHONG
# gui cho nguoi dung cuoi). Chay: build-bundle.bat  (hoac -Build de build image
# truoc khi dong goi). Ket qua: dist\talkcut-install\ gom launcher + compose +
# image dung san (.tar.gz) + checksum SHA-256. Copy ca thu muc do sang may nha.
param([switch]$Build)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Info($m) { Write-Host $m -ForegroundColor Cyan }
function Ok($m)   { Write-Host $m -ForegroundColor Green }
function Warn($m) { Write-Host $m -ForegroundColor Yellow }
function Fail($m) { Write-Host $m -ForegroundColor Red }

$studioImg = 'talkcut-studio-studio:latest'
$faceImg   = 'talkcut-face-engine:latest'
$outDir    = Join-Path $root 'dist\talkcut-install'
$rawTar    = Join-Path $outDir 'talkcut-images.tar'
$gzTar     = Join-Path $outDir 'talkcut-images.tar.gz'
$sumFile   = "$gzTar.sha256"

# --- 0. Docker san sang ---------------------------------------------------
docker version --format '{{.Server.Version}}' 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'Docker chua chay. Mo Docker Desktop roi chay lai.'; exit 1 }

# --- 1. (Tuy chon) build image tu ma nguon --------------------------------
if ($Build) {
  Info 'Dang build image tu ma nguon (docker compose build)...'
  docker compose -f compose.yaml build
  if ($LASTEXITCODE -ne 0) { Fail 'Build that bai.'; exit 1 }
}

foreach ($img in @($studioImg, $faceImg)) {
  docker image inspect $img 2>$null | Out-Null
  if ($LASTEXITCODE -ne 0) { Fail "Thieu image $img. Chay lai voi -Build, hoac build truoc."; exit 1 }
}

# --- 2. Chuan bi thu muc + chep file nho ----------------------------------
New-Item -ItemType Directory -Force -Path (Join-Path $outDir 'scripts') | Out-Null
Copy-Item -Force start.bat, stop.bat, compose.yaml, compose.gpu.yaml, .env.example, INSTALL.md $outDir
Copy-Item -Force scripts\start.ps1 (Join-Path $outDir 'scripts')
Ok 'Da chep launcher + compose + INSTALL.md vao bo cai.'

# --- 3. Xuat image ra tar (docker tu ghi file, khong qua pipe PowerShell) --
Remove-Item -Force -ErrorAction SilentlyContinue $rawTar, $gzTar, $sumFile
Info 'Dang xuat image (docker save)... co the mat vai phut.'
docker save -o $rawTar $studioImg $faceImg
if ($LASTEXITCODE -ne 0) { Fail 'docker save that bai.'; exit 1 }

# --- 4. Nen .tar -> .tar.gz -----------------------------------------------
# Uu tien gzip that (Git Bash) cho ti le nen tot; neu khong co, dung .NET.
function Find-Gzip {
  $c = Get-Command gzip -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($p in @(
      (Join-Path $env:ProgramFiles 'Git\usr\bin\gzip.exe'),
      (Join-Path ${env:ProgramFiles(x86)} 'Git\usr\bin\gzip.exe'),
      (Join-Path $env:LOCALAPPDATA 'Programs\Git\usr\bin\gzip.exe'))) {
    if ($p -and (Test-Path $p)) { return $p }
  }
  return $null
}
$gzip = Find-Gzip
if ($gzip) {
  Info "Dang nen bang gzip ($gzip)..."
  & $gzip -f -6 $rawTar    # tao talkcut-images.tar.gz, xoa .tar goc
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path $gzTar)) { Fail 'Nen bang gzip that bai.'; exit 1 }
} else {
  Warn 'Khong tim thay gzip (cai Git for Windows de nen tot hon) - dung .NET GZipStream.'
  $in  = [System.IO.File]::OpenRead($rawTar)
  $fs  = [System.IO.File]::Create($gzTar)
  $gz  = New-Object System.IO.Compression.GZipStream($fs, [System.IO.Compression.CompressionLevel]::Optimal)
  try { $in.CopyTo($gz, 4MB) } finally { $gz.Dispose(); $fs.Dispose(); $in.Dispose() }
  Remove-Item -Force $rawTar
}

# --- 5. Checksum SHA-256 (dinh dang sha256sum: "<hash> *<ten>") -----------
Info 'Dang tinh checksum SHA-256...'
$hash = (Get-FileHash -Algorithm SHA256 $gzTar).Hash.ToLower()
"$hash *talkcut-images.tar.gz" | Set-Content -Encoding ASCII $sumFile

$sizeGB = [math]::Round((Get-Item $gzTar).Length / 1GB, 2)
Ok ''
Ok "Xong. Bo cai o: $outDir"
Ok ("  talkcut-images.tar.gz  = $sizeGB GB")
Ok ("  SHA-256                = $hash")
Ok 'Copy CA thu muc talkcut-install (ke ca .tar.gz va .sha256) sang may nha, roi nhap doi start.bat.'
