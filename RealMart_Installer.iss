; Real Mart Professional Installer Script for Inno Setup
; Download Inno Setup from: https://jrsoftware.org/isinfo.php

[Setup]
AppName=Real Mart POS
AppVersion=1.0.0
AppPublisher=Adarsh & Rushikesh
DefaultDirName={autopf}\RealMart
DefaultGroupName=RealMart
AllowNoIcons=yes
; Output file name: RealMart_Setup.exe
OutputBaseFilename=RealMart_Setup
Compression=lzma
SolidCompression=yes
; Requires Admin to install to Program Files
PrivilegesRequired=admin
; Setup Icon (if you have one)
; SetupIconFile=images\app_icon.ico
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; IMPORTANT: Run 'python build_exe.py' first to generate the 'dist\RealMart' folder
Source: "dist\RealMart\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Also include the database folder if not already inside dist
; Source: "Database\*"; DestDir: "{app}\Database"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Real Mart"; Filename: "{app}\RealMart.exe"
Name: "{autodesktop}\Real Mart"; Filename: "{app}\RealMart.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\RealMart.exe"; Description: "{cm:LaunchProgram,Real Mart}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\Database"
Type: filesandordirs; Name: "{app}\backups"
