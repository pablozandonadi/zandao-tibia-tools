# Gera o instalador do Zandao Tibia Tools (ZandaoTibiaToolsSetup.exe), igual ao do Zandonadi Radar:
#   1) testes;
#   2) PyInstaller empacota o app (zandao_tibia_tools.py + web/) numa pasta com o .exe;
#   3) Inno Setup transforma essa pasta no instalador.
# Os arquivos do build ficam em %TEMP%\zandao_tibia_tools_build, fora da pasta do projeto (Google Drive).
#
# Uso:  powershell -ExecutionPolicy Bypass -File .\instalador\gerar_instalador.ps1
# A versão vem de VERSAO_APP em versao.py (a mesma que o app compara com a última Release do GitHub).

param([string]$PastaBuild = (Join-Path $env:TEMP "zandao_tibia_tools_build"))

# "Continue" de propósito: PyInstaller e ISCC escrevem progresso no stderr. O sucesso é checado em $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot

$linhaVersao = Select-String -Path (Join-Path $raiz "versao.py") -Pattern '^VERSAO_APP\s*=\s*"([^"]+)"'
if (-not $linhaVersao) { throw "Nao achei VERSAO_APP em versao.py" }
$versao = $linhaVersao.Matches[0].Groups[1].Value
Write-Host "Versao: $versao"

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 nao encontrado." }

Write-Host "1/3  Testes..."
Push-Location $raiz
python -m unittest
$ok = $LASTEXITCODE
Pop-Location
if ($ok -ne 0) { throw "Testes falharam, instalador nao gerado." }

Write-Host "2/3  PyInstaller..."
$spec = Join-Path $PastaBuild "spec"
python -m PyInstaller --noconfirm --clean --windowed --name "ZandaoTibiaTools" `
    --icon (Join-Path $raiz "icon.ico") `
    --add-data "$(Join-Path $raiz 'web');web" --add-data "$(Join-Path $raiz 'sons_padrao');sons_padrao" --add-data "$(Join-Path $raiz 'icon.ico');." `
    --distpath (Join-Path $PastaBuild "dist") --workpath (Join-Path $PastaBuild "work") --specpath $spec `
    (Join-Path $raiz "zandao_tibia_tools.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

$app = Join-Path $PastaBuild "dist\ZandaoTibiaTools"
New-Item -ItemType Directory -Force (Join-Path $app "data") | Out-Null
Copy-Item (Join-Path $raiz "data\imbuements.json") (Join-Path $app "data") -Force

Write-Host "3/3  Inno Setup..."
& $iscc "/DMyAppVersion=$versao" "/DSourceDistDir=$app" "/DOutputDir=$(Join-Path $PastaBuild 'output')" `
    (Join-Path $PSScriptRoot "ZandaoTibiaToolsSetup.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou" }

Write-Host ""
Write-Host "Pronto: $(Join-Path $PastaBuild 'output\ZandaoTibiaToolsSetup.exe')"
