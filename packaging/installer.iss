; Inno Setup script for Fulfillment Studio.
; Produces a single "Fulfillment Studio Setup <ver>.exe" from the PyInstaller
; one-folder build at ../dist/Fulfillment Studio/.
;
; Build steps (from repo root):
;   1) uv run pyinstaller packaging/lbb.spec --clean --noconfirm
;   2) ISCC packaging/installer.iss          (Inno Setup 6 compiler)
; Output lands in packaging/installer-output/.
;
; Installs per-user (no admin needed) so non-technical operators can run it
; without elevation or a SmartScreen "make changes to your device?" prompt.

#define AppName "Fulfillment Studio"
#define AppVersion "0.1.0"
#define Publisher "Flanacom GmbH"
#define ExeName "Fulfillment Studio.exe"

[Setup]
; A stable, unique identity for upgrades/uninstall. Do not change between versions.
AppId={{8F3A1C7E-5B2D-4A9F-9E1C-7D6B4F2A0C13}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#Publisher}
AppPublisherURL=https://www.flanacom.de
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#ExeName}
SetupIconFile=..\src\lbb\web\assets\flanacom.ico
OutputDir=installer-output
OutputBaseFilename=Fulfillment Studio Setup {#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Per-user install — no administrator rights required.
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"

[Files]
; The entire PyInstaller one-folder bundle (exe + _internal/ web assets, runtime).
Source: "..\dist\Fulfillment Studio\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#ExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent
