# PowerShell Code Signing Script for WhatsMation
# Generates a self-signed code signing certificate and signs the compiled binaries

$CertSubject = "CN=ALAN KJ Code Signing, O=ALAN KJ, C=IN"
$CertStoreLocation = "Cert:\CurrentUser\My"

Write-Host "Checking for existing Code Signing Certificate..." -ForegroundColor Cyan

$Cert = Get-ChildItem -Path $CertStoreLocation | Where-Object {
    $_.Subject -eq $CertSubject -and $_.EnhancedKeyUsageList.FriendlyName -contains "Code Signing"
} | Select-Object -First 1

if (-not $Cert) {
    Write-Host "Creating Self-Signed Code Signing Certificate..." -ForegroundColor Yellow
    $Cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $CertSubject `
        -CertStoreLocation $CertStoreLocation `
        -NotAfter (Get-Date).AddYears(3)
    Write-Host "Created Certificate with Thumbprint: $($Cert.Thumbprint)" -ForegroundColor Green
} else {
    Write-Host "Found existing certificate: $($Cert.Thumbprint)" -ForegroundColor Green
}

# Sign files in dist_release if they exist
$FilesToSign = Get-ChildItem -Path "dist_release" -Include "*.exe", "*.dll" -Recurse -ErrorAction SilentlyContinue

if ($FilesToSign) {
    foreach ($File in $FilesToSign) {
        Write-Host "Signing file: $($File.FullName)..." -ForegroundColor Cyan
        Set-AuthenticodeSignature -FilePath $File.FullName -Certificate $Cert -TimestampServer "http://timestamp.digicert.com"
    }
    Write-Host "All release executables signed successfully!" -ForegroundColor Green
} else {
    Write-Host "No files found in dist_release to sign. Run build_release.py first." -ForegroundColor Yellow
}
