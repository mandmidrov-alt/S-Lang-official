#define MyAppName "S-Lang"
#define MyAppVersion "1.0"
#define MyAppPublisher "S-Lang Project"
#define MyAppExeName "slang1.0.exe"

[Setup]
AppId={{A9B65E3A-6B80-4D31-9B4C-SLANG10}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\S-Lang\1.0
DefaultGroupName=S-Lang
OutputBaseFilename=S-Lang-1.0-Windows-x64-Setup
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "..\..\dist\windows-x86_64\slang1.0.exe"; DestDir: "{app}"; Flags: ignoreversion

[Tasks]
Name: "addtopath"; Description: "Add S-Lang to the user PATH"; Flags: unchecked

[Code]
procedure CurStepChanged(CurStep: TSetupStep);
var
  Path: string;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('addtopath') then begin
    if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Path) then Path := '';
    if Pos(ExpandConstant('{app}'), Path) = 0 then begin
      if (Path <> '') and (Path[Length(Path)] <> ';') then Path := Path + ';';
      RegWriteStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', Path + ExpandConstant('{app}'));
    end;
  end;
end;
