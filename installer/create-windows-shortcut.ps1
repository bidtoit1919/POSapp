param([Parameter(Mandatory=$true)][string]$ApplicationPath)
$desktop = [Environment]::GetFolderPath('Desktop')
$shortcut = Join-Path $desktop 'ShopPOS.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath = $ApplicationPath
$link.WorkingDirectory = Split-Path $ApplicationPath
$link.IconLocation = "$ApplicationPath,0"
$link.Description = 'Open ShopPOS'
$link.Save()
Write-Host "Created desktop shortcut: $shortcut"
