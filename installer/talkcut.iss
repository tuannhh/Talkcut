; Inno Setup script cho TalkCut Studio (Windows).
; Bien dich bang: build-installer.bat  (o thu muc goc du an)
; Ket qua: dist\TalkCutStudio-Setup.exe  (bo cai offline mot file, ~2GB)
;
; Bo cai chi dat file ung dung + image dung san + tao loi tat. KHONG nhung
; Docker Desktop (giay phep cua Docker khong cho phep phat hanh lai, va lan
; dau cai Docker can quyen admin + WSL2 + khoi dong lai may). Neu may chua co
; Docker, bo cai se moi mo trang tai Docker chinh chu.

#define MyAppName "TalkCut Studio"
#define MyAppVersion "0.12.0"
#define MyAppPublisher "TalkCut"
#define MyAppExe "start.bat"

[Setup]
AppId={{7E1C3B2A-4D5F-4A9C-9B6E-TALKCUT00001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
; Cai vao thu muc nguoi dung ghi duoc (start.ps1 tao .env ngay tai day, khong
; can quyen admin luc chay).
DefaultDirName={localappdata}\Programs\TalkCut Studio
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=TalkCutStudio-Setup
SetupIconFile=talkcut.ico
UninstallDisplayIcon={app}\talkcut.ico
WizardStyle=modern
; Image .gz da nen roi -> khong nen lai (nhanh hon nhieu, kich thuoc ~nhu cu).
Compression=lzma2/fast
SolidCompression=no
DisableWelcomePage=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tao loi tat tren man hinh (Desktop)"; GroupDescription: "Loi tat:"

[Files]
Source: "..\dist\talkcut-install\start.bat";            DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\talkcut-install\stop.bat";             DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\talkcut-install\compose.yaml";         DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\talkcut-install\compose.gpu.yaml";     DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\talkcut-install\.env.example";         DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\talkcut-install\INSTALL.md";           DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\talkcut-install\scripts\start.ps1";    DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "talkcut.ico";                                  DestDir: "{app}"; Flags: ignoreversion
; Image dung san (~2GB) - khong nen lai vi da la .gz
Source: "..\dist\talkcut-install\talkcut-images.tar.gz";        DestDir: "{app}"; Flags: ignoreversion nocompression
Source: "..\dist\talkcut-install\talkcut-images.tar.gz.sha256"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\TalkCut Studio";        Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\talkcut.ico"; Comment: "Khoi chay TalkCut Studio"
Name: "{group}\Tat TalkCut Studio";    Filename: "{app}\stop.bat";    WorkingDir: "{app}"; IconFilename: "{app}\talkcut.ico"; Comment: "Tat dich vu (giu du lieu)"
Name: "{group}\Huong dan cai dat";     Filename: "{app}\INSTALL.md"
Name: "{autodesktop}\TalkCut Studio";  Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\talkcut.ico"; Comment: "Khoi chay TalkCut Studio"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; WorkingDir: "{app}"; Description: "Khoi chay TalkCut Studio ngay bay gio"; Flags: nowait postinstall skipifsilent

[Code]
function DockerInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{commonpf}\Docker\Docker\Docker Desktop.exe')) or
            FileExists(ExpandConstant('{commonpf}\Docker\Docker\resources\bin\docker.exe'));
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrCode: Integer;
begin
  if (CurStep = ssPostInstall) and (not DockerInstalled()) then
  begin
    if MsgBox('TalkCut Studio can Docker Desktop de chay, nhung may nay chua cai.' + #13#10 + #13#10 +
              'Nhan YES de mo trang tai Docker Desktop (chinh chu). Sau khi cai Docker va khoi dong lai may, hay mo TalkCut Studio bang loi tat vua tao.',
              mbConfirmation, MB_YESNO) = IDYES then
      ShellExec('open', 'https://www.docker.com/products/docker-desktop/', '', '', SW_SHOW, ewNoWait, ErrCode);
  end;
end;
