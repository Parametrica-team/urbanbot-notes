param([string]$Python='', [string]$Vault='')
$ErrorActionPreference='Stop'
if (-not $Python) {
    $bundledPython=Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
    if (Test-Path -LiteralPath $bundledPython) { $Python=$bundledPython } else { $Python=(Get-Command python -ErrorAction Stop).Source }
}
if ($Vault) {
    & node (Join-Path $PSScriptRoot '../scripts/import-vault.mjs') $Vault
    if ($LASTEXITCODE -ne 0) { throw 'Vault import failed' }
}
& $Python -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; previous index retained' }
$previousDbEnv=$env:RAG_DB_PATH
$previousCacheEnv=$env:RAG_CACHE_DB_PATH
$candidate=Join-Path $PSScriptRoot '.state/index.candidate.sqlite'
$production=Join-Path $PSScriptRoot '.state/index.sqlite'
$embeddingCache=Join-Path $PSScriptRoot '.state/embedding-cache.sqlite'
try {
    $env:RAG_DB_PATH=$candidate
    $env:RAG_CACHE_DB_PATH=if(Test-Path -LiteralPath $embeddingCache){$embeddingCache}else{$production}
    & $Python (Join-Path $PSScriptRoot 'app.py') index
    if ($LASTEXITCODE -ne 0) { throw 'Index update failed; previous index retained' }
    # Cached vectors are reusable even when answer evaluation fails; this is never served.
    Copy-Item -LiteralPath $candidate -Destination $embeddingCache -Force
    & $Python (Join-Path $PSScriptRoot 'evaluate.py')
    if ($LASTEXITCODE -ne 0) { throw 'Evaluation failed; previous index retained. Inspect rag/.state/evaluation.json' }
    if (Test-Path -LiteralPath $production) { Copy-Item -LiteralPath $production -Destination ($production + '.backup') -Force }
    # os.replace is atomic and replaces only after successful evaluation.
    & $Python -c 'import os,sys; os.replace(sys.argv[1],sys.argv[2])' $candidate $production
    if ($LASTEXITCODE -ne 0) { throw 'Candidate promotion failed; previous index retained' }
} finally {
    $env:RAG_DB_PATH=$previousDbEnv
    $env:RAG_CACHE_DB_PATH=$previousCacheEnv
    if (Test-Path -LiteralPath $candidate) { Remove-Item -LiteralPath $candidate }
}
Write-Output 'Index rebuilt and evaluated. No files were automatically committed or published.'
