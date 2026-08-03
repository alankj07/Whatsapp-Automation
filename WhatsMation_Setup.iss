; Inno Setup Script for WhatsMation Desktop Application
; Requires Inno Setup 6.0 or higher (https://jrsoftware.org/isdl.php)

#define MyAppName "WhatsMation"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "ALAN KJ"
#define MyAppURL "https://github.com/alankj07/whatsapp-message-sender"
#define MyAppExeName "WhatsMation.exe"

[Setup]
; Unique App ID for Windows Installation tracking
AppId={{D3F98123-5A4C-4F91-986D-45A0B1A2C3D4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Default Install directory: User Local AppData Programs (no admin rights needed) or Program Files
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE
OutputBaseFilename=WhatsMation-v1.0.0-Setup
OutputDir=dist_release

; LZMA2 Maximum compression for fast download
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

; Branding & Icons
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Distribute all files from dist\WhatsMation directory
Source: "dist\WhatsMation\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\WhatsMation\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
