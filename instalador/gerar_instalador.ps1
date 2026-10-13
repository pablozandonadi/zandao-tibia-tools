# Gera o instalador do Zandao Tibia Tools (ZandaoTibiaToolsSetup.exe), igual ao do Zandonadi Radar:
#   1) testes;
#   2) PyInstaller empacota o app (zandao_tibia_tools.py + web/) numa pasta com o .exe;
#   3) Inno Setup transforma essa pasta no instalador.
# Os arquivos do build ficam em %TEMP%\zandao_tibia_tools_build, fora da pasta do projeto (Google Drive).
#
# Uso:  powershell -ExecutionPolicy Bypass -File .\instalador\gerar_instalador.ps1
# A versão vem de VERSAO_APP em versao.py (a mesma que o app compara com a última Release do GitHub).

param(
    [string]$PastaBuild = (Join-Path $env:TEMP "zandao_tibia_tools_build"),
    [ValidateSet("stable", "beta")][string]$Canal = "stable",
    [string]$BetaBuild = "",
    [string]$SourceCommit = "",
    [string]$SigningThumbprint = $env:TIBIA_SIGNING_THUMBPRINT,
    [switch]$RequireSignature = ($env:TIBIA_REQUIRE_SIGNATURE -eq "true")
)

# "Continue" de propósito: PyInstaller e ISCC escrevem progresso no stderr. O sucesso é checado em $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$raiz = Split-Path -Parent $PSScriptRoot

$linhaVersao = Select-String -Path (Join-Path $raiz "versao.py") -Pattern '^VERSAO_APP\s*=\s*"([^"]+)"'
if (-not $linhaVersao) { throw "Nao achei VERSAO_APP em versao.py" }
$versao = $linhaVersao.Matches[0].Groups[1].Value
$versaoInstalador = $versao
if ($Canal -eq "beta") {
    if ($BetaBuild -notmatch '^\d+\.\d+$') { throw "BetaBuild deve ser numero.tentativa" }
    $versao = "$versao-beta.$BetaBuild"
}
Write-Host "Versao: $versao ($Canal)"

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 7\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw "Inno Setup 6 nao encontrado." }
$taskCompilerInfo = (Get-Item -LiteralPath $iscc).VersionInfo.ProductVersion
if ($taskCompilerInfo -notmatch '6\.7\.1') { throw 'Use Inno Setup 6.7.1 para este build fixado.' }

# Também é usado pelo workflow de publicação; fixa o rasterizador incluído no executável.
python -m pip install --require-hashes -r (Join-Path $raiz 'requirements-bootstrap.lock')
if ($LASTEXITCODE -ne 0) { throw 'Falha no bootstrap fixado' }
python -m pip install --no-build-isolation --require-hashes -r (Join-Path $raiz 'requirements-build.lock')
if ($LASTEXITCODE -ne 0) { throw "Falha ao instalar o rasterizador dos timers." }

python (Join-Path $raiz 'package_tools.py') resources $raiz
if ($LASTEXITCODE -ne 0) { throw 'Recursos fora da allowlist' }
Write-Host "1/3  Testes..."
Push-Location $raiz
python -m unittest
$ok = $LASTEXITCODE
Pop-Location
if ($ok -ne 0) { throw "Testes falharam, instalador nao gerado." }

Write-Host "2/3  PyInstaller..."
$spec = Join-Path $PastaBuild "spec"
New-Item -ItemType Directory -Force $PastaBuild | Out-Null
$metadata = Join-Path $PastaBuild "canal_build.json"
$taskPolicy = Join-Path $PastaBuild 'signing_policy.json'
$taskSigned = [bool]$SigningThumbprint
if ($RequireSignature -and !$taskSigned) { throw 'Certificado obrigatório não configurado' }
@{required=$taskSigned;thumbprints=@($(if($taskSigned){$SigningThumbprint.ToUpper()}))} | ConvertTo-Json | Set-Content -LiteralPath $taskPolicy -Encoding utf8
@{canal=$Canal; versao=$versao; source_sha=$SourceCommit} | ConvertTo-Json | Set-Content -LiteralPath $metadata -Encoding utf8
python -m PyInstaller --noconfirm --clean --windowed --name "ZandaoTibiaTools" `
    --add-data "$metadata;." --add-data "$taskPolicy;." `
    --icon (Join-Path $raiz "icon.ico") `
    --add-data "$(Join-Path $raiz 'web');web" --add-data "$(Join-Path $raiz 'sons_padrao');sons_padrao" --add-data "$(Join-Path $raiz 'icon.ico');." `
    --distpath (Join-Path $PastaBuild "dist") --workpath (Join-Path $PastaBuild "work") --specpath $spec `
    (Join-Path $raiz "zandao_tibia_tools.py")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller falhou" }

$app = Join-Path $PastaBuild "dist\ZandaoTibiaTools"
New-Item -ItemType Directory -Force (Join-Path $app "data") | Out-Null
Copy-Item (Join-Path $raiz "data\imbuements.json") (Join-Path $app "data") -Force
Copy-Item (Join-Path $raiz "data\task_items.json") (Join-Path $app "data") -Force
Copy-Item (Join-Path $raiz "data\creature_knowledge.json") (Join-Path $app "data") -Force
Copy-Item (Join-Path $raiz "data\hunt_catalog.json") (Join-Path $app "data") -Force

& (Join-Path $PSScriptRoot 'assinar.ps1') -Arquivo (Join-Path $app 'ZandaoTibiaTools.exe') -Thumbprint $SigningThumbprint -Obrigatorio:$RequireSignature
if ($LASTEXITCODE -ne 0) { throw 'Assinatura do app falhou' }
python (Join-Path $raiz 'package_tools.py') create $app $raiz $versao $Canal $SourceCommit
if ($LASTEXITCODE -ne 0) { throw 'Manifesto/pacote inválido' }
Write-Host "3/3  Inno Setup..."
& $iscc "/DMyAppVersion=$versao" "/DMyAppNumericVersion=$versaoInstalador" "/DMyAppChannel=$Canal" "/DSourceDistDir=$app" "/DOutputDir=$(Join-Path $PastaBuild 'output')" `
    (Join-Path $PSScriptRoot "ZandaoTibiaToolsSetup.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup falhou" }

Write-Host ""
$installerName = if ($Canal -eq "beta") { "ZandaoTibiaToolsBetaSetup.exe" } else { "ZandaoTibiaToolsSetup.exe" }
& (Join-Path $PSScriptRoot 'assinar.ps1') -Arquivo (Join-Path $PastaBuild "output\$installerName") -Thumbprint $SigningThumbprint -Obrigatorio:$RequireSignature
if ($LASTEXITCODE -ne 0) { throw 'Assinatura do instalador falhou' }
Write-Host "Pronto: $(Join-Path $PastaBuild "output\$installerName")"

