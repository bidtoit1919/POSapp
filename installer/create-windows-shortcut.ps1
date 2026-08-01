param([Parameter(Mandatory=$true)][string]$ApplicationPath)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $ApplicationPath -PathType Leaf)) {
  throw "ShopPOS executable was not found: $ApplicationPath"
}
$desktop = [Environment]::GetFolderPath('Desktop')
$directory = Split-Path -LiteralPath $ApplicationPath
$resolvedApplication = (Resolve-Path -LiteralPath $ApplicationPath).Path
$shortcut = Join-Path $desktop 'ShopPOS.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $resolvedApplication
$link.WorkingDirectory = $directory
$link.IconLocation = "$resolvedApplication,0"
$link.Description = 'Open ShopPOS'
$link.Save()
Write-Host "Created desktop shortcut: $shortcut"
