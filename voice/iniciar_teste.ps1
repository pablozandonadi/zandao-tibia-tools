param(
    [switch]$PrepareOnly,
    [switch]$SelfTest,
    [ValidateSet('stable', 'beta', 'source')][string]$Channel = 'stable',
    [string]$DataDir,
    [string]$Text,
    [switch]$NoSpeech,
    [ValidateSet('piper', 'windows')][string]$Tts = 'piper',
    [switch]$BenchmarkTts,
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$runtime = Join-Path ([IO.Path]::GetTempPath()) 'tibia-tudo-voice-spike'
$venvPython = Join-Path $runtime 'venv\Scripts\python.exe'
$model = Join-Path $runtime 'vosk-model-small-pt-0.3'
$piperModel = Join-Path $runtime 'piper\pt_BR-faber-medium.onnx'
try {
    if ($BenchmarkTts -and ($NoSpeech -or $Tts -ne 'piper' -or $SelfTest -or $PrepareOnly)) {
        throw '-BenchmarkTts requer -Tts piper e não combina com -NoSpeech, -SelfTest ou -PrepareOnly.'
    }
    New-Item -ItemType Directory -Force -Path $runtime | Out-Null
    if (-not (Test-Path -LiteralPath $venvPython)) {
        & $Python -m venv (Join-Path $runtime 'venv')
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao criar ambiente Python. Instale Python 3.10 a 3.12 de 64 bits ou informe -Python caminho.' }
    }
    if ($Tts -eq 'piper' -and -not $SelfTest -and (-not $NoSpeech -or $PrepareOnly)) {
        & $venvPython -c "import sys, importlib.util; from importlib.metadata import version; sys.exit(0 if importlib.util.find_spec('piper') and version('piper-tts') == '1.3.0' else 1)" 2>$null
        if ($LASTEXITCODE -ne 0) {
            & $venvPython -m pip install --disable-pip-version-check 'piper-tts==1.3.0'
            if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar Piper. Tente novamente ou use -Tts windows.' }
        }
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $piperModel) | Out-Null
        foreach ($suffix in @('', '.json')) {
            $target = $piperModel + $suffix
            if (-not (Test-Path -LiteralPath $target)) {
                Write-Host 'Baixando voz brasileira Piper Faber (modelo de aproximadamente 63 MB)...'
                Invoke-WebRequest -UseBasicParsing -Uri ('https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx' + $suffix) -OutFile ($target + '.download')
                Move-Item -LiteralPath ($target + '.download') -Destination $target -Force
            }
        }
    }
    if (-not $BenchmarkTts) {
    & $venvPython -c "import sys, importlib.util; from importlib.metadata import version; sys.exit(0 if all(importlib.util.find_spec(n) for n in ('vosk', 'sounddevice')) and version('vosk') == '0.3.45' and version('sounddevice') == '0.5.5' else 1)" 2>$null
    if ($LASTEXITCODE -ne 0) {
        & $venvPython -m pip install --disable-pip-version-check 'vosk==0.3.45' 'sounddevice==0.5.5'
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao instalar dependências. Verifique a internet e tente novamente.' }
    }
    if (-not ((Test-Path -LiteralPath (Join-Path $model 'final.mdl')) -or (Test-Path -LiteralPath (Join-Path $model 'am\final.mdl')))) {
        Write-Host 'Baixando modelo português offline (aproximadamente 31 MB)...'
        $archive = Join-Path $runtime 'modelo.zip'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip' -OutFile $archive
        $extract = @"
import pathlib, sys, zipfile
root = pathlib.Path(sys.argv[2]).resolve()
with zipfile.ZipFile(sys.argv[1]) as archive:
    for member in archive.infolist():
        target = (root / member.filename).resolve()
        if not target.is_relative_to(root) or pathlib.PurePosixPath(member.filename).parts[0] != 'vosk-model-small-pt-0.3':
            raise ValueError('Caminho inesperado no modelo')
    archive.extractall(root)
"@
        & $venvPython -c $extract $archive $runtime
        if ($LASTEXITCODE -ne 0) { throw 'Falha ao extrair modelo.' }
        Remove-Item -LiteralPath $archive
    }
    }
    if ($SelfTest) {
        & $venvPython -B -m unittest discover -s $PSScriptRoot -p 'test_spike_assistente.py' -v
        if ($LASTEXITCODE -ne 0) { throw 'Os testes falharam.' }
        exit 0
    }
    if ($PrepareOnly) { Write-Host 'Pronto. Modelo e dependências preparados; microfone não foi aberto.'; exit 0 }
    $arguments = @('-B', (Join-Path $PSScriptRoot 'spike_assistente.py'), '--model', $model, '--channel', $Channel, '--tts', $Tts, '--piper-model', $piperModel)
    if ($BenchmarkTts) { $arguments += '--benchmark-tts' }
    if ($DataDir) { $arguments += @('--data-dir', $DataDir) }
    if ($PSBoundParameters.ContainsKey('Text')) { $arguments += @('--text', $Text) }
    if ($NoSpeech) { $arguments += '--no-speech' }
    & $venvPython @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Teste encerrado com erro.' }
} catch {
    Write-Host ('Não foi possível executar: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
