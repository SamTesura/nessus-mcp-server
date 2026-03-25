# Nessus MCP Server - Automated File Deployment
# Copies all required files to the installation directory
# Run as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Nessus MCP Server - File Deployment" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$destDir = "C:\Program Files\nessus_mcp_server"

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator" -ForegroundColor Red
    Write-Host ""
    Write-Host "To run as Administrator:" -ForegroundColor Yellow
    Write-Host "1. Right-click PowerShell" -ForegroundColor White
    Write-Host "2. Select 'Run as Administrator'" -ForegroundColor White
    Write-Host "3. Run this script again" -ForegroundColor White
    Write-Host ""
    pause
    exit 1
}

Write-Host "Creating directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $destDir | Out-Null
Write-Host "Created: $destDir" -ForegroundColor Green
Write-Host ""

# List of files to check
$requiredFiles = @(
    "nessus_mcp_server.py",
    "requirements.txt",
    "Dockerfile",
    "config.json"
)

$optionalFiles = @(
    "test_nessus_mcp.py",
    "setup_nessus_mcp.py",
    "build-docker.ps1"
)

# Check current directory for files
Write-Host "Checking for files in current directory..." -ForegroundColor Yellow
$currentDir = Get-Location

$foundFiles = @()
$missingFiles = @()

foreach ($file in $requiredFiles) {
    $filePath = Join-Path $currentDir $file
    if (Test-Path $filePath) {
        Write-Host "  Found: $file" -ForegroundColor Green
        $foundFiles += $file
    } else {
        Write-Host "  Missing: $file" -ForegroundColor Red
        $missingFiles += $file
    }
}

Write-Host ""

if ($missingFiles.Count -gt 0) {
    Write-Host "ERROR: Missing required files!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Missing files:" -ForegroundColor Yellow
    foreach ($file in $missingFiles) {
        Write-Host "  - $file" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Please download all required files first." -ForegroundColor Yellow
    Write-Host "Files should be in the same directory as this script." -ForegroundColor Yellow
    Write-Host ""
    pause
    exit 1
}

# Copy files
Write-Host "Copying files to installation directory..." -ForegroundColor Yellow
Write-Host ""

foreach ($file in ($requiredFiles + $optionalFiles)) {
    $sourcePath = Join-Path $currentDir $file
    $destPath = Join-Path $destDir $file
    
    if (Test-Path $sourcePath) {
        try {
            Copy-Item $sourcePath $destPath -Force
            Write-Host "  Copied: $file" -ForegroundColor Green
        } catch {
            Write-Host "  Failed to copy: $file" -ForegroundColor Red
            Write-Host "    Error: $_" -ForegroundColor Red
        }
    }
}

Write-Host ""

# Verify files in destination
Write-Host "Verifying installation..." -ForegroundColor Yellow
$allFilesPresent = $true

foreach ($file in $requiredFiles) {
    $filePath = Join-Path $destDir $file
    if (Test-Path $filePath) {
        Write-Host "  OK: $file" -ForegroundColor Green
    } else {
        Write-Host "  MISSING: $file" -ForegroundColor Red
        $allFilesPresent = $false
    }
}

Write-Host ""

if ($allFilesPresent) {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Installation Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "All files copied successfully to:" -ForegroundColor Green
    Write-Host "  $destDir" -ForegroundColor White
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Yellow
    Write-Host "1. Build Docker image:" -ForegroundColor White
    Write-Host "   cd '$destDir'" -ForegroundColor Gray
    Write-Host "   docker build -t nessus-mcp-server ." -ForegroundColor Gray
    Write-Host ""
    Write-Host "2. Configure Claude Desktop" -ForegroundColor White
    Write-Host "   See COMPLETE_INSTALLATION_GUIDE.md for details" -ForegroundColor Gray
    Write-Host ""
    Write-Host "3. Restart Claude Desktop" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  Installation Failed!" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Some files were not copied successfully." -ForegroundColor Red
    Write-Host "Please check the errors above and try again." -ForegroundColor Yellow
    Write-Host ""
}

pause
