param([string]$InstallDir = "$env:LOCALAPPDATA\S-Lang\1.0")
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '..\..\dist\windows-x86_64\slang1.0.exe'
if (!(Test-Path $source)) { throw "Build slang1.0.exe first: python packaging/build-runtime.py" }
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
Copy-Item $source (Join-Path $InstallDir 'slang1.0.exe') -Force
$userPath = [Environment]::GetEnvironmentVariable('Path','User')
if (($userPath -split ';') -notcontains $InstallDir) {
  [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';') + ';' + $InstallDir).TrimStart(';')), 'User')
}
Write-Host "S-Lang installed to $InstallDir"
Write-Host 'Open a new terminal, then run: slang version'
