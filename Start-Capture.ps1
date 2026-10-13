param([ValidateRange(60, 7200)][int]$DurationSeconds = 7200, [string]$Distro = 'Ubuntu', [string]$UpstreamProxy = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'WindowsProxy.ps1')
$statePath = Join-Path $PSScriptRoot 'private\windows-state.json'
$regPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
if (Test-Path -LiteralPath $statePath) {
    $saved = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
    if ($saved.distro) { $Distro = $saved.distro }
    $statusText = & wsl.exe -d $Distro --exec ($saved.linuxRoot + '/.venv/bin/python') ($saved.linuxRoot + '/proxy_service.py') status
    if ($LASTEXITCODE -ne 0) { throw 'Could not inspect existing capture process.' }
    $status = $statusText | ConvertFrom-Json
    if ($status.running -and (Test-Path -LiteralPath ('Cert:\CurrentUser\Root\' + $saved.thumbprint))) {
        if (-not $saved.PSObject.Properties['connections']) {
            $saved | Add-Member -NotePropertyName connections -NotePropertyValue (Get-JinganConnectionSnapshot)
        }
        # Preserve the original proxy and in-memory flows, but invalidate old watchdogs.
        $saved.captureId = [guid]::NewGuid().ToString()
        $saved | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding utf8
        Set-ItemProperty -LiteralPath $regPath -Name ProxyServer -Value '127.0.0.1:18080'
        Set-ItemProperty -LiteralPath $regPath -Name ProxyEnable -Value 1
        Remove-ItemProperty -LiteralPath $regPath -Name AutoConfigURL -ErrorAction SilentlyContinue
        [JinganProxySettings]::Apply('127.0.0.1:18080', [string]$saved.original.ProxyOverride)
        if (-not ('JinganInternetSettings' -as [type])) {
            Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class JinganInternetSettings {
    [DllImport("wininet.dll")] public static extern bool InternetSetOption(IntPtr h, int option, IntPtr buffer, int length);
}
'@
        }
        [void][JinganInternetSettings]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0)
        [void][JinganInternetSettings]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0)
        & wsl.exe -d $Distro --exec ($saved.linuxRoot + '/.venv/bin/python') ($saved.linuxRoot + '/proxy_service.py') guard --capture-id $saved.captureId --duration $DurationSeconds
        if ($LASTEXITCODE -ne 0) { & (Join-Path $PSScriptRoot 'Restore-Capture.ps1'); throw 'Could not start capture guard.' }
        Write-Output ('Capture ready (existing session resumed); automatic restore in ' + $DurationSeconds + ' seconds.')
        return
    }
    # Recover stale state instead of treating a leftover file as a live session.
    & (Join-Path $PSScriptRoot 'Restore-Capture.ps1')
}
$settings = Get-ItemProperty -LiteralPath $regPath
$original = @{}
foreach ($name in @('ProxyEnable', 'ProxyServer', 'ProxyOverride', 'AutoConfigURL')) {
    $property = $settings.PSObject.Properties[$name]
    if ($null -ne $property) { $original[$name] = $property.Value }
}
$wslPathInput = $PSScriptRoot.Replace('\', '/')
$resolvedPath = & wsl.exe -d $Distro --exec wslpath -a $wslPathInput
if ($LASTEXITCODE -ne 0 -or -not $resolvedPath) { throw 'Could not resolve WSL project path.' }
$linuxRoot = $resolvedPath.Trim()
if ($LASTEXITCODE -ne 0) { throw 'Could not resolve WSL project path.' }
$upstream = $null
if ($UpstreamProxy) {
    if ($UpstreamProxy -notmatch '^[a-zA-Z0-9.\-]+:\d+$') { throw 'UpstreamProxy must be host:port reachable from WSL.' }
    $upstream = $UpstreamProxy
} elseif ($settings.ProxyEnable -eq 1 -and $settings.ProxyServer) {
    if ($settings.ProxyServer -notmatch '^[a-zA-Z0-9.\-]+:\d+$') { throw 'Existing proxy format requires manual upstream configuration.' }
    $upstream = $settings.ProxyServer
}
$launchArgs = @('-d', $Distro, '--exec', ($linuxRoot + '/.venv/bin/python'), ($linuxRoot + '/proxy_service.py'), 'start')
if ($upstream) { $launchArgs += @('--upstream', $upstream) }
& wsl.exe @launchArgs
if ($LASTEXITCODE -ne 0) { throw 'WSL capture service failed to start.' }
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new((Join-Path $PSScriptRoot 'private\mitm\mitmproxy-ca-cert.cer'))
$certAlreadyPresent = Test-Path -LiteralPath ('Cert:\CurrentUser\Root\' + $certificate.Thumbprint)
$captureId = [guid]::NewGuid().ToString()
$state = @{original = $original; connections = (Get-JinganConnectionSnapshot); thumbprint = $certificate.Thumbprint; certificateAdded = (-not $certAlreadyPresent); linuxRoot = $linuxRoot; distro = $Distro; captureId = $captureId}
$state | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $statePath -Encoding utf8
try {
    if (-not $certAlreadyPresent) {
        Import-Certificate -FilePath (Join-Path $PSScriptRoot 'private\mitm\mitmproxy-ca-cert.cer') -CertStoreLocation 'Cert:\CurrentUser\Root' | Out-Null
    }
    # Verify Windows -> WSL -> existing upstream -> HTTPS before switching system proxy.
    $probe = Invoke-WebRequest -Uri 'https://mitmproxy.org' -Proxy 'http://127.0.0.1:18080' -TimeoutSec 15
    if ($probe.StatusCode -ne 200) { throw 'HTTPS bridge test failed.' }
    Set-ItemProperty -LiteralPath $regPath -Name ProxyServer -Value '127.0.0.1:18080'
    Set-ItemProperty -LiteralPath $regPath -Name ProxyEnable -Value 1
    Remove-ItemProperty -LiteralPath $regPath -Name AutoConfigURL -ErrorAction SilentlyContinue
    [JinganProxySettings]::Apply('127.0.0.1:18080', [string]$original.ProxyOverride)
    if (-not ('JinganInternetSettings' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class JinganInternetSettings {
    [DllImport("wininet.dll")] public static extern bool InternetSetOption(IntPtr h, int option, IntPtr buffer, int length);
}
'@
    }
    [void][JinganInternetSettings]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0)
    [void][JinganInternetSettings]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0)
    & wsl.exe -d $Distro --exec ($linuxRoot + '/.venv/bin/python') ($linuxRoot + '/proxy_service.py') guard --capture-id $captureId --duration $DurationSeconds
    if ($LASTEXITCODE -ne 0) { throw 'Could not start capture guard.' }
    Write-Output ('Capture ready on 127.0.0.1:18080; automatic restore in ' + $DurationSeconds + ' seconds.')
} catch {
    & (Join-Path $PSScriptRoot 'Restore-Capture.ps1')
    throw
}
