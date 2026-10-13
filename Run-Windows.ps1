param(
    [ValidateSet('list','doctor','claim','bag','logs')][string]$Action = 'claim',
    [ValidateRange(1,2147483647)][int]$CouponId = 4,
    [switch]$DryRun,
    [string]$At = '',
    [string]$Proxy = ''
)
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$python = Join-Path $PSScriptRoot '.venv-win\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run Setup-Windows.ps1 first.' }
$runArgs = @('-u', (Join-Path $PSScriptRoot 'jingan.py'))
if ($Proxy) { $runArgs += @('--proxy', $Proxy) }
$runArgs += $Action
if ($Action -eq 'claim') {
    $runArgs += @('--coupon', $CouponId)
    if (-not $DryRun) { $runArgs += '--send' }
    if ($At) { $runArgs += @('--at', $At) }
}
& $python @runArgs
exit $LASTEXITCODE
