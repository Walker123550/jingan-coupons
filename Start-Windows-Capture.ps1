param([string]$UpstreamProxy = '')
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$mitmdump = Join-Path $PSScriptRoot '.venv-win\Scripts\mitmdump.exe'
if (-not (Test-Path -LiteralPath $mitmdump)) { throw 'Run Setup-Windows.ps1 -WithCapture first.' }
$runArgs = @('--quiet', '--listen-host', '127.0.0.1', '--listen-port', '18080', '--set', ('confdir='+(Join-Path $PSScriptRoot 'private\mitm')), '--set', 'block_global=true', '--set', 'stream_large_bodies=512k', '-s', (Join-Path $PSScriptRoot 'capture_addon.py'))
if ($UpstreamProxy) {
    if ($UpstreamProxy -notmatch '^[a-zA-Z0-9.\-]+:\d+$') { throw 'Use host:port for the HTTP upstream.' }
    $runArgs += @('--mode', ('upstream:http://'+$UpstreamProxy))
}
Write-Output 'Native capture listens on 127.0.0.1:18080. Keep this window open; Ctrl+C stops it.'
Write-Output 'This foreground tool does not change the system proxy or root certificates.'
Write-Output 'Follow docs/WINDOWS.md for manual proxy/certificate setup and restore.'
& $mitmdump @runArgs
exit $LASTEXITCODE
