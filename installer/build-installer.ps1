# Bien dich bo cai Windows mot file (dist\TalkCutStudio-Setup.exe) tu bo cai
# da dong goi trong dist\talkcut-install\. Neu chua co bo cai do (hoac chua co
# image tar), tu chay build-bundle.ps1 truoc. Chay qua build-installer.bat.
param([switch]$Build)  # -Build: build lai image tu ma nguon truoc khi dong goi

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Info($m) { Write-Host $m -ForegroundColor Cyan }
function Ok($m)   { Write-Host $m -ForegroundColor Green }
function Fail($m) { Write-Host $m -ForegroundColor Red }

$tar = Join-Path $root 'dist\talkcut-install\talkcut-images.tar.gz'

# 1. Dam bao bo cai (image tar) da san sang.
if ($Build -or -not (Test-Path $tar)) {
  Info 'Chua co image tar (hoac yeu cau -Build) - dang chay build-bundle.ps1...'
  $bb = Join-Path $PSScriptRoot '..\scripts\build-bundle.ps1'
  if ($Build) { & $bb -Build } else { & $bb }
  if ($LASTEXITCODE -ne 0) { Fail 'build-bundle.ps1 that bai.'; exit 1 }
}
if (-not (Test-Path $tar)) { Fail "Van khong thay $tar."; exit 1 }

# 2. Tim ISCC.exe (Inno Setup 6).
function Find-ISCC {
  $c = Get-Command ISCC -ErrorAction SilentlyContinue
  if ($c) { return $c.Source }
  foreach ($p in @(
      (Join-Path $env:LOCALAPPDATA 'Programs\Inno Setup 6\ISCC.exe'),
      (Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'),
      (Join-Path $env:ProgramFiles 'Inno Setup 6\ISCC.exe'))) {
    if ($p -and (Test-Path $p)) { return $p }
  }
  return $null
}
$iscc = Find-ISCC
if (-not $iscc) {
  Fail 'Khong tim thay Inno Setup (ISCC.exe). Cai bang: winget install JRSoftware.InnoSetup'
  exit 1
}
Ok "Dung ISCC: $iscc"

# 3. Bien dich.
Info 'Dang bien dich bo cai (co the mat vai phut vi kem image ~2GB)...'
& $iscc (Join-Path $PSScriptRoot 'talkcut.iss')
if ($LASTEXITCODE -ne 0) { Fail 'Bien dich that bai.'; exit 1 }

$exe = Join-Path $root 'dist\TalkCutStudio-Setup.exe'
if (Test-Path $exe) {
  $gb = [math]::Round((Get-Item $exe).Length / 1GB, 2)
  Ok ''
  Ok "Xong! Bo cai: $exe  ($gb GB)"
  Ok 'Gui/copy file .exe nay sang may nha, nhap doi de cai. Xong se co loi tat "TalkCut Studio" tren Desktop + Start Menu.'
} else {
  Fail 'Khong thay file .exe dau ra.'; exit 1
}
