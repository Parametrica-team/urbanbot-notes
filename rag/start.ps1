param([string]$Python = '', [switch]$PullModels)
$ErrorActionPreference = 'Stop'
$ragRoot = $PSScriptRoot
$runtimeRoot = Join-Path $env:USERPROFILE '.local/share/urbanbot-rag'
$ollamaExe = Join-Path $runtimeRoot 'runtime/ollama/ollama.exe'
if (-not (Test-Path -LiteralPath $ollamaExe)) { throw 'Run rag/install.ps1 first.' }
if (-not $Python) {
    $bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $Python = $bundledPython }
    else { $Python = (Get-Command python -ErrorAction Stop).Source }
}
$env:OLLAMA_HOST = '127.0.0.1:11435'
$env:OLLAMA_MODELS = Join-Path $runtimeRoot 'models'
$env:OLLAMA_NO_CLOUD = '1'
$env:OLLAMA_MAX_LOADED_MODELS = '1'
$env:OLLAMA_NUM_PARALLEL = '1'
$env:RAG_OLLAMA_URL = 'http://127.0.0.1:11435'
New-Item -ItemType Directory -Force -Path (Join-Path $ragRoot '.state') | Out-Null
$modelListener = Get-NetTCPConnection -LocalPort 11435 -State Listen -ErrorAction SilentlyContinue
if ($modelListener) {
    $owner = Get-CimInstance Win32_Process -Filter "ProcessId = $($modelListener[0].OwningProcess)"
    if ($owner.ExecutablePath -ne $ollamaExe.Replace('/', '\')) { throw 'Port 11435 is occupied by a different service.' }
} else {
    $modelProcess = Start-Process $ollamaExe -ArgumentList 'serve' -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeRoot 'ollama.stdout.log') -RedirectStandardError (Join-Path $runtimeRoot 'ollama.stderr.log')
    $modelProcess.Id | Set-Content (Join-Path $ragRoot '.state/ollama.pid')
}
$ready = $false
for ($attempt=0; $attempt -lt 30; $attempt++) {
    try { $null=Invoke-RestMethod 'http://127.0.0.1:11435/api/version' -TimeoutSec 2; $ready=$true; break }
    catch { Start-Sleep -Seconds 1 }
}
if (-not $ready) { throw 'Ollama did not become ready; inspect its log.' }
if ($PullModels) {
    & $ollamaExe pull bge-m3
    if ($LASTEXITCODE -ne 0) { throw 'Embedding model pull failed' }
    & $ollamaExe pull qwen3:4b-instruct-2507-q4_K_M
    if ($LASTEXITCODE -ne 0) { throw 'Chat model pull failed' }
}
if (-not (Test-Path -LiteralPath (Join-Path $ragRoot '.state/index.sqlite'))) {
    & $Python (Join-Path $ragRoot 'app.py') index
    if ($LASTEXITCODE -ne 0) { throw 'Index build failed; run with -PullModels on first start.' }
}
$listener=Get-NetTCPConnection -LocalPort 48870 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    $owner=Get-CimInstance Win32_Process -Filter "ProcessId = $($listener[0].OwningProcess)"
    if (-not $owner.CommandLine.Contains((Join-Path $ragRoot 'app.py'))) { throw 'Port 48870 is occupied by another service.' }
} else {
    $appProcess=Start-Process $Python -ArgumentList @('"' + (Join-Path $ragRoot 'app.py') + '"','serve','--port','48870') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $ragRoot '.state/server.stdout.log') -RedirectStandardError (Join-Path $ragRoot '.state/server.stderr.log')
    $appProcess.Id | Set-Content (Join-Path $ragRoot '.state/server.pid')
}
Write-Output 'RAG: http://127.0.0.1:48870'
