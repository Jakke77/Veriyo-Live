$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$exe = Join-Path $root 'Veriyo-Live.exe'
if (-not (Test-Path $exe)) { throw 'Pura koko ZIP ennen pikakuvakkeiden luontia.' }
$shell = New-Object -ComObject WScript.Shell
$menu = Join-Path ([Environment]::GetFolderPath('Programs')) 'Veriyo Live'
New-Item -ItemType Directory -Force -Path $menu | Out-Null
foreach ($folder in @([Environment]::GetFolderPath('Desktop'), $menu)) {
    $shortcut = $shell.CreateShortcut((Join-Path $folder 'Veriyo Live.lnk'))
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $root
    $shortcut.IconLocation = "$exe,0"
    $shortcut.Save()
}
Write-Output 'Veriyo Live -pikakuvakkeet luotu.'
