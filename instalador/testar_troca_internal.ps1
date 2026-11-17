# Teste da troca da _internal: atualização interrompida no meio não pode deixar o app sem _internal\python314.dll.
# Usa a identidade de teste (ValidationBuild, AppId próprio) com arquivos falsos e instala só em <Raiz>\app.
# Rodar: powershell -File instalador\testar_troca_internal.ps1 -Raiz Z:\Temp\zt-inst-test   (precisa do Inno Setup 6)
# Esperado: "B abortado" e "B com _internal em uso" mostram exe A + dll A; "B normal" mostra exe B e só so_B.pyd.
param([string]$Iss = (Join-Path $PSScriptRoot 'ZandaoTibiaToolsSetup.iss'), [string]$Rotulo = 'atual', [string]$Raiz = (Join-Path ([IO.Path]::GetTempPath()) 'zt-inst-test'))
$ErrorActionPreference = 'Stop'
$raiz = $Raiz
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
if (Test-Path $raiz) { Remove-Item -Recurse -Force $raiz }
foreach ($v in 'A', 'B') {
    $d = "$raiz\dist$v"; New-Item -ItemType Directory -Force "$d\_internal" | Out-Null
    Set-Content -Encoding ascii "$d\ZandaoTibiaTools.exe" "exe $v"
    Set-Content -Encoding ascii "$d\_internal\python314.dll" "dll $v"
    Set-Content -Encoding ascii "$d\_internal\so_$v.pyd" "so $v"
    & $iscc /Q /DValidationBuild /DMyAppChannel=stable "/DMyAppVersion=1.0.$([int][char]$v)" "/DSourceDistDir=$d" "/DOutputDir=$raiz\out$v" $Iss | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "ISCC falhou ($v)" }
}
$app = "$raiz\app"
$flags = '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOCLOSEAPPLICATIONS', '/TASKS=""', "/DIR=$app"
$p = Start-Process "$raiz\outA\TibiaTudoValidationSetup.exe" -ArgumentList $flags -Wait -PassThru
"[$Rotulo] instalar A: codigo $($p.ExitCode); internal = $((Get-ChildItem "$app\_internal" -Name) -join ',')"

# B com o exe travado (simula algo segurando o arquivo): a cópia falha e a instalação aborta no meio
$trava = [IO.File]::Open("$app\ZandaoTibiaTools.exe", 'Open', 'Read', 'None')
try { $p = Start-Process "$raiz\outB\TibiaTudoValidationSetup.exe" -ArgumentList $flags -Wait -PassThru }
finally { $trava.Close() }
$dll = if (Test-Path "$app\_internal\python314.dll") { Get-Content "$app\_internal\python314.dll" } else { 'FALTANDO' }
"[$Rotulo] B abortado: codigo $($p.ExitCode); exe = $(Get-Content "$app\ZandaoTibiaTools.exe"); python314.dll = $dll; pastas = $((Get-ChildItem $app -Name) -join ',')"

# B com um arquivo da _internal travado (app antigo ainda aberto): não pode sobrar app sem python314.dll
$trava = [IO.File]::Open("$app\_internal\python314.dll", 'Open', 'Read', 'None')
try { $p = Start-Process "$raiz\outB\TibiaTudoValidationSetup.exe" -ArgumentList $flags -Wait -PassThru }
finally { $trava.Close() }
$dll = if (Test-Path "$app\_internal\python314.dll") { Get-Content "$app\_internal\python314.dll" } else { 'FALTANDO' }
"[$Rotulo] B com _internal em uso: codigo $($p.ExitCode); exe = $(Get-Content "$app\ZandaoTibiaTools.exe"); python314.dll = $dll; internal = $((Get-ChildItem "$app\_internal" -Name -ErrorAction SilentlyContinue) -join ','); pastas = $((Get-ChildItem $app -Name) -join ',')"

# B normal: tem que terminar com tudo novo e sem sobras
$p = Start-Process "$raiz\outB\TibiaTudoValidationSetup.exe" -ArgumentList $flags -Wait -PassThru
"[$Rotulo] B normal: codigo $($p.ExitCode); exe = $(Get-Content "$app\ZandaoTibiaTools.exe"); internal = $((Get-ChildItem "$app\_internal" -Name) -join ','); pastas = $((Get-ChildItem $app -Name) -join ',')"
$p = Start-Process "$app\unins000.exe" -ArgumentList '/VERYSILENT', '/SUPPRESSMSGBOXES' -Wait -PassThru
"[$Rotulo] desinstalado: codigo $($p.ExitCode)"
