#!/usr/bin/env python3
"""
Tenable Nessus MCP Server
Model Context Protocol server for vulnerability scanning with Nessus
"""

import json
import asyncio
import logging
import re
import time
import os
from typing import Any, Dict, List, Optional, Union
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from mcp.server import Server
from mcp.types import Tool, TextContent, ImageContent, EmbeddedResource

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nessus-mcp")


def normalize_fingerprint(value: str) -> str:
    """Return a SHA-256 certificate fingerprint as 64 lowercase hex digits."""
    fingerprint = value.replace(':', '').replace(' ', '').lower()
    if not re.fullmatch(r'[0-9a-f]{64}', fingerprint):
        raise ValueError(
            "tls_fingerprint must be the SHA-256 fingerprint of the Nessus server "
            "certificate: 64 hex digits, colons optional (see docs/troubleshooting.md)"
        )
    return fingerprint


class PinnedCertAdapter(HTTPAdapter):
    """Trust exactly one server certificate, identified by its SHA-256 fingerprint.

    Nessus serves a self-signed certificate issued to the scanner host, so it neither
    chains to a public CA nor matches host.docker.internal. Pinning its fingerprint
    authenticates that one server without either check: urllib3 refuses any other
    certificate, so the CA and hostname checks it replaces are switched off here.
    """

    def __init__(self, fingerprint: str, **kwargs):
        self._fingerprint = fingerprint
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['assert_fingerprint'] = self._fingerprint
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['assert_fingerprint'] = self._fingerprint
        return super().proxy_manager_for(*args, **kwargs)

    def send(self, request, **kwargs):
        # Otherwise requests swaps in REQUESTS_CA_BUNDLE, if set, and the CA check
        # rejects the self-signed certificate before the pin is compared.
        kwargs['verify'] = False
        return super().send(request, **kwargs)


