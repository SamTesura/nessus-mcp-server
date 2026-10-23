# ============================================================
# FASTEST FIX - Copy and Paste These Commands
# ============================================================
# Run in PowerShell AS ADMINISTRATOR
# ============================================================

# 1. Create the config file directly (one command)
@'
{
  "nessus_url": "https://host.docker.internal:8834",
  "access_key": "YOUR KEY",
  "secret_key": "YOUR KEY",
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
'@ | Out-File "C:\Program Files\nessus_mcp_server\config.json" -Encoding utf8

# 2. Build Docker image (fixed build script)
cd "C:\Program Files\nessus_mcp_server"
docker build --pull -t nessus-mcp-server .

# 3. Test Docker connectivity and get the Nessus certificate fingerprint
docker run --rm --add-host=host.docker.internal:host-gateway nessus-mcp-server sh -c "openssl s_client -connect host.docker.internal:8834 </dev/null 2>/dev/null | openssl x509 -noout -fingerprint -sha256"

# ============================================================
# Expected output: sha256 Fingerprint=AB:CD:...:EF
# Paste the part after "=" into "tls_fingerprint" in config.json.
# ============================================================

# 4. Add to Claude Desktop config
# Location: %APPDATA%\Claude\claude_desktop_config.json
# 
# Add this inside "mcpServers": { }
#
# "nessus": {
#   "command": "docker",
#   "args": [
#     "run",
#     "--rm",
#     "-i",
#     "--add-host=host.docker.internal:host-gateway",
#     "-v",
#     "C:/Program Files/nessus_mcp_server:/app/config",
#     "nessus-mcp-server"
#   ]
# }

# 5. Restart Claude Desktop completely (File > Quit, then reopen)

# ============================================================
# DONE! Test in Claude: "List my Nessus scans"
# ============================================================
