; ============================================================
; SOFTIA - SCRIPT DE INSTALADOR (INNO SETUP)
; ============================================================
;
; Este script empacota a pasta gerada pelo PyInstaller
; (SoftIA\dist\SoftIA) em um instalador único (SoftIA_Setup.exe).
;
; Como gerar o instalador:
; 1. Gere a build mais recente do app (a partir da pasta SoftIA):
;      python -m PyInstaller --name SoftIA --windowed ^
;        --icon "Imagens/softia.ico" --add-data "Imagens;Imagens" ^
;        --collect-all sounddevice --collect-all cv2 --collect-all mss ^
;        --noconfirm main.py
; 2. Compile este script (a partir da pasta Setup):
;      "ISCC.exe" SoftIA.iss
; 3. O instalador final aparece em Setup\Instalador\SoftIA_Setup.exe
;
; A chave de API do Gemini NUNCA é incluída aqui. Cada usuário
; informa a própria chave na primeira execução do programa
; (tela de configuração inicial do SOFTIA).
; ============================================================

#define MyAppName "SoftIA"
#define MyAppVersion "1.9.2.5"
#define MyAppPublisher "Klecio Mauricio"
#define MyAppExeName "SoftIA.exe"

; Pasta com o resultado da build do PyInstaller (onedir).
; Este script agora fica dentro de SoftIA\Setup, por isso o
; caminho sobe apenas um nível para chegar em SoftIA\dist.
#define MyDistDir "..\dist\SoftIA"

[Setup]
AppId={{B6E2F6A0-6C1E-4B7B-9E3B-9F1B7C5C9A11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=Instalador
OutputBaseFilename=SoftIA_Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
; Copia toda a pasta gerada pelo PyInstaller (exe + dependências).
Source: "{#MyDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName} agora"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove os arquivos de execução do programa. Isso é seguro porque
; a chave de API, as memórias e a agenda do usuário ficam salvas
; fora da pasta de instalação, em %APPDATA%\SoftIA, e não são
; apagadas por este desinstalador.
Type: filesandordirs; Name: "{app}\_internal"
