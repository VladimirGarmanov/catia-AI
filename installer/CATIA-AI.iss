#define AppName "CATIA AI"
#define AppVersion "0.2.1"
#ifndef BundleDir
  #error BundleDir must point to the prepared CATIA-AI payload
#endif
#ifndef OutputDir
  #define OutputDir "..\dist\windows-installer"
#endif

[Setup]
AppId={{F46A7828-0DC0-4AF0-8A75-6239339937AC}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=CATIA AI contributors
DefaultDirName={localappdata}\Programs\CATIA-AI
DefaultGroupName=CATIA AI
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
OutputDir={#OutputDir}
OutputBaseFilename=CATIA-AI-Setup
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
UninstallDisplayName=CATIA AI
DisableProgramGroupPage=yes
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\CATIA AI"; Filename: "{app}\project\START_AI.cmd"; WorkingDir: "{app}\project"
Name: "{autodesktop}\CATIA AI"; Filename: "{app}\project\START_AI.cmd"; WorkingDir: "{app}\project"; Tasks: desktopicon

[InstallDelete]
Type: files; Name: "{autoprograms}\CATIA AI - Codex.lnk"
Type: files; Name: "{autoprograms}\CATIA AI - Claude Code.lnk"
Type: files; Name: "{autoprograms}\CATIA AI - Install Claude Code.lnk"
Type: files; Name: "{app}\project\START_CATIA_AI.cmd"
Type: files; Name: "{app}\project\START_CLAUDE_AI.cmd"
Type: files; Name: "{app}\project\START_WITH_DRAWING.cmd"
Type: files; Name: "{app}\project\START_CLAUDE_WITH_DRAWING.cmd"
Type: files; Name: "{app}\project\START_SMART_DRAWING.cmd"
Type: files; Name: "{app}\project\START_TEAM_AI.cmd"
Type: files; Name: "{app}\project\START_CLAUDE_TEAM.cmd"
Type: files; Name: "{app}\project\INSTALL_CLAUDE.cmd"
Type: files; Name: "{app}\project\DIAGNOSE_CLAUDE.cmd"
Type: files; Name: "{app}\project\setup_codex.ps1"
Type: files; Name: "{app}\project\WINDOWS_CODEX.md"
Type: files; Name: "{app}\project\WINDOWS_CLAUDE.md"
Type: files; Name: "{app}\project\scripts\configure_codex_agents.py"

[Run]
Filename: "{app}\project\INSTALL.cmd"; Parameters: "--client claude"; WorkingDir: "{app}\project"; Description: "Also download and install Claude Code (internet required)"; Flags: postinstall skipifsilent unchecked
Filename: "{app}\project\START_AI.cmd"; WorkingDir: "{app}\project"; Description: "Start CATIA AI"; Flags: postinstall nowait skipifsilent
