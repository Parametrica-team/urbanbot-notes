$ErrorActionPreference='Stop'
$runtimeRoot=Join-Path $env:USERPROFILE '.local/share/urbanbot-rag/runtime'
New-Item -ItemType Directory -Force -Path $runtimeRoot | Out-Null
$zip=Join-Path $runtimeRoot 'ollama.zip'
if (-not (Test-Path -LiteralPath $zip)) {
    Invoke-WebRequest 'https://github.com/ollama/ollama/releases/download/v0.40.13/ollama-windows-amd64.zip' -OutFile $zip
}
$expected='7afa38624fa62ee5d8293422d0ab084c1bb4603134c7f4dafce11a033b57cc19'
if ((Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Runtime checksum mismatch' }
Expand-Archive -LiteralPath $zip -DestinationPath (Join-Path $runtimeRoot 'ollama') -Force
Write-Output 'Runtime installed without changing system services or PATH. Next: ./rag/start.ps1 -PullModels'
