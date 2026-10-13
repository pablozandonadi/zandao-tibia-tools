param([Parameter(Mandatory=$true)][string]$PastaBuild,[Parameter(Mandatory=$true)][string]$Versao,[ValidateSet('stable','beta')][string]$Canal='stable')
$ErrorActionPreference='Stop'
$taskSource=Split-Path -Parent $PSScriptRoot
$taskApp=Join-Path $PastaBuild 'dist\ZandaoTibiaTools'
$taskInstaller=Join-Path $PastaBuild ('output\'+ $(if($Canal -eq 'beta'){'ZandaoTibiaToolsBetaSetup.exe'}else{'ZandaoTibiaToolsSetup.exe'}))
if (!(Test-Path -LiteralPath $taskInstaller)) { throw 'Instalador ausente' }
python (Join-Path $taskSource 'package_tools.py') verify $taskApp
if ($LASTEXITCODE -ne 0) { throw 'Manifesto do portátil inválido' }
$taskPrefix=if($Canal -eq 'beta'){'ZandaoTibiaToolsBeta'}else{'ZandaoTibiaTools'}
$taskZip=Join-Path $PastaBuild "output\$taskPrefix-v$Versao.zip"
Compress-Archive -Path "$taskApp/*" -DestinationPath $taskZip -Force
$taskHashes=Join-Path $PastaBuild 'output\SHA256SUMS.txt'
python (Join-Path $taskSource 'package_tools.py') hashes $taskHashes $taskInstaller $taskZip
if ($LASTEXITCODE -ne 0) { throw 'Não foi possível gerar hashes' }
Copy-Item -LiteralPath (Join-Path $taskApp 'package-manifest.json') -Destination (Join-Path $PastaBuild 'output\package-manifest.json') -Force
Copy-Item -LiteralPath (Join-Path $taskApp 'sbom.json') -Destination (Join-Path $PastaBuild 'output\sbom.json') -Force
