param(
    [string]$Distro = 'Ubuntu',
    [ValidateRange(1, 2147483647)][int]$CouponId = 4,
    [switch]$DryRun,
    [string]$At = ''
)
$ErrorActionPreference = 'Stop'
$linuxRoot = & wsl.exe -d $Distro --exec wslpath -a ($PSScriptRoot.Replace('\','/'))
if ($LASTEXITCODE -ne 0 -or -not $linuxRoot) { throw 'Could not resolve WSL project path.' }
$python = $linuxRoot.Trim() + '/.venv/bin/python'
$script = $linuxRoot.Trim() + '/jingan.py'
$runArgs = @('-d', $Distro, '--exec', $python, '-u', $script, 'claim', '--coupon', $CouponId)
if (-not $DryRun) { $runArgs += '--send' }
if ($At) { $runArgs += @('--at', $At) }
Write-Output 'Keep this window open. Start 10 minutes before the intended release.'
& wsl.exe @runArgs
exit $LASTEXITCODE
