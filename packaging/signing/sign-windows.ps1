param(
  [Parameter(Mandatory=$true)][string]$CertificatePath,
  [Parameter(Mandatory=$true)][string]$CertificatePassword,
  [Parameter(Mandatory=$true)][string[]]$Files,
  [string]$TimestampUrl = 'http://timestamp.digicert.com'
)
$ErrorActionPreference = 'Stop'
$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
  $candidate = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
  if ($candidate) { $signtool = $candidate } else { throw 'signtool.exe not found.' }
}
foreach ($file in $Files) {
  if (!(Test-Path $file)) { throw "File not found: $file" }
  & $signtool.Source sign /fd SHA256 /f $CertificatePath /p $CertificatePassword /tr $TimestampUrl /td SHA256 $file
  if ($LASTEXITCODE -ne 0) { throw "Authenticode signing failed: $file" }
  & $signtool.Source verify /pa /all $file
  if ($LASTEXITCODE -ne 0) { throw "Signature verification failed: $file" }
}
