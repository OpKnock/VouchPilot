param(
    [string]$Version = "latest",
    [string]$InstallDir = "$env:LOCALAPPDATA\Programs\VouchPilot"
)

$ErrorActionPreference = "Stop"
$repo = "OpKnock/VouchPilot"
$asset = "VouchPilot-Windows.zip"
$downloadUrl = if ($Version -eq "latest") {
    "https://github.com/$repo/releases/latest/download/$asset"
} else {
    "https://github.com/$repo/releases/download/$Version/$asset"
}

$tmp = Join-Path $env:TEMP ("VouchPilot-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null
$zip = Join-Path $tmp $asset

try {
    Write-Host "Downloading VouchPilot..."
    Invoke-WebRequest -Uri $downloadUrl -OutFile $zip -UseBasicParsing

    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    Expand-Archive -Path $zip -DestinationPath $InstallDir -Force

    $exe = Join-Path $InstallDir "VouchPilot.exe"
    if (-not (Test-Path $exe)) {
        throw "VouchPilot.exe was not present in the downloaded package."
    }

    $shell = New-Object -ComObject WScript.Shell
    $desktop = [Environment]::GetFolderPath("Desktop")
    $shortcut = $shell.CreateShortcut((Join-Path $desktop "VouchPilot.lnk"))
    $shortcut.TargetPath = $exe
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.Description = "VouchPilot offline GST voucher intelligence"
    $shortcut.Save()

    Start-Process -FilePath $exe
    Write-Host "VouchPilot installed to $InstallDir"
} finally {
    if (Test-Path $tmp) {
        Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
