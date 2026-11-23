param(
    [switch]$ReplaceDefault
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$LauncherPy = Join-Path $Root "launcher.py"
$IconPath = Join-Path $Root "assets\gemini_catgirl.ico"
$DesktopDir = [Environment]::GetFolderPath("Desktop")

# Auto-detect pythonw.exe on any Windows machine
$PywPath = $null
$cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
if ($cmd -and (Test-Path $cmd.Source)) {
    $PywPath = $cmd.Source
}
if (-not $PywPath) {
    $found = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python\Python3*\pythonw.exe" -ErrorAction SilentlyContinue | Sort-Object FullName -Descending | Select-Object -First 1
    if ($found) { $PywPath = $found.FullName }
}
if (-not $PywPath) {
    throw "Could not locate pythonw.exe. Please install Python 3.10+ and add it to PATH."
}

$ws = New-Object -ComObject WScript.Shell

# 1. Create dedicated "Antigravity (Gemini 娘).lnk" on Desktop
$shortcutPath = Join-Path $DesktopDir "Antigravity (Gemini 娘).lnk"
$sc = $ws.CreateShortcut($shortcutPath)
$sc.TargetPath = $PywPath
$sc.Arguments = "`"$LauncherPy`""
$sc.WorkingDirectory = $Root
$sc.Description = "Google Antigravity (Gemini Catgirl Startup Animation)"
if (Test-Path $IconPath) {
    $sc.IconLocation = "$IconPath,0"
}
$sc.Save()
Write-Output "Created Desktop shortcut: $shortcutPath"

# 2. Optionally replace default Antigravity.lnk (backing up original first)
if ($ReplaceDefault) {
    $origLnk = Join-Path $DesktopDir "Antigravity.lnk"
    $backupLnk = Join-Path $Root "Antigravity_original_backup.lnk"
    if ((Test-Path $origLnk) -and -not (Test-Path $backupLnk)) {
        Copy-Item $origLnk $backupLnk -Force
        Write-Output "Backed up original shortcut to: $backupLnk"
    }
    $sc2 = $ws.CreateShortcut($origLnk)
    $sc2.TargetPath = $PywPath
    $sc2.Arguments = "`"$LauncherPy`""
    $sc2.WorkingDirectory = $Root
    $sc2.Description = "Google Antigravity (Gemini Catgirl Startup Animation)"
    if (Test-Path $IconPath) {
        $sc2.IconLocation = "$IconPath,0"
    }
    $sc2.Save()
    Write-Output "Updated default Desktop shortcut: $origLnk"
}
