$ErrorActionPreference='Stop'
foreach ($name in @('server','ollama')) {
    $pidFile=Join-Path $PSScriptRoot ".state/$name.pid"
    if (-not (Test-Path -LiteralPath $pidFile)) { continue }
    $servicePid=[int](Get-Content -LiteralPath $pidFile)
    $process=Get-CimInstance Win32_Process -Filter "ProcessId = $servicePid"
    if ($process) {
        $expected=if ($name -eq 'server') { Join-Path $PSScriptRoot 'app.py' } else { Join-Path $env:USERPROFILE '.local/share/urbanbot-rag/runtime/ollama/ollama.exe' }
        if (-not $process.CommandLine.Replace('/','\').Contains($expected.Replace('/','\'))) { throw "Refusing to stop unrelated PID $servicePid" }
        Stop-Process -Id $servicePid
    }
    Remove-Item -LiteralPath $pidFile
}
