$ErrorActionPreference = 'Stop'
$certFile = Join-Path $PSScriptRoot 'private\mitm\mitmproxy-ca-cert.cer'
$certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($certFile)
$rows = @()
foreach ($location in @('CurrentUser','LocalMachine')) {
    foreach ($name in @('Root','CA')) {
        $store = [System.Security.Cryptography.X509Certificates.X509Store]::new($name,$location)
        try {
            $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
            $rows += [pscustomobject]@{
                Location=$location; Store=$name
                Matches=$store.Certificates.Find('FindByThumbprint',$certificate.Thumbprint,$false).Count
            }
        } finally { $store.Close() }
    }
}
$result = [pscustomobject]@{
    Account=[System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    Thumbprint=$certificate.Thumbprint
    CheckedAt=(Get-Date).ToString('o')
    Stores=$rows
}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'private\certificate-diagnostic.json') -Encoding UTF8
$rows | Format-Table -AutoSize
Write-Output 'Read-only diagnostic saved. No proxy, trust or login settings changed.'
