# Read-only certificate lookup independent of the PowerShell Cert: provider.
function Find-JinganTrustedRoot {
    param([Parameter(Mandatory=$true)][string]$Thumbprint)
    $normalized = ($Thumbprint -replace '[\s\u200e\u200f]', '').ToUpperInvariant()
    if ($normalized -notmatch '^[0-9A-F]{40}$') { throw 'Invalid SHA-1 certificate thumbprint.' }
    foreach ($location in @('CurrentUser', 'LocalMachine')) {
        $store = [System.Security.Cryptography.X509Certificates.X509Store]::new('Root', $location)
        try {
            $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
            $matches = $store.Certificates.Find(
                [System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,
                $normalized, $false)
            if ($matches.Count -gt 0) {
                return [pscustomobject]@{ StoreLocation=$location; Thumbprint=$normalized }
            }
        } finally { $store.Close() }
    }
    return $null
}
