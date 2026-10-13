param([Parameter(Mandatory=$true)][string]$Arquivo, [string]$Thumbprint, [switch]$Obrigatorio)
$ErrorActionPreference = 'Stop'
if (!$Thumbprint) {
    if ($Obrigatorio) { throw 'Certificado de assinatura não configurado. Build bloqueado.' }
    Write-Host 'Sem certificado: pacote de análise não assinado.'
    exit 0
}
if ($Thumbprint -notmatch '^[0-9a-fA-F]{40}$') { throw 'Thumbprint inválido' }
$taskSignTool = (Get-Command signtool.exe -ErrorAction SilentlyContinue).Source
if (!$taskSignTool) {
    $taskSignTool = Get-ChildItem -Path "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1 -ExpandProperty FullName
}
if (!$taskSignTool) { throw 'SignTool do Windows SDK não encontrado' }
& $taskSignTool sign /sha1 $Thumbprint /fd SHA256 /tr https://timestamp.digicert.com /td SHA256 $Arquivo
if ($LASTEXITCODE -ne 0) { throw 'Assinatura falhou' }
$taskSignature = Get-AuthenticodeSignature -LiteralPath $Arquivo
if ($taskSignature.Status -ne 'Valid' -or $taskSignature.SignerCertificate.Thumbprint -ne $Thumbprint -or !$taskSignature.TimeStamperCertificate) { throw 'Assinatura/publicador/timestamp inválidos' }
