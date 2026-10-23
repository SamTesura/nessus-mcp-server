# Nessus MCP Server - Complete Installation Guide

## Required Files Checklist

Before building, make sure ALL these files are in `C:\Program Files\nessus_mcp_server\`:

### ✓ Core Files (REQUIRED)
- [ ] `nessus_mcp_server.py` - Main MCP server implementation
- [ ] `requirements.txt` - Python dependencies
- [ ] `Dockerfile` - Docker container configuration
- [ ] `nessus_mcp_config.json` - Your Nessus configuration with API keys

### ✓ Setup Files (OPTIONAL but helpful)
- [ ] `setup_nessus_mcp.py` - Configuration wizard
- [ ] `test_nessus_mcp.py` - Test suite
- [ ] `build-docker.ps1` - Build script

---

## Step-by-Step Installation

### Step 1: Create Directory Structure

```powershell
# Create main directory
New-Item -ItemType Directory -Force -Path "C:\Program Files\nessus_mcp_server"

# Navigate to directory
cd "C:\Program Files\nessus_mcp_server"
```

### Step 2: Download All Required Files

Download these files from Claude and place them in the directory:

1. **nessus_mcp_server.py** - The main server file
2. **Dockerfile** - The simplified Docker configuration
3. **requirements.txt** - Python dependencies
4. **nessus_mcp_config.json** - Pre-configured with your API keys (copy from `nessus_mcp_config.json.example`)

Optional files:
- **test_nessus_mcp.py** - For testing
- **setup_nessus_mcp.py** - Configuration wizard
- **build-docker.ps1** - Build automation

### Step 3: Verify Files Are Present

```powershell
# Check files exist
Get-ChildItem "C:\Program Files\nessus_mcp_server"
```

Expected output should show at minimum:
```
Dockerfile
nessus_mcp_server.py
requirements.txt
nessus_mcp_config.json
```

### Step 4: Build Docker Image

```powershell
# Navigate to directory
cd "C:\Program Files\nessus_mcp_server"

# Build the image
docker build --pull -t nessus-mcp-server .
```

`--pull` fetches the current `python:3.11-slim`, so the image gets the base's latest CA certificates. Rebuild this way after any CA-trust fix, such as the October 2026 eMudhra compromise; an image built earlier keeps the old trust store.

Expected output:
```
[+] Building X.Xs (10/10) FINISHED
Successfully built <image-id>
Successfully tagged nessus-mcp-server:latest
```

### Step 5: Test Docker Image

```powershell
# Test connectivity and print the Nessus certificate fingerprint
docker run --rm --add-host=host.docker.internal:host-gateway nessus-mcp-server sh -c "openssl s_client -connect host.docker.internal:8834 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"
```

Expected: one line such as `sha256 Fingerprint=AB:CD:...:EF`. That shows the container reaches Nessus. Copy the part after `=` into `tls_fingerprint` in your config: the server then trusts exactly this certificate. To double-check it, open https://localhost:8834 in your browser and compare the SHA-256 fingerprint in its certificate viewer.

### Step 6: Configure Claude Desktop

Edit: `%APPDATA%\Claude\claude_desktop_config.json`

Add this configuration:

```json
{
  "mcpServers": {
    "nessus": {
      "command": "docker",
      "args": [
        "run",
        "--rm",
        "-i",
        "--add-host=host.docker.internal:host-gateway",
        "-v",
        "C:/Program Files/nessus_mcp_server:/app/config",
        "nessus-mcp-server"
      ]
    }
  }
}
```

**Important**: If you already have other MCP servers, add the "nessus" section inside the existing "mcpServers" object.

> The Dockerfile bakes in `NESSUS_CONFIG_PATH=/app/config/nessus_mcp_config.json`. If you mount your config at a different path or filename, override it via `-e NESSUS_CONFIG_PATH=/your/path/your_file.json` in the args.

### Step 7: Restart Claude Desktop

1. Quit Claude Desktop completely (File → Quit)
2. Wait 5 seconds
3. Reopen Claude Desktop
4. Wait 30-60 seconds for MCP servers to initialize

### Step 8: Verify Integration

In Claude chat, try these commands:

```
Can you check my Nessus server status?
```

```
List my Nessus scans
```

```
What scan policies are available?
```

---

## Quick Reference: File Contents

### Minimal File Structure
```
C:\Program Files\nessus_mcp_server\
├── Dockerfile                       (Docker build instructions)
├── nessus_mcp_server.py             (MCP server code)
├── requirements.txt                 (Python dependencies)
└── nessus_mcp_config.json           (Your API keys and settings)
```

### Complete File Structure
```
C:\Program Files\nessus_mcp_server\
├── Dockerfile
├── nessus_mcp_server.py
├── requirements.txt
├── nessus_mcp_config.json
├── setup_nessus_mcp.py              (Setup wizard)
├── test_nessus_mcp.py               (Test suite)
└── build-docker.ps1                 (Build script)
```

---

## Troubleshooting Build Errors

### Error: "test_nessus_mcp.py: not found"
**Solution**: Use the simplified Dockerfile provided (it doesn't require test file)

### Error: "nessus_mcp_server.py: not found"
**Solution**: Make sure nessus_mcp_server.py is in the build directory

### Error: "Configuration file not found. Please create nessus_mcp_config.json"
**Solution**: Place `nessus_mcp_config.json` in the directory mounted to `/app/config` inside the container (default install: `C:\Program Files\nessus_mcp_server\`). The Python server reads `NESSUS_CONFIG_PATH` (set by the Dockerfile to `/app/config/nessus_mcp_config.json`) and falls back to `~/.config/nessus-mcp/config.json` or `./nessus_mcp_config.json`.

### Error: "COPY failed"
**Solution**: Verify you're running `docker build` from the directory containing all files

### Error: "Permission denied"
**Solution**: Run PowerShell as Administrator

---

## One-Command Setup (If all files are downloaded)

```powershell
# Run as Administrator
cd "C:\Program Files\nessus_mcp_server"

