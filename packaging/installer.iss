; Instalador de Presupuestos (Inno Setup 6). Lo compila packaging\build.bat.
#ifndef AppVersion
  #define AppVersion "0.8.0"
#endif
#define AppName "Presupuestos"
#define AppExe "PresupuestosApp.exe"

[Setup]
AppId={{6F2A7C1E-8B3D-4E5F-9A21-3C4D5E6F7A80}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Eduardo José Moreno
AppCopyright=Copyright (C) 2026 Eduardo José Moreno - GPL-3.0-or-later
AppPublisherURL=https://github.com/edumor/presupuestos-proyectos
AppSupportURL=https://github.com/edumor/presupuestos-proyectos/issues
AppUpdatesURL=https://github.com/edumor/presupuestos-proyectos/releases
DefaultDirName={localappdata}\Programs\Presupuestos
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=Presupuestos-Setup-{#AppVersion}
SetupIconFile=recursos\icono.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "escritorio"; Description: "Crear un acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "..\dist\PresupuestosApp\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; DestName: "LICENSE.txt"; Flags: ignoreversion
Source: "..\NOTICE.md"; DestDir: "{app}"; DestName: "NOTICE.txt"; Flags: ignoreversion

[Icons]
Name: "{group}\Presupuestos"; Filename: "{app}\{#AppExe}"
Name: "{group}\Licencia y autoría"; Filename: "{app}\NOTICE.txt"
Name: "{group}\Manual de uso"; Filename: "{app}\_internal\docs\Manual_Presupuestos.pdf"; Check: FileExists(ExpandConstant('{app}\_internal\docs\Manual_Presupuestos.pdf'))
Name: "{group}\Carpeta de datos y respaldos"; Filename: "{localappdata}\PresupuestosApp"
Name: "{group}\Desinstalar Presupuestos"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Presupuestos"; Filename: "{app}\{#AppExe}"; Tasks: escritorio

[Run]
Filename: "{app}\{#AppExe}"; Description: "Abrir Presupuestos ahora"; Flags: nowait postinstall skipifsilent

; Los datos (%LOCALAPPDATA%\PresupuestosApp) NO se borran al desinstalar ni al actualizar.
