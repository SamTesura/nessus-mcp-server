# Nessus MCP Server - Docker Setup Checklist

## Pre-requisites ✓
- [ ] Docker Desktop installed and running
- [ ] Nessus Essentials installed and running on host
- [ ] Nessus accessible at https://localhost:8834
- [ ] Nessus API keys generated (Settings → API Keys)

## File Setup ✓
1. [ ] Project directory created: `C:\Program Files\nessus_mcp_server\`
2. [ ] All files copied to directory:
   - [ ] `Dockerfile`
   - [ ] `nessus_mcp_server.py`
   - [ ] `requirements.txt`
   - [ ] `build-docker.ps1` (corrected version)
3. [ ] Config file created: `config.json`
4. [ ] Config updated with correct URL: `https://host.docker.internal:8834`
5. [ ] API keys added to config.json

## Docker Build ✓
```powershell
cd "C:\Program Files\nessus_mcp_server"
.\build-docker.ps1
```

Expected output:
```
✓ Docker is running
✓ Docker image built successfully
✓ Image ID: <image-hash>
```

## Test Docker Connection ✓
```powershell
docker run --rm --add-host=host.docker.internal:host-gateway nessus-mcp-server sh -c "openssl s_client -connect host.docker.internal:8834 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"
```

Expected: one line such as `sha256 Fingerprint=AB:CD:...:EF`. That shows the container reaches Nessus. Copy the part after `=` into `tls_fingerprint` in your config: the server then trusts exactly this certificate. To double-check it, open https://localhost:8834 in your browser and compare the SHA-256 fingerprint in its certificate viewer.

## Claude Desktop Configuration ✓

1. [ ] Open: `%APPDATA%\Claude\claude_desktop_config.json`
2. [ ] Add MCP server config:

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

3. [ ] Save file
4. [ ] Validate JSON syntax (no errors)

## Restart Claude Desktop ✓
1. [ ] Completely quit Claude Desktop (File → Quit)
2. [ ] Reopen Claude Desktop
3. [ ] Wait for initialization (30-60 seconds)

## Verify Integration ✓

In Claude chat, test these commands:

1. [ ] Check Nessus connection:
   ```
   Can you check my Nessus server status?
   ```

2. [ ] List available scans:
   ```
   List my Nessus scans
   ```

3. [ ] Get scan policies:
   ```
   What scan policies are available in Nessus?
   ```

## Troubleshooting Checklist ✓

If tools not appearing:
- [ ] Check Claude Desktop logs: `%APPDATA%\Claude\logs\mcp*.log`
- [ ] Verify Docker image: `docker images | grep nessus-mcp-server`
- [ ] Test container manually (see Docker Build section)
- [ ] Verify config.json syntax and API keys
- [ ] Ensure Nessus is running: open https://localhost:8834 in browser

If connection errors:
- [ ] Verify URL in config.json: `https://host.docker.internal:8834`
- [ ] Check `tls_fingerprint` in config matches the fingerprint the Docker connection test prints
- [ ] Test host connectivity: `curl https://localhost:8834`
- [ ] Verify Docker host networking: `--add-host=host.docker.internal:host-gateway`

## Common Issues & Quick Fixes

### ❌ "localhost:8834 connection refused"
**Fix**: Change config URL to `https://host.docker.internal:8834`

### ❌ PowerShell syntax errors in build-docker.ps1
**Fix**: Use the corrected `build-docker.ps1` file provided

### ❌ "Config file not found"
**Fix**: Check volume mount path uses forward slashes: `C:/Program Files/...`

### ❌ "SSL certificate error"
**Fix**: Set `"tls_fingerprint"` in config.json to the fingerprint the Docker connection test prints (see [troubleshooting](troubleshooting.md#-problem-ssl-certificate-verify-failed)). Do not turn `verify_ssl` off: the API keys would then go to any server that answers.

### ❌ Tools not appearing in Claude
**Fix**: 
1. Check logs: `%APPDATA%\Claude\logs\mcp*.log`
2. Verify JSON syntax in claude_desktop_config.json
3. Restart Claude Desktop completely (File → Quit)
4. Wait 60 seconds after reopening

## Success Indicators ✅

You'll know it's working when:
- ✅ Claude recognizes Nessus-related commands
- ✅ Claude can list available scans
- ✅ Claude can create and launch scans
- ✅ Claude can generate vulnerability reports
- ✅ No error messages in Claude Desktop logs

## File Locations Reference

| Item | Path |
|------|------|
| Project directory | `C:\Program Files\nessus_mcp_server\` |
| Config file | `C:\Program Files\nessus_mcp_server\config.json` |
| Claude config | `%APPDATA%\Claude\claude_desktop_config.json` |
| Claude logs | `%APPDATA%\Claude\logs\` |
| Nessus interface | `https://localhost:8834` |

## Next Steps

Once verified working:
1. Run your first scan: "Run a basic network scan on 192.168.1.0/24"
2. Check vulnerabilities: "Show me critical vulnerabilities from my last scan"
3. Generate report: "Create a PDF report of scan results"
4. Explore workflows: "Run a complete scan and generate a summary report"

---

**Need Help?** See `DOCKER_TROUBLESHOOTING.md` for detailed troubleshooting guides.
