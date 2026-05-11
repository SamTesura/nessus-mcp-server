# Nessus MCP Server - Docker Build Script
# Builds and configures the Docker container for Claude Desktop integration

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Nessus MCP Server - Docker Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
Write-Host "Checking Docker status..." -ForegroundColor Yellow
try {
    $dockerCheck = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Docker is not running. Please start Docker Desktop first." -ForegroundColor Red
        exit 1
    }
    Write-Host "Docker is running" -ForegroundColor Green
}
catch {
    Write-Host "Error: Docker is not installed or not accessible." -ForegroundColor Red
    exit 1
}

Write-Host ""

# Build the Docker image
Write-Host "Building Docker image..." -ForegroundColor Yellow
docker build -t nessus-mcp-server .

if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "Docker image built successfully" -ForegroundColor Green
Write-Host ""

# Check if image was created
$image = docker images nessus-mcp-server -q
if ($image) {
    Write-Host "Image ID: $image" -ForegroundColor Green
}
else {
    Write-Host "Image not found after build" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Make sure Nessus is running on your host" -ForegroundColor White
Write-Host "   - Nessus should be accessible at https://localhost:8834" -ForegroundColor White
Write-Host ""
Write-Host "2. Add to Claude Desktop config (claude_desktop_config.json):" -ForegroundColor White
Write-Host ""
Write-Host "{" -ForegroundColor Gray
Write-Host '  "mcpServers": {' -ForegroundColor Gray
Write-Host '    "nessus": {' -ForegroundColor Gray
Write-Host '      "command": "docker",' -ForegroundColor Gray
Write-Host '      "args": [' -ForegroundColor Gray
Write-Host '        "run",' -ForegroundColor Gray
Write-Host '        "--rm",' -ForegroundColor Gray
Write-Host '        "-i",' -ForegroundColor Gray
Write-Host '        "--add-host=host.docker.internal:host-gateway",' -ForegroundColor Gray
Write-Host '        "-v",' -ForegroundColor Gray
Write-Host '        "C:/Program Files/nessus_mcp_server:/app/config",' -ForegroundColor Gray
Write-Host '        "nessus-mcp-server"' -ForegroundColor Gray
Write-Host '      ]' -ForegroundColor Gray
Write-Host '    }' -ForegroundColor Gray
Write-Host '  }' -ForegroundColor Gray
Write-Host "}" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Update your nessus_mcp_config.json file:" -ForegroundColor White
Write-Host '   - Change "url" from "https://localhost:8834"' -ForegroundColor White
Write-Host '     to "https://host.docker.internal:8834"' -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Restart Claude Desktop" -ForegroundColor White
Write-Host ""
Write-Host "To test the setup, run:" -ForegroundColor Yellow
$testCommand = 'docker run --rm -i --add-host=host.docker.internal:host-gateway -v "C:/Program Files/nessus_mcp_server:/app/config" nessus-mcp-server'
Write-Host "  $testCommand" -ForegroundColor Cyan
Write-Host ""
