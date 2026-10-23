$ErrorActionPreference='Stop'
$phaseRoot=Split-Path -Parent $PSScriptRoot
$metadata=Join-Path $phaseRoot 'evidence\cft-metadata.json'
& curl.exe --fail --location --silent --show-error --output $metadata 'https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json'
if($LASTEXITCODE -ne 0){throw 'Official Chrome for Testing metadata retrieval failed'}
$release=(Get-Content -LiteralPath $metadata -Raw | ConvertFrom-Json).channels.Stable
$asset=$release.downloads.chrome | Where-Object platform -eq 'win64'
if($asset.url -notlike 'https://storage.googleapis.com/chrome-for-testing-public/*/win64/chrome-win64.zip'){throw 'Unexpected official asset URL'}
$archive=Join-Path $PSScriptRoot ('chrome-'+$release.version+'.zip')
if(!(Test-Path -LiteralPath $archive)){
    & curl.exe --fail --location --silent --show-error --output $archive $asset.url
    if($LASTEXITCODE -ne 0){throw 'Chrome for Testing download failed'}
}
Expand-Archive -LiteralPath $archive -DestinationPath $PSScriptRoot
$binary=Join-Path $PSScriptRoot 'chrome-win64\chrome.exe'
$signature=Get-AuthenticodeSignature -LiteralPath $binary
@{version=$release.version;url=$asset.url;archiveSha256=(Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLower();binarySha256=(Get-FileHash -LiteralPath $binary -Algorithm SHA256).Hash.ToLower();signatureStatus=[string]$signature.Status;signer=$signature.SignerCertificate.Subject;sourceVerification='Official HTTPS metadata and asset; local SHA256 recorded, not compared with an unavailable publisher digest';binary=$binary;time=(Get-Date -Format o)} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $phaseRoot 'evidence\cft-install.json') -Encoding utf8
Get-Content -LiteralPath (Join-Path $phaseRoot 'evidence\cft-install.json')
