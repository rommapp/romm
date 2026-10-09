; Inno Setup script for the RomM Windows installer (WSL2 based).
; Build: iscc /DAppVersion=5.0.0 romm.iss, with dist\romm-wsl.tar.gz from build-rootfs.sh.

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

[Setup]
AppId={{6C0E8B6E-2F4B-4E7A-9C1E-6F0D2B9A4D11}
AppName=RomM
AppVersion={#AppVersion}
AppPublisher=RomM
AppPublisherURL=https://romm.app
DefaultDirName={localappdata}\Programs\RomM
DefaultGroupName=RomM
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.19041
OutputDir=dist
OutputBaseFilename=RomM-Setup-{#AppVersion}
Compression=lzma2/fast
SolidCompression=no
DisableProgramGroupPage=yes
UninstallDisplayName=RomM

[Files]
Source: "RomM.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\romm-wsl.tar.gz"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "autostart"; Description: "Start RomM when I sign in"

[Icons]
Name: "{group}\Open RomM"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\RomM.ps1"" open"
Name: "{group}\Stop RomM"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\RomM.ps1"" stop"
Name: "{group}\RomM logs"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\RomM.ps1"" logs"
Name: "{group}\RomM settings"; Filename: "notepad.exe"; Parameters: """{localappdata}\RomM\romm.env"""
Name: "{userstartup}\RomM"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\RomM.ps1"" start"; Tasks: autostart

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\RomM.ps1"" {code:InstallVerb} -Rootfs ""{app}\romm-wsl.tar.gz"" -Library ""{code:LibraryPath}"" -Port {code:PortValue}"; StatusMsg: "Setting up RomM in WSL..."; Flags: runhidden waituntilterminated
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File ""{app}\RomM.ps1"" open"; Description: "Open RomM"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\RomM.ps1"" uninstall {code:UninstallFlags}"; Flags: runhidden waituntilterminated; RunOnceId: "UnregisterRomM"

[Code]
var
  LibraryPage: TInputDirWizardPage;
  PortPage: TInputQueryWizardPage;
  KeepDataOnUninstall: Boolean;

function IsUpgrade(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\RomM\romm.env'));
end;

function InstallVerb(Param: String): String;
begin
  if IsUpgrade() then Result := 'upgrade' else Result := 'install';
end;

function LibraryPath(Param: String): String;
begin
  Result := LibraryPage.Values[0];
end;

function PortValue(Param: String): String;
begin
  Result := PortPage.Values[0];
end;

function WslReady(): Boolean;
var
  Code: Integer;
begin
  Result := Exec(ExpandConstant('{sys}\wsl.exe'), '--status', '', SW_HIDE, ewWaitUntilTerminated, Code) and (Code = 0);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  if not WslReady() then
  begin
    MsgBox('RomM runs inside WSL2, which is not set up on this PC.' + #13#10#13#10 +
      'Open PowerShell as administrator, run:' + #13#10 +
      '    wsl --install --no-distribution' + #13#10 +
      'then restart Windows and run this installer again.', mbInformation, MB_OK);
    Result := False;
  end;
end;

procedure InitializeWizard();
begin
  LibraryPage := CreateInputDirPage(wpSelectDir, 'Game library',
    'Where are your ROMs?',
    'Pick the folder that holds your platform folders (for example D:\Games\ROMs\snes).',
    False, '');
  LibraryPage.Add('');
  PortPage := CreateInputQueryPage(LibraryPage.ID, 'Port',
    'Which port should RomM listen on?', 'RomM will be at http://localhost:<port>.');
  PortPage.Add('Port:', False);
  PortPage.Values[0] := '8080';
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := IsUpgrade() and ((PageID = LibraryPage.ID) or (PageID = PortPage.ID));
end;

function InitializeUninstall(): Boolean;
begin
  KeepDataOnUninstall := MsgBox('Keep your RomM data (database, saves, states, covers) so a later install picks it back up?' + #13#10#13#10 +
    'Choose No to delete it. Your ROM library folder is never touched.', mbConfirmation, MB_YESNO) = IDYES;
  Result := True;
end;

function UninstallFlags(Param: String): String;
begin
  if KeepDataOnUninstall then Result := '-KeepData' else Result := '';
end;
