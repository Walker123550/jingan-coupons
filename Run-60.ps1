param([string]$Distro = 'Ubuntu', [switch]$DryRun)
$ErrorActionPreference = 'Stop'
$linuxRoot = & wsl.exe -d $Distro --exec wslpath -a ($PSScriptRoot.Replace('\','/'))
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve WSL project path.' }
Write-Output 'Start about 10 minutes before release. Keep this window open and prevent sleep.'
$runArgs = @('-d', $Distro, '--exec', ($linuxRoot.Trim()+'/.venv/bin/python'), '-u', ($linuxRoot.Trim()+'/jingan.py'), 'claim', '--coupon', '4')
if (-not $DryRun) { $runArgs += '--send' }
& wsl.exe @runArgs
exit $LASTEXITCODE
