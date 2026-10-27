# Per-user Windows 10/11 lock image. Never changes authentication, policy or sign-in screen.
param(
    [Parameter(Mandatory=$true)][ValidateSet('Backup','Set')][string]$Operation,
    [Parameter(Mandatory=$true)][string]$ImagePath
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType=WindowsRuntime]
$null = [Windows.System.UserProfile.LockScreen, Windows.System.UserProfile, ContentType=WindowsRuntime]
$null = [Windows.System.UserProfile.UserProfilePersonalizationSettings, Windows.System.UserProfile, ContentType=WindowsRuntime]
function Await-Result($Operation, [Type]$ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
        $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetGenericArguments().Count -eq 1 -and
        $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
    } | Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.GetAwaiter().GetResult()
}
if ($Operation -eq 'Backup') {
    $uri = [Windows.System.UserProfile.LockScreen]::OriginalImageFile
    if ($null -eq $uri) { throw 'Nykyistä lukituskuvaa ei voi varmuuskopioida.' }
    if ($uri.Scheme -eq 'file') {
        $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($uri.LocalPath)) ([Windows.Storage.StorageFile])
    } else {
        $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromApplicationUriAsync($uri)) ([Windows.Storage.StorageFile])
    }
    [System.IO.File]::Copy($file.Path, $ImagePath, $true)
} else {
    if (-not [Windows.System.UserProfile.UserProfilePersonalizationSettings]::IsSupported()) {
        throw 'Windows ei salli tämän käyttäjän lukituskuvan vaihtamista.'
    }
    $file = Await-Result ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
    $ok = Await-Result ([Windows.System.UserProfile.UserProfilePersonalizationSettings]::Current.TrySetLockScreenImageAsync($file)) ([bool])
    if (-not $ok) { throw 'Windows ei hyväksynyt lukituskuvaa. Tarkista omat mukautusasetukset.' }
}
Write-Output 'OK'
