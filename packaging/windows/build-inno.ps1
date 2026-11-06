$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$iss = Join-Path $root 'packaging\windows\slang.iss'
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) { throw 'Inno Setup (ISCC.exe) is required.' }
& $iscc.Source $iss
