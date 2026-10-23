# Nessus MCP Server - Docker Troubleshooting Guide

## Docker Networking Issues

### ❌ Problem: "Connection refused" or "Cannot connect to Nessus"

**Cause**: Docker container using `localhost:8834` instead of Docker host network.

**Solution**:
1. Update your `config.json`:
   ```json
   "nessus_url": "https://host.docker.internal:8834"
   ```

2. Make sure the `--add-host=host.docker.internal:host-gateway` flag is in your Docker run command

3. Verify Nessus is running on your host:
   ```powershell
   curl https://localhost:8834
   ```

### ❌ Problem: "SSL Certificate Verify Failed"

Nessus serves a self-signed certificate issued to your computer's name, so it neither chains to a public CA nor matches `host.docker.internal`, and normal verification fails.

**Solution**: Pin that certificate. Print its SHA-256 fingerprint from the container:

```powershell
docker run --rm --add-host=host.docker.internal:host-gateway nessus-mcp-server sh -c "openssl s_client -connect host.docker.internal:8834 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"
```

Copy the part after `=` into your config:

```json
{
  "url": "https://host.docker.internal:8834",
  "tls_fingerprint": "AB:CD:...:EF"
}
```

The server then trusts exactly this certificate and nothing else. Compare the fingerprint once with the one your browser shows for https://localhost:8834. If Nessus later regenerates its certificate, the connection fails until you repeat this.

Do not set `verify_ssl` to `false` instead: the API keys would then go, unverified, to whatever answers on that address. (`verify_ssl` also accepts the path of a CA bundle, for a Nessus certificate issued by your own CA; that certificate must then also name `host.docker.internal`, or the hostname check fails.)

### ❌ Problem: "Config file not found"

**Cause**: Volume mount path incorrect or file doesn't exist.

**Solution**:
1. Make sure config.json exists at: `C:\Program Files\nessus_mcp_server\config.json`

2. Check volume mount in claude_desktop_config.json:
   ```json
   "-v",
   "C:/Program Files/nessus_mcp_server:/app/config",
   ```

3. Note: Use forward slashes (/) in Docker volume paths, even on Windows

### ❌ Problem: PowerShell syntax errors in build-docker.ps1

**Symptoms**:
- "Missing Catch or Finally block"
- "Missing string terminator"
- "Missing closing '}'"

**Solution**: Use the corrected build-docker.ps1 provided. The original had:
- Incomplete try-catch blocks
- Unclosed strings
- Missing braces

## Common Setup Issues

### Issue: Claude Desktop not detecting the MCP server

**Checklist**:
1. ✓ Docker image built: `docker images | grep nessus-mcp-server`
2. ✓ Config added to claude_desktop_config.json
3. ✓ Config file syntax valid (use JSON validator)
4. ✓ Claude Desktop restarted
5. ✓ Logs checked: `%APPDATA%\Claude\logs\mcp*.log`

### Issue: "Permission denied" errors

**Windows Solution**:
```powershell
# Run PowerShell as Administrator
icacls "C:\Program Files\nessus_mcp_server" /grant Everyone:F
```

**Check file permissions**:
```powershell
Get-Acl "C:\Program Files\nessus_mcp_server\config.json"
```

### Issue: Docker build fails

**Common causes**:
1. Docker Desktop not running
2. Internet connection issues (can't download base image)
3. Dockerfile not in current directory

**Solution**:
```powershell
# 1. Start Docker Desktop
# 2. Navigate to project directory
cd "C:\Program Files\nessus_mcp_server"

# 3. Verify Dockerfile exists
ls Dockerfile

# 4. Rebuild with no cache
docker build --pull --no-cache -t nessus-mcp-server .
```

## Testing Commands

### Test Docker image directly:
```powershell
docker run --rm -i `
  --add-host=host.docker.internal:host-gateway `
  -v "C:/Program Files/nessus_mcp_server:/app/config" `
  nessus-mcp-server
```

### Test Nessus connectivity from Docker:
```powershell
docker run --rm -it `
  --add-host=host.docker.internal:host-gateway `
  nessus-mcp-server `
  sh -c "openssl s_client -connect host.docker.internal:8834 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"
```

### Inspect container logs:
```powershell
# If container is running
docker logs <container-id>

# Or run with output
docker run --rm `
  --add-host=host.docker.internal:host-gateway `
  -v "C:/Program Files/nessus_mcp_server:/app/config" `
  nessus-mcp-server 2>&1
```

## Network Configuration Reference

### Correct URL formats:

| Environment | Nessus URL |
|-------------|-----------|
| Docker container | `https://host.docker.internal:8834` |
| Host machine | `https://localhost:8834` |
| Remote Nessus | `https://nessus.example.com:8834` |

### Docker run command anatomy:

```powershell
docker run \
  --rm \                                           # Remove container after exit
  -i \                                             # Interactive mode (for MCP)
  --add-host=host.docker.internal:host-gateway \  # Enable host network access
  -v "C:/Program Files/nessus_mcp_server:/app/config" \  # Mount config directory
  nessus-mcp-server                                # Image name
```

## Quick Fixes

### Reset everything:
```powershell
# 1. Remove Docker image
docker rmi nessus-mcp-server

# 2. Rebuild
cd "C:\Program Files\nessus_mcp_server"
.\build-docker.ps1

# 3. Test connection (prints the certificate fingerprint)
docker run --rm --add-host=host.docker.internal:host-gateway nessus-mcp-server sh -c "openssl s_client -connect host.docker.internal:8834 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"
```

### Verify Claude Desktop config:
```powershell
# View config
cat "$env:APPDATA\Claude\claude_desktop_config.json"

# Validate JSON syntax
python -m json.tool "$env:APPDATA\Claude\claude_desktop_config.json"
```

### Check Nessus API keys:
```powershell
# Uses the server's own client, so the certificate is checked exactly as in production
docker run --rm --add-host=host.docker.internal:host-gateway -v "C:/Program Files/nessus_mcp_server:/app/config" nessus-mcp-server python -c "import json; from nessus_mcp_server import NessusClient as C; c=json.load(open('/app/config/nessus_mcp_config.json')); n=C(c['url'], c['access_key'], c['secret_key'], c.get('verify_ssl', True), c.get('tls_fingerprint')); print(len(n.list_scans() or []), 'scans visible: keys and certificate OK')"
```

## Still Having Issues?

1. **Check Nessus logs**: See if API requests are reaching Nessus
2. **Check Docker logs**: `docker logs <container-id>`
3. **Check Claude logs**: `%APPDATA%\Claude\logs\`
4. **Verify ports**: `netstat -ano | findstr 8834`
5. **Test without Docker**: Try the standalone Python version to isolate Docker issues

## Alternative: Non-Docker Setup

If Docker continues to cause issues, use the standalone version:

1. Install dependencies:
   ```powershell
   pip install requests
   ```

2. Use localhost URL in config:
   ```json
   "nessus_url": "https://localhost:8834"
   ```

3. Add to claude_desktop_config.json:
   ```json
   "nessus": {
     "command": "python",
     "args": ["C:/Program Files/nessus_mcp_server/nessus_mcp_server.py"]
   }
   ```
