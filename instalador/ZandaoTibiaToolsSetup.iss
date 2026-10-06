; Instalador do Zandao Tibia Tools (Inno Setup 6), no mesmo modelo do Zandonadi Radar.
; Não compile na mão: use instalador\gerar_instalador.ps1, que faz o build e passa SourceDistDir/OutputDir.
;
; Instala por usuário (AppData\Local\Programs), sem pedir administrador: o programa grava ao lado do
; .exe o histórico de hunts, os preços dos embuimentos, os personagens etc.
;
; Instalador "limpo": nenhum dado pessoal vai junto (historico_hunts.json, dados_embuimentos.json,
; settings.json, preferencias.json, meus_personagens.json). Cada pessoa começa do zero, e numa
; atualização esses arquivos ficam intactos, porque o instalador nunca os cria nem apaga.

#define MyAppName "Zandao Tibia Tools"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "Zandao"
#define MyAppExeName "ZandaoTibiaTools.exe"
#ifndef SourceDistDir
  #define SourceDistDir "dist\ZandaoTibiaTools"
#endif
#ifndef OutputDir
  #define OutputDir "output"
#endif
#define ProjDir ".."

[Setup]
AppId={{5C7E2B91-3A4F-4D6B-8E1C-9F2A7B3D4E60}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir={#OutputDir}
OutputBaseFilename=ZandaoTibiaToolsSetup
SetupIconFile={#ProjDir}\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; fecha o app se estiver aberto (senão não dá para trocar os arquivos)
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um ícone na área de trabalho"; GroupDescription: "Ícones adicionais:"

; bibliotecas da versão anterior: apaga antes de copiar as novas (os dados do usuário ficam na pasta principal)
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"
; o Simulated Keys saiu do app na v1.0.5: apaga o .exe dele e o atalho de iniciar com o Windows
Type: files; Name: "{app}\macro\SimulatedKeys.exe"
Type: files; Name: "{userstartup}\ZandaoSimulatedKeys.lnk"

[Files]
Source: "{#SourceDistDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o {#MyAppName} agora"; Flags: nowait postinstall skipifsilent

[Code]
// A interface é desenhada pelo WebView2 da Microsoft. Windows 11 e Windows 10 atualizado já trazem;
// se não tiver, baixa o instalador oficial (~2 MB) e instala em silêncio.
function WebView2Instalado: Boolean;
var
  Versao: String;
begin
  Versao := '';
  if not RegQueryStringValue(HKLM32, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versao) then
    if not RegQueryStringValue(HKLM64, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versao) then
      RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Versao);
  Result := (Versao <> '') and (Versao <> '0.0.0.0');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  CodigoSaida: Integer;
begin
  Result := '';
  // versões até a 1.0.4 tinham o Simulated Keys: fecha se estiver rodando, para o instalador poder apagá-lo
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/IM SimulatedKeys.exe /F', '', SW_HIDE, ewWaitUntilTerminated, CodigoSaida);
  if WebView2Instalado then
    Exit;
  try
    WizardForm.StatusLabel.Caption := 'Baixando o componente WebView2 da Microsoft...';
    DownloadTemporaryFile('https://go.microsoft.com/fwlink/p/?LinkId=2124703', 'MicrosoftEdgeWebview2Setup.exe', '', nil);
    WizardForm.StatusLabel.Caption := 'Instalando o componente WebView2...';
    Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, CodigoSaida);
  except
  end;
  if not WebView2Instalado then
    MsgBox('Nao consegui instalar o componente WebView2 da Microsoft, que o Zandao Tibia Tools usa para desenhar a tela. ' +
           'Se o programa nao abrir, instale o "WebView2 Runtime" pelo site da Microsoft e abra o programa de novo.',
           mbInformation, MB_OK);
end;