# Create config (if not downloaded)
@'
{
  "url": "https://host.docker.internal:8834",
  "access_key": "YOUR_KEY_HERE",
  "secret_key": "YOUR_KEY_HERE",
  "tls_fingerprint": "PASTE_THE_NESSUS_CERTIFICATE_SHA256_FINGERPRINT",
  "scan_defaults": {
    "policy_id": null,
    "folder_id": null,
    "scanner_id": null
  },
  "export_defaults": {
    "format": "pdf",
    "chapters": "vuln_hosts_summary"
  },
  "workflow_defaults": {
    "auto_launch": true,
    "auto_export": true,
    "cleanup_on_complete": false,
    "poll_interval": 15
  }
}
'@ | Out-File "nessus_mcp_config.json" -Encoding utf8

# Build
docker build --pull -t nessus-mcp-server .

# Test connectivity and print the fingerprint to paste into tls_fingerprint
docker run --rm --add-host=host.docker.internal:host-gateway nessus-mcp-server sh -c "openssl s_client -connect host.docker.internal:8834 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"
```

---

## Testing Without Docker (Alternative)

If Docker continues to cause issues, you can run the server directly:

```powershell
# Install dependencies
pip install requests mcp

# Update nessus_mcp_config.json to use localhost
# Change "url" to "https://localhost:8834"

# Add to Claude Desktop config:
{
  "mcpServers": {
    "nessus": {
      "command": "python",
      "args": ["C:/Program Files/nessus_mcp_server/nessus_mcp_server.py"],
      "env": {
        "NESSUS_CONFIG_PATH": "C:/Program Files/nessus_mcp_server/nessus_mcp_config.json"
      }
    }
  }
}
```

---

## Verification Checklist

Before contacting support, verify:

- [ ] All 4 required files exist in the directory
- [ ] `nessus_mcp_config.json` has correct API keys
- [ ] `nessus_mcp_config.json` uses `"url": "https://host.docker.internal:8834"` (not `nessus_url`)
- [ ] Docker Desktop is running
- [ ] Nessus is running at https://localhost:8834
- [ ] Docker build completes without errors
- [ ] The Docker connection test prints a `sha256 Fingerprint=` line, and `tls_fingerprint` in your config matches it
- [ ] Claude Desktop config has correct JSON syntax
- [ ] Claude Desktop was fully restarted (quit and reopen)

---

## Success Indicators

You'll know it's working when:
- ✅ `docker build` completes successfully
- ✅ The Docker connection test prints the Nessus certificate fingerprint
- ✅ Claude recognizes Nessus commands
- ✅ Claude can list scans and policies
- ✅ No errors in `%APPDATA%\Claude\logs\mcp*.log`

## Next Steps After Setup

Once working, try:
1. Create a scan: "Create a basic network scan for 192.168.1.0/24"
2. Check results: "Show me vulnerabilities from my latest scan"
3. Generate report: "Create a PDF report of critical vulnerabilities"
4. Run workflow: "Run a full scan on 10.0.0.1 and summarize findings"
