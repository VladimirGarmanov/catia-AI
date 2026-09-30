#define AppName "CATIA AI"
#define AppVersion "0.2.0"
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
Name: "{autoprograms}\CATIA AI"; Filename: "{app}\project\START_CATIA_AI.cmd"; WorkingDir: "{app}\project"
Name: "{autodesktop}\CATIA AI"; Filename: "{app}\project\START_CATIA_AI.cmd"; WorkingDir: "{app}\project"; Tasks: desktopicon

[Run]
Filename: "{app}\project\START_CATIA_AI.cmd"; WorkingDir: "{app}\project"; Description: "Start CATIA AI"; Flags: postinstall nowait skipifsilent
