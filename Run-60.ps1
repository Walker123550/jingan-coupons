$ErrorActionPreference = 'Stop'
$linuxRoot = & wsl.exe -d Ubuntu --exec wslpath -a ($PSScriptRoot.Replace('\','/'))
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve WSL project path.' }
Write-Output 'Start about 10 minutes before release. Keep this window open and prevent sleep.'
& wsl.exe -d Ubuntu --exec ($linuxRoot.Trim()+'/.venv/bin/python') -u ($linuxRoot.Trim()+'/jingan.py') claim --coupon 4 --send
exit $LASTEXITCODE