class NessusClient:
    """Client for interacting with Nessus API"""

    def __init__(self, url: str, access_key: str, secret_key: str,
                 verify_ssl: Union[bool, str] = True, tls_fingerprint: Optional[str] = None):
        self.url = url.rstrip('/')
        self.access_key = access_key
        self.secret_key = secret_key
        self.verify_ssl = verify_ssl
        self.headers = {
            'X-ApiKeys': f'accessKey={access_key}; secretKey={secret_key}',
            'Content-Type': 'application/json'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        if tls_fingerprint:
            self.session.mount('https://', PinnedCertAdapter(normalize_fingerprint(tls_fingerprint)))
        else:
            # True: public CAs. A path: that CA bundle. False: no check at all.
            self.session.verify = verify_ssl
            if verify_ssl is False:
                logger.warning(
                    "verify_ssl is false: the Nessus API keys are sent without checking the "
                    "server's certificate. Set tls_fingerprint instead (see docs/troubleshooting.md)."
                )
    
    def _request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make API request"""
        url = f"{self.url}{endpoint}"
        
        try:
            if method == 'GET':
                response = self.session.get(url)
            elif method == 'POST':
                response = self.session.post(url, json=data)
            elif method == 'PUT':
                response = self.session.put(url, json=data)
            elif method == 'DELETE':
                response = self.session.delete(url)
            
            response.raise_for_status()
            return response.json() if response.text else {}
        
        except requests.exceptions.RequestException as e:
            error_msg = f"API Error: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" - {error_detail}"
                except:
                    error_msg += f" - {e.response.text}"
            raise Exception(error_msg)
    
    # Server Information
    def get_server_properties(self) -> Dict:
        return self._request('GET', '/server/properties')
    
    def get_server_status(self) -> Dict:
        return self._request('GET', '/server/status')
    
    # Scan Management
    def list_scans(self) -> List[Dict]:
        response = self._request('GET', '/scans')
        return response.get('scans', [])
    
    def get_scan_details(self, scan_id: int) -> Dict:
        return self._request('GET', f'/scans/{scan_id}')
    
    def create_scan(self, name: str, targets: str, template: str = 'basic') -> Dict:
        templates = self.list_templates()
        template_uuid = None
        
        for tmpl in templates:
            if template.lower() in tmpl['name'].lower():
                template_uuid = tmpl['uuid']
                break
        
        if not template_uuid:
            template_uuid = templates[0]['uuid'] if templates else None
        
        data = {
            'uuid': template_uuid,
            'settings': {
                'name': name,
                'text_targets': targets,
                'enabled': True
            }
        }
        
        return self._request('POST', '/scans', data)
    
    def launch_scan(self, scan_id: int) -> Dict:
        return self._request('POST', f'/scans/{scan_id}/launch')
    
    def stop_scan(self, scan_id: int) -> Dict:
        return self._request('POST', f'/scans/{scan_id}/stop')
    
    def pause_scan(self, scan_id: int) -> Dict:
        return self._request('POST', f'/scans/{scan_id}/pause')
    
    def resume_scan(self, scan_id: int) -> Dict:
        return self._request('POST', f'/scans/{scan_id}/resume')
    
    def delete_scan(self, scan_id: int) -> Dict:
        return self._request('DELETE', f'/scans/{scan_id}')
    
    # Templates & Policies
    def list_templates(self) -> List[Dict]:
        response = self._request('GET', '/editor/scan/templates')
        return response.get('templates', [])
    
    def list_policies(self) -> List[Dict]:
        response = self._request('GET', '/policies')
        return response.get('policies', [])
    
    # Vulnerabilities
    def get_vulnerabilities(self, scan_id: int, history_id: Optional[int] = None) -> List[Dict]:
        endpoint = f'/scans/{scan_id}'
        if history_id:
            endpoint += f'?history_id={history_id}'
        
        response = self._request('GET', endpoint)
        return response.get('vulnerabilities', [])
    
    def get_vulnerability_details(self, scan_id: int, plugin_id: int, history_id: Optional[int] = None) -> Dict:
        endpoint = f'/scans/{scan_id}/plugins/{plugin_id}'
        if history_id:
            endpoint += f'?history_id={history_id}'
        
        return self._request('GET', endpoint)
    
    def get_host_vulnerabilities(self, scan_id: int, host_id: int, history_id: Optional[int] = None) -> Dict:
        endpoint = f'/scans/{scan_id}/hosts/{host_id}'
        if history_id:
            endpoint += f'?history_id={history_id}'
        
        return self._request('GET', endpoint)
    
    # Export
    def export_scan(self, scan_id: int, format: str = 'pdf', history_id: Optional[int] = None) -> int:
        data = {'format': format}
        if history_id:
            data['history_id'] = history_id
        
        response = self._request('POST', f'/scans/{scan_id}/export', data)
        return response.get('file')
    
    def get_export_status(self, scan_id: int, file_id: int) -> str:
        response = self._request('GET', f'/scans/{scan_id}/export/{file_id}/status')
        return response.get('status')
    
    def download_export(self, scan_id: int, file_id: int) -> bytes:
        url = f"{self.url}/scans/{scan_id}/export/{file_id}/download"
        response = self.session.get(url)
        response.raise_for_status()
        return response.content
    
    # Helper Methods
    def wait_for_scan(self, scan_id: int, poll_interval: int = 10, timeout: int = 3600) -> str:
        """Wait for scan to complete"""
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Scan {scan_id} exceeded timeout of {timeout} seconds")
            
            details = self.get_scan_details(scan_id)
            status = details.get('info', {}).get('status')
            
            if status in ['completed', 'canceled', 'aborted']:
                return status
            
            time.sleep(poll_interval)
    
    def wait_for_export(self, scan_id: int, file_id: int, timeout: int = 300) -> bool:
        """Wait for export to be ready"""
        start_time = time.time()
        
        while True:
            if time.time() - start_time > timeout:
                return False
            
            status = self.get_export_status(scan_id, file_id)
            if status == 'ready':
                return True
            
            time.sleep(2)


class NessusMCPServer:
    """MCP Server for Nessus"""
    
    def __init__(self):
        self.server = Server("nessus-mcp")
        self.nessus: Optional[NessusClient] = None
        self.config: Dict[str, Any] = {}
        self.output_dir = Path.home() / "nessus_reports"
        
        # Register handlers
        self.server.list_tools = self.list_tools
        self.server.call_tool = self.call_tool
        
        # Load configuration
        self.load_config()
        
        # Create output directory
        self.output_dir.mkdir(exist_ok=True)
    
    def load_config(self):
        """Load configuration from file"""
        # Check for environment variable first (Docker support)
        config_path_env = os.environ.get('NESSUS_CONFIG_PATH')
        
        if config_path_env:
            config_paths = [Path(config_path_env)]
        else:
            config_paths = [
                Path.home() / ".config" / "nessus-mcp" / "config.json",
                Path("nessus_mcp_config.json"),
            ]
        
        for config_path in config_paths:
            if config_path.exists():
                with open(config_path) as f:
                    self.config = json.load(f)
                logger.info(f"Loaded configuration from {config_path}")
                break
        else:
            raise FileNotFoundError(
                "Configuration file not found. Please create nessus_mcp_config.json"
            )
        
        # Initialize Nessus client
        self.nessus = NessusClient(
            url=self.config.get('url', 'https://localhost:8834'),
            access_key=self.config['access_key'],
            secret_key=self.config['secret_key'],
            verify_ssl=self.config.get('verify_ssl', True),
            tls_fingerprint=self.config.get('tls_fingerprint')
        )
        
        # Test connection
        try:
            props = self.nessus.get_server_properties()
            version = props.get('nessus_version') or 'unknown'
            logger.info(f"Connected to Nessus (version: {version})")
        except Exception as e:
            logger.error(f"Failed to connect to Nessus: {e}")
            raise
    
    async def list_tools(self) -> List[Tool]:
        """List available MCP tools"""
        return [
            # Server Information
            Tool(
                name="get_server_info",
                description="Get Nessus server information including version and status",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            # Scan Management
            Tool(
                name="list_scans",
                description="List all vulnerability scans with their status and details",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="get_scan_details",
                description="Get detailed information about a specific scan including hosts and vulnerabilities",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            Tool(
                name="create_scan",
                description="Create a new vulnerability scan with specified targets and template",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the scan"
                        },
                        "targets": {
                            "type": "string",
                            "description": "Target IPs or hostnames (comma-separated or CIDR notation)"
                        },
                        "template": {
                            "type": "string",
                            "description": "Scan template (basic, discovery, advanced, etc.)",
                            "default": "basic"
                        }
                    },
                    "required": ["name", "targets"]
                }
            ),
            Tool(
                name="launch_scan",
                description="Start a scan that has been created",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID to launch"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            Tool(
                name="get_scan_status",
                description="Check the current status of a scan (running, completed, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            Tool(
                name="stop_scan",
                description="Stop a currently running scan",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID to stop"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            Tool(
                name="pause_scan",
                description="Pause a currently running scan",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID to pause"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            Tool(
                name="resume_scan",
                description="Resume a paused scan",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID to resume"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            Tool(
                name="delete_scan",
                description="Delete a scan from Nessus",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID to delete"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            
            # Templates & Policies
            Tool(
                name="list_templates",
                description="List available scan templates (basic, advanced, discovery, etc.)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            Tool(
                name="list_policies",
                description="List custom scan policies",
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            ),
            
            # Vulnerabilities
            Tool(
                name="get_vulnerabilities",
                description="Get list of vulnerabilities from a completed scan with severity filtering",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID"
                        },
                        "min_severity": {
                            "type": "string",
                            "description": "Minimum severity to include (info, low, medium, high, critical)",
                            "enum": ["info", "low", "medium", "high", "critical"],
                            "default": "info"
                        },
                        "include_remediation": {
                            "type": "boolean",
                            "description": "Include remediation recommendations",
                            "default": True
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            Tool(
                name="get_vulnerability_details",
                description="Get detailed information about a specific vulnerability including remediation steps",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID"
                        },
                        "plugin_id": {
                            "type": "integer",
                            "description": "The vulnerability plugin ID"
                        }
                    },
                    "required": ["scan_id", "plugin_id"]
                }
            ),
            Tool(
                name="get_host_vulnerabilities",
                description="Get all vulnerabilities for a specific host",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID"
                        },
                        "host_id": {
                            "type": "integer",
                            "description": "The host ID"
                        }
                    },
                    "required": ["scan_id", "host_id"]
                }
            ),
            
            # Export
            Tool(
                name="export_scan",
                description="Export scan results to PDF, HTML, CSV, or Nessus format and save to local filesystem",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scan_id": {
                            "type": "integer",
                            "description": "The scan ID to export"
                        },
                        "format": {
                            "type": "string",
                            "description": "Export format",
                            "enum": ["pdf", "html", "csv", "nessus"],
                            "default": "pdf"
                        },
                        "filename": {
                            "type": "string",
                            "description": "Optional custom filename (without extension)"
                        }
                    },
                    "required": ["scan_id"]
                }
            ),
            
            # Workflow Tools
            Tool(
                name="scan_workflow",
                description="Complete scan workflow: create scan, launch it, wait for completion, and return summarized results with critical/high vulnerabilities",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name for the scan"
                        },
                        "targets": {
                            "type": "string",
                            "description": "Target IPs or hostnames"
                        },
                        "template": {
                            "type": "string",
                            "description": "Scan template",
                            "default": "basic"
                        },
                        "export_format": {
                            "type": "string",
                            "description": "Format to export results",
                            "enum": ["pdf", "html", "csv", "nessus", "none"],
                            "default": "pdf"
                        }
                    },
                    "required": ["name", "targets"]
                }
            ),
            Tool(
                name="quick_scan",
                description="Fast host discovery scan to quickly identify active hosts and open ports",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "targets": {
                            "type": "string",
                            "description": "Target IPs or hostnames"
                        }
                    },
                    "required": ["targets"]
                }
            ),
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Call a specific tool"""
        try:
            if name == "get_server_info":
                return await self._get_server_info()
            elif name == "list_scans":
                return await self._list_scans()
            elif name == "get_scan_details":
                return await self._get_scan_details(arguments['scan_id'])
            elif name == "create_scan":
                return await self._create_scan(
                    arguments['name'],
                    arguments['targets'],
                    arguments.get('template', 'basic')
                )
            elif name == "launch_scan":
                return await self._launch_scan(arguments['scan_id'])
            elif name == "get_scan_status":
                return await self._get_scan_status(arguments['scan_id'])
            elif name == "stop_scan":
                return await self._stop_scan(arguments['scan_id'])
            elif name == "pause_scan":
                return await self._pause_scan(arguments['scan_id'])
            elif name == "resume_scan":
                return await self._resume_scan(arguments['scan_id'])
            elif name == "delete_scan":
                return await self._delete_scan(arguments['scan_id'])
            elif name == "list_templates":
                return await self._list_templates()
            elif name == "list_policies":
                return await self._list_policies()
            elif name == "get_vulnerabilities":
                return await self._get_vulnerabilities(
                    arguments['scan_id'],
                    arguments.get('min_severity', 'info'),
                    arguments.get('include_remediation', True)
                )
            elif name == "get_vulnerability_details":
                return await self._get_vulnerability_details(
                    arguments['scan_id'],
                    arguments['plugin_id']
                )
            elif name == "get_host_vulnerabilities":
                return await self._get_host_vulnerabilities(
                    arguments['scan_id'],
                    arguments['host_id']
                )
            elif name == "export_scan":
                return await self._export_scan(
                    arguments['scan_id'],
                    arguments.get('format', 'pdf'),
                    arguments.get('filename')
                )
            elif name == "scan_workflow":
                return await self._scan_workflow(
                    arguments['name'],
                    arguments['targets'],
                    arguments.get('template', 'basic'),
                    arguments.get('export_format', 'pdf')
                )
            elif name == "quick_scan":
                return await self._quick_scan(arguments['targets'])
            else:
                raise ValueError(f"Unknown tool: {name}")
        
        except Exception as e:
            logger.error(f"Error calling tool {name}: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    # Tool Implementations
    async def _get_server_info(self) -> List[TextContent]:
        props = self.nessus.get_server_properties()
        status = self.nessus.get_server_status()
        
        info = f"""## Nessus Server Information

**Version:** {props.get('nessus_version')}
**Server Type:** {props.get('server_version')}
**Status:** {status.get('status')}
**Scanner UUID:** {props.get('scanner_uuid')}

**Capabilities:**
- Web Server: {props.get('capabilities', {}).get('webserver', 'Unknown')}
- Update: {props.get('capabilities', {}).get('update', 'Unknown')}
"""
        return [TextContent(type="text", text=info)]
    
    async def _list_scans(self) -> List[TextContent]:
        scans = self.nessus.list_scans()
        
        if not scans:
            return [TextContent(type="text", text="No scans found.")]
        
        output = "## Active Scans\n\n"
        output += "| ID | Name | Status | Targets | Last Modified |\n"
        output += "|---|---|---|---|---|\n"
        
        for scan in scans:
            scan_id = scan.get('id', 'N/A')
            name = scan.get('name', 'N/A')
            status = scan.get('status', 'N/A')
            targets = scan.get('targets', 'N/A')
            last_mod = scan.get('last_modification_date', 'N/A')
            
            output += f"| {scan_id} | {name} | {status} | {targets} | {last_mod} |\n"
        
        output += f"\n**Total Scans:** {len(scans)}"
        
        return [TextContent(type="text", text=output)]
    
    async def _get_scan_details(self, scan_id: int) -> List[TextContent]:
        details = self.nessus.get_scan_details(scan_id)
        info = details.get('info', {})
        hosts = details.get('hosts', [])
        vulns = details.get('vulnerabilities', [])
        
        # Calculate severity counts
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for vuln in vulns:
            severity = vuln.get('severity', 0)
            count = vuln.get('count', 1)
            if severity == 4:
                severity_counts['critical'] += count
            elif severity == 3:
                severity_counts['high'] += count
            elif severity == 2:
                severity_counts['medium'] += count
            elif severity == 1:
                severity_counts['low'] += count
            else:
                severity_counts['info'] += count
        
        output = f"""## Scan Details: {info.get('name')}

**Scan ID:** {scan_id}
**Status:** {info.get('status')}
**Targets:** {info.get('targets')}
**Start Time:** {info.get('scan_start', 'N/A')}
**End Time:** {info.get('scan_end', 'N/A')}

### Vulnerability Summary
- **Critical:** {severity_counts['critical']}
- **High:** {severity_counts['high']}
- **Medium:** {severity_counts['medium']}
- **Low:** {severity_counts['low']}
- **Info:** {severity_counts['info']}

### Hosts Scanned
**Total Hosts:** {len(hosts)}
"""
        
        if hosts:
            output += "\n| Host | Critical | High | Medium | Low |\n"
            output += "|---|---|---|---|---|\n"
            for host in hosts[:10]:  # Limit to first 10
                hostname = host.get('hostname', 'N/A')
                crit = host.get('critical', 0)
                high = host.get('high', 0)
                med = host.get('medium', 0)
                low = host.get('low', 0)
                output += f"| {hostname} | {crit} | {high} | {med} | {low} |\n"
            
            if len(hosts) > 10:
                output += f"\n*Showing 10 of {len(hosts)} hosts*\n"
        
        return [TextContent(type="text", text=output)]
    
    async def _create_scan(self, name: str, targets: str, template: str) -> List[TextContent]:
        result = self.nessus.create_scan(name, targets, template)
        scan_id = result['scan']['id']
        
        output = f"""## Scan Created Successfully

**Scan ID:** {scan_id}
**Name:** {name}
**Targets:** {targets}
**Template:** {template}

**Status:** Ready to launch

Use `launch_scan` with scan_id={scan_id} to start the scan.
"""
        return [TextContent(type="text", text=output)]
    
    async def _launch_scan(self, scan_id: int) -> List[TextContent]:
        self.nessus.launch_scan(scan_id)
        
        output = f"""## Scan Launched

**Scan ID:** {scan_id}

The scan is now running. Use `get_scan_status` to check progress.
"""
        return [TextContent(type="text", text=output)]
    
    async def _get_scan_status(self, scan_id: int) -> List[TextContent]:
        details = self.nessus.get_scan_details(scan_id)
        info = details.get('info', {})
        
        status = info.get('status')
        progress = info.get('scanner_progress', 0)
        
        output = f"""## Scan Status

**Scan ID:** {scan_id}
**Status:** {status}
**Progress:** {progress}%

"""
        if status == 'running':
            output += "The scan is currently in progress."
        elif status == 'completed':
            output += "The scan has completed successfully. You can now retrieve vulnerabilities."
        elif status == 'canceled':
            output += "The scan was canceled."
        elif status == 'aborted':
            output += "The scan was aborted."
        
        return [TextContent(type="text", text=output)]
    
    async def _stop_scan(self, scan_id: int) -> List[TextContent]:
        self.nessus.stop_scan(scan_id)
        return [TextContent(type="text", text=f"Scan {scan_id} has been stopped.")]
    
    async def _pause_scan(self, scan_id: int) -> List[TextContent]:
        self.nessus.pause_scan(scan_id)
        return [TextContent(type="text", text=f"Scan {scan_id} has been paused.")]
    
    async def _resume_scan(self, scan_id: int) -> List[TextContent]:
        self.nessus.resume_scan(scan_id)
        return [TextContent(type="text", text=f"Scan {scan_id} has been resumed.")]
    
    async def _delete_scan(self, scan_id: int) -> List[TextContent]:
        self.nessus.delete_scan(scan_id)
        return [TextContent(type="text", text=f"Scan {scan_id} has been deleted.")]
    
    async def _list_templates(self) -> List[TextContent]:
        templates = self.nessus.list_templates()
        
        output = "## Available Scan Templates\n\n"
        output += "| Name | Description |\n"
        output += "|---|---|\n"
        
        for tmpl in templates:
            name = tmpl.get('name', 'N/A')
            desc = tmpl.get('desc', 'N/A')
            output += f"| {name} | {desc} |\n"
        
        return [TextContent(type="text", text=output)]
    
    async def _list_policies(self) -> List[TextContent]:
        policies = self.nessus.list_policies()
        
        if not policies:
            return [TextContent(type="text", text="No custom policies found.")]
        
        output = "## Custom Scan Policies\n\n"
        output += "| ID | Name | Description |\n"
        output += "|---|---|---|\n"
        
        for policy in policies:
            pol_id = policy.get('id', 'N/A')
            name = policy.get('name', 'N/A')
            desc = policy.get('description', 'N/A')
            output += f"| {pol_id} | {name} | {desc} |\n"
        
        return [TextContent(type="text", text=output)]
    
    async def _get_vulnerabilities(self, scan_id: int, min_severity: str, include_remediation: bool) -> List[TextContent]:
        vulns = self.nessus.get_vulnerabilities(scan_id)
        
        # Severity mapping
        severity_map = {'info': 0, 'low': 1, 'medium': 2, 'high': 3, 'critical': 4}
        min_sev_value = severity_map.get(min_severity, 0)
        
        # Filter by severity
        filtered_vulns = [v for v in vulns if v.get('severity', 0) >= min_sev_value]
        
        if not filtered_vulns:
            return [TextContent(type="text", text=f"No vulnerabilities found with severity >= {min_severity}")]
        
        # Sort by severity (highest first)
        filtered_vulns.sort(key=lambda x: x.get('severity', 0), reverse=True)
        
        output = f"## Vulnerabilities (Severity >= {min_severity})\n\n"
        
        # Summary
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0}
        for vuln in filtered_vulns:
            sev = vuln.get('severity', 0)
            count = vuln.get('count', 1)
            if sev == 4:
                severity_counts['critical'] += count
            elif sev == 3:
                severity_counts['high'] += count
            elif sev == 2:
                severity_counts['medium'] += count
            elif sev == 1:
                severity_counts['low'] += count
        
        output += "### Summary\n"
        output += f"- **Critical:** {severity_counts['critical']}\n"
        output += f"- **High:** {severity_counts['high']}\n"
        output += f"- **Medium:** {severity_counts['medium']}\n"
        output += f"- **Low:** {severity_counts['low']}\n\n"
        
        # List vulnerabilities
        output += "### Critical & High Vulnerabilities\n\n"
        
        for vuln in filtered_vulns:
            if vuln.get('severity', 0) >= 3:  # Critical or High
                sev_name = "CRITICAL" if vuln.get('severity') == 4 else "HIGH"
                plugin_name = vuln.get('plugin_name', 'Unknown')
                plugin_id = vuln.get('plugin_id', 'N/A')
                count = vuln.get('count', 1)
                
                output += f"**[{sev_name}] {plugin_name}**\n"
                output += f"- Plugin ID: {plugin_id}\n"
                output += f"- Affected Hosts: {count}\n"
                
                if include_remediation:
                    # Get detailed info for remediation
                    try:
                        details = self.nessus.get_vulnerability_details(scan_id, plugin_id)
                        if 'solution' in details.get('info', {}).get('plugindescription', {}):
                            solution = details['info']['plugindescription']['pluginattributes'].get('solution', 'No solution available')
                            output += f"- **Remediation:** {solution[:200]}...\n"
                    except:
                        pass
                
                output += "\n"
        
        return [TextContent(type="text", text=output)]
    
    async def _get_vulnerability_details(self, scan_id: int, plugin_id: int) -> List[TextContent]:
        details = self.nessus.get_vulnerability_details(scan_id, plugin_id)
        
        info = details.get('info', {})
        plugin_desc = info.get('plugindescription', {})
        plugin_attrs = plugin_desc.get('pluginattributes', {})
        
        severity = info.get('severity', 0)
        sev_map = {0: 'Info', 1: 'Low', 2: 'Medium', 3: 'High', 4: 'Critical'}
        
        output = f"""## Vulnerability Details

**Plugin ID:** {plugin_id}
**Name:** {plugin_attrs.get('plugin_name', 'N/A')}
**Severity:** {sev_map.get(severity, 'Unknown')}

### Description
{plugin_attrs.get('description', 'No description available')}

### Solution
{plugin_attrs.get('solution', 'No solution available')}

### See Also
{plugin_attrs.get('see_also', 'N/A')}

### CVE References
{', '.join(plugin_attrs.get('cve', [])) if plugin_attrs.get('cve') else 'None'}

### Risk Information
- **CVSS Base Score:** {plugin_attrs.get('cvss_base_score', 'N/A')}
- **CVSS Vector:** {plugin_attrs.get('cvss_vector', 'N/A')}
"""
        
        return [TextContent(type="text", text=output)]
    
    async def _get_host_vulnerabilities(self, scan_id: int, host_id: int) -> List[TextContent]:
        host_data = self.nessus.get_host_vulnerabilities(scan_id, host_id)
        
        info = host_data.get('info', {})
        vulns = host_data.get('vulnerabilities', [])
        
        output = f"""## Host Vulnerabilities

**Host:** {info.get('host-fqdn', info.get('host-ip', 'N/A'))}
**Operating System:** {info.get('operating-system', 'Unknown')}
**Total Vulnerabilities:** {len(vulns)}

### Vulnerability Breakdown
"""
        
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for vuln in vulns:
            sev = vuln.get('severity', 0)
            if sev == 4:
                severity_counts['critical'] += 1
            elif sev == 3:
                severity_counts['high'] += 1
            elif sev == 2:
                severity_counts['medium'] += 1
            elif sev == 1:
                severity_counts['low'] += 1
            else:
                severity_counts['info'] += 1
        
        output += f"- **Critical:** {severity_counts['critical']}\n"
        output += f"- **High:** {severity_counts['high']}\n"
        output += f"- **Medium:** {severity_counts['medium']}\n"
        output += f"- **Low:** {severity_counts['low']}\n"
        output += f"- **Info:** {severity_counts['info']}\n"
        
        return [TextContent(type="text", text=output)]
    
    async def _export_scan(self, scan_id: int, format: str, filename: Optional[str]) -> List[TextContent]:
        # Request export
        file_id = self.nessus.export_scan(scan_id, format)
        
        # Wait for export to be ready
        if not self.nessus.wait_for_export(scan_id, file_id):
            return [TextContent(type="text", text="Export timed out. Please try again.")]
        
        # Download export
        data = self.nessus.download_export(scan_id, file_id)
        
        # Save to file
        if not filename:
            filename = f"scan_{scan_id}_report"
        
        output_path = self.output_dir / f"{filename}.{format}"
        with open(output_path, 'wb') as f:
            f.write(data)
        
        output = f"""## Scan Export Complete

**Format:** {format.upper()}
**File:** {output_path}
**Size:** {len(data) / 1024:.2f} KB

The report has been saved to your local filesystem.
"""
        return [TextContent(type="text", text=output)]
    
    async def _scan_workflow(self, name: str, targets: str, template: str, export_format: str) -> List[TextContent]:
        output = "## Complete Scan Workflow\n\n"
        
        # Step 1: Create scan
        output += "### Step 1: Creating Scan\n"
        result = self.nessus.create_scan(name, targets, template)
        scan_id = result['scan']['id']
        output += f"✓ Scan created (ID: {scan_id})\n\n"
        
        # Step 2: Launch scan
        output += "### Step 2: Launching Scan\n"
        self.nessus.launch_scan(scan_id)
        output += "✓ Scan launched\n\n"
        
        # Step 3: Wait for completion
        output += "### Step 3: Waiting for Completion\n"
        output += "This may take several minutes...\n"
        
        try:
            status = self.nessus.wait_for_scan(scan_id, poll_interval=15, timeout=3600)
            output += f"✓ Scan completed with status: {status}\n\n"
        except TimeoutError:
            output += "⚠ Scan is still running. Check status later with get_scan_status.\n"
            return [TextContent(type="text", text=output)]
        
        # Step 4: Get results
        output += "### Step 4: Scan Results\n"
        details = self.nessus.get_scan_details(scan_id)
        vulns = details.get('vulnerabilities', [])
        
        severity_counts = {'critical': 0, 'high': 0, 'medium': 0, 'low': 0, 'info': 0}
        for vuln in vulns:
            sev = vuln.get('severity', 0)
            count = vuln.get('count', 1)
            if sev == 4:
                severity_counts['critical'] += count
            elif sev == 3:
                severity_counts['high'] += count
            elif sev == 2:
                severity_counts['medium'] += count
            elif sev == 1:
                severity_counts['low'] += count
            else:
                severity_counts['info'] += count
        
        output += f"- **Critical:** {severity_counts['critical']}\n"
        output += f"- **High:** {severity_counts['high']}\n"
        output += f"- **Medium:** {severity_counts['medium']}\n"
        output += f"- **Low:** {severity_counts['low']}\n"
        output += f"- **Info:** {severity_counts['info']}\n\n"
        
        # Show critical/high vulnerabilities
        if severity_counts['critical'] > 0 or severity_counts['high'] > 0:
            output += "### Critical & High Vulnerabilities\n"
            for vuln in sorted(vulns, key=lambda x: x.get('severity', 0), reverse=True):
                if vuln.get('severity', 0) >= 3:
                    sev_name = "CRITICAL" if vuln.get('severity') == 4 else "HIGH"
                    output += f"- **[{sev_name}]** {vuln.get('plugin_name')} (affects {vuln.get('count', 1)} host(s))\n"
            output += "\n"
        
        # Step 5: Export (if requested)
        if export_format != 'none':
            output += "### Step 5: Exporting Report\n"
            file_id = self.nessus.export_scan(scan_id, export_format)
            
            if self.nessus.wait_for_export(scan_id, file_id):
                data = self.nessus.download_export(scan_id, file_id)
                output_path = self.output_dir / f"scan_{scan_id}_report.{export_format}"
                with open(output_path, 'wb') as f:
                    f.write(data)
                output += f"✓ Report exported to: {output_path}\n"
            else:
                output += "⚠ Export timed out\n"
        
        output += f"\n**Scan ID {scan_id} workflow complete!**"
        
        return [TextContent(type="text", text=output)]
    
    async def _quick_scan(self, targets: str) -> List[TextContent]:
        name = f"Quick Discovery - {targets}"
        
        # Create discovery scan
        result = self.nessus.create_scan(name, targets, 'discovery')
        scan_id = result['scan']['id']
        
        # Launch
        self.nessus.launch_scan(scan_id)
        
        # Wait for completion (discovery scans are fast)
        try:
            status = self.nessus.wait_for_scan(scan_id, poll_interval=10, timeout=600)
        except TimeoutError:
            return [TextContent(type="text", text=f"Quick scan started (ID: {scan_id}) but is taking longer than expected. Check status later.")]
        
        # Get results
        details = self.nessus.get_scan_details(scan_id)
        hosts = details.get('hosts', [])
        
        output = f"""## Quick Scan Results

**Targets:** {targets}
**Scan ID:** {scan_id}
**Active Hosts Found:** {len(hosts)}

### Discovered Hosts
"""
        
        for host in hosts:
            hostname = host.get('hostname', 'N/A')
            host_ip = host.get('host_ip', 'N/A')
            os = host.get('operating_system', 'Unknown')
            
            output += f"- **{hostname}** ({host_ip})\n"
            output += f"  - OS: {os}\n"
            output += f"  - Severity: C:{host.get('critical', 0)} H:{host.get('high', 0)} M:{host.get('medium', 0)} L:{host.get('low', 0)}\n"
        
        return [TextContent(type="text", text=output)]


async def main():
    """Main entry point for MCP server"""
    server = NessusMCPServer()
    
    # Run stdio server
    from mcp.server.stdio import stdio_server

    logger.info("MCP server ready on stdio, waiting for client (e.g. Claude Desktop) to send requests...")
    async with stdio_server() as (read_stream, write_stream):
        await server.server.run(
            read_stream,
            write_stream,
            server.server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
