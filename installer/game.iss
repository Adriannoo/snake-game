#define RootDir AddBackslash(SourcePath) + ".."
#ifndef AppIdentifier
  #define AppIdentifier "SnakeGame-8DFAB340-71E0-48BB-A867-EA2168CFE711"
#endif
#ifndef SetupName
  #define SetupName "SnakeGame-Setup"
#endif

[Setup]
AppId={#AppIdentifier}
AppName=Snake Game
AppVersion=1.0.0
DefaultDirName={localappdata}\Programs\SnakeGame
DefaultGroupName=Snake Game
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#RootDir}\releases
OutputBaseFilename={#SetupName}
SetupIconFile={#RootDir}\build\snake.ico
UninstallDisplayIcon={app}\SnakeGame.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked

[Files]
Source: "{#RootDir}\dist\SnakeGame.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Snake Game"; Filename: "{app}\SnakeGame.exe"
Name: "{userdesktop}\Snake Game"; Filename: "{app}\SnakeGame.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\SnakeGame.exe"; Description: "Abrir Snake Game"; Flags: nowait postinstall skipifsilent
