<#
.SYNOPSIS
AXIOM Desktop v6.8 — Windows Installer

.DESCRIPTION
Installs the AXIOM background daemon to the Windows Registry (HKCU\Software\Microsoft\Windows\CurrentVersion\Run)
so it starts silently on user login. Generates a Desktop shortcut for the GUI utilizing the AXIOM logo.
#>

$ErrorActionPreference = "Stop"

# ── Colors ──────────────────────────────────────────────────────
function Write-Info($msg)    { Write-Host "[INFO]  $msg" -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host "[ OK ]  $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "[WARN]  $msg" -ForegroundColor Yellow }
function Write-ErrorMsg($msg){ Write-Host "[FAIL]  $msg" -ForegroundColor Red }

# ── Banner ──────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan -NoNewline; Write-Host ""
Write-Host "  ║         AXIOM Desktop v6.8 — Windows Installer        ║" -ForegroundColor Cyan -NoNewline; Write-Host ""
Write-Host "  ║       Local-First AI Orchestration for Windows PC     ║" -ForegroundColor Cyan -NoNewline; Write-Host ""
Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan -NoNewline; Write-Host ""
Write-Host ""

# ── Preflight Checks ───────────────────────────────────────────
Write-Info "Running preflight checks..."

$axiomCmd = Get-Command "axiom" -ErrorAction SilentlyContinue
if (-not $axiomCmd) {
    Write-Warn "'axiom' command not found in PATH."
    Write-Warn "Ensure you have installed the package (pip install -e .) inside your virtual environment."
} else {
    Write-Success "Found 'axiom' executable."
}

# ── Step 1: Registry Auto-Start ────────────────────────────────
Write-Host ""
Write-Info "Step 1/2: Installing background daemon to Registry..."

$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$daemonCommand = "cmd.exe /c start /b axiom daemon start"

try {
    Set-ItemProperty -Path $regPath -Name "AxiomDaemon" -Value $daemonCommand
    Write-Success "Registry key added: HKCU\Software\Microsoft\Windows\CurrentVersion\Run\AxiomDaemon"
    
    # Start it right now so the user doesn't have to logout/login
    Write-Info "Starting AXIOM daemon in the background..."
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c start /b axiom daemon start" -WindowStyle Hidden
    Write-Success "AXIOM daemon started."
} catch {
    Write-ErrorMsg "Failed to add registry key: $_"
    exit 1
}

# ── Step 2: Desktop Shortcut ───────────────────────────────────
Write-Host ""
Write-Info "Step 2/2: Creating AXIOM Desktop shortcut..."

$WshShell = New-Object -comObject WScript.Shell
$desktopPath = [System.Environment]::GetFolderPath('Desktop')
$shortcutPath = Join-Path -Path $desktopPath -ChildPath "AXIOM.lnk"
$shortcut = $WshShell.CreateShortcut($shortcutPath)

# We want the shortcut to run the GUI
$shortcut.TargetPath = "axiom-gui"
$shortcut.WindowStyle = 1 # Normal window
$shortcut.Description = "AXIOM Local-First AI Orchestration Platform"

# Try to resolve icon
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$repoDir = Split-Path -Parent $scriptDir
$iconPath = Join-Path -Path $repoDir -ChildPath "axiom\gui\assets\logo.png"

# Windows shortcuts officially require .ico, but newer Windows versions can sometimes
# handle PNGs, or we just point to the executable if the PNG fails to render.
# For best results, we specify the PNG but gracefully fallback if it doesn't exist.
if (Test-Path $iconPath) {
    $shortcut.IconLocation = $iconPath
    Write-Success "Attached icon from $iconPath"
} else {
    Write-Warn "logo.png not found at $iconPath. Using default icon."
}

try {
    $shortcut.Save()
    Write-Success "Desktop shortcut created at $shortcutPath"
} catch {
    Write-ErrorMsg "Failed to create Desktop shortcut: $_"
}

# ── Summary ────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green -NoNewline; Write-Host ""
Write-Host "  ║            Installation Complete!                     ║" -ForegroundColor Green -NoNewline; Write-Host ""
Write-Host "  ╠═══════════════════════════════════════════════════════╣" -ForegroundColor Green -NoNewline; Write-Host ""
Write-Host "  ║  Daemon:   Runs automatically on Windows login        ║" -ForegroundColor Green -NoNewline; Write-Host ""
Write-Host "  ║  Logs:     Check Windows Event Viewer                 ║" -ForegroundColor Green -NoNewline; Write-Host ""
Write-Host "  ║  GUI:      Double-click the 'AXIOM' icon on Desktop   ║" -ForegroundColor Green -NoNewline; Write-Host ""
Write-Host "  ╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green -NoNewline; Write-Host ""
Write-Host ""
