param([int]$DelaySeconds = 0, [string]$CaptureId = '')
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'WindowsProxy.ps1')
if ($DelaySeconds -gt 0) { Start-Sleep -Seconds $DelaySeconds }
$statePath = Join-Path $PSScriptRoot 'private\windows-state.json'
if (-not (Test-Path -LiteralPath $statePath)) { exit 0 }
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
if ($CaptureId -and $CaptureId -ne $state.captureId) { exit 0 }
$regPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings'
$current = Get-ItemProperty -LiteralPath $regPath
# Respect an intervening user change to the proxy.
if ($current.ProxyServer -eq '127.0.0.1:18080') {
    foreach ($name in @('ProxyEnable', 'ProxyServer', 'ProxyOverride', 'AutoConfigURL')) {
        $property = $state.original.PSObject.Properties[$name]
        if ($null -ne $property) {
            Set-ItemProperty -LiteralPath $regPath -Name $name -Value $property.Value
        } else {
            Remove-ItemProperty -LiteralPath $regPath -Name $name -ErrorAction SilentlyContinue
        }
    }
    if ($state.connections) {
        $key='HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings\Connections'
        foreach($property in $state.connections.PSObject.Properties) {
            Set-ItemProperty -LiteralPath $key -Name $property.Name -Value ([Convert]::FromBase64String($property.Value))
        }
    }
    [JinganProxySettings]::Notify()
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
}
if ($state.certificateAdded -and $state.thumbprint) {
    $certPath = 'Cert:\CurrentUser\Root\' + $state.thumbprint
    if (Test-Path -LiteralPath $certPath) {
        try { Remove-Item -LiteralPath $certPath } catch {
            # Root-store confirmation needs a user; still stop the capture service.
            @{thumbprint=$state.thumbprint;certificateFile=(Join-Path $PSScriptRoot 'private\mitm\mitmproxy-ca-cert.cer')} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'private\certificate-cleanup-pending.json') -Encoding utf8
            Write-Warning 'Temporary certificate removal requires interactive confirmation; capture will still stop.'
        }
    }
}
& wsl.exe -d Ubuntu -- ($state.linuxRoot + '/.venv/bin/python') ($state.linuxRoot + '/proxy_service.py') stop
Remove-Item -LiteralPath $statePath
Write-Output 'Capture stopped; original Windows proxy restored. Certificate cleanup may require user confirmation.'
