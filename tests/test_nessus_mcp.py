#!/usr/bin/env python3
"""
Test suite for Nessus MCP Server
Run basic connectivity and functionality tests
"""

import json
import sys
from pathlib import Path

try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:
    print("Error: requests library not installed")
    print("Install with: pip install requests")
    sys.exit(1)


class PinnedCertAdapter(HTTPAdapter):
    """Trust only the certificate whose SHA-256 fingerprint is pinned (as the server does)."""

    def __init__(self, fingerprint, **kwargs):
        self._fingerprint = fingerprint
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['assert_fingerprint'] = self._fingerprint
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, *args, **kwargs):
        kwargs['assert_fingerprint'] = self._fingerprint
        return super().proxy_manager_for(*args, **kwargs)

    def send(self, request, **kwargs):
        kwargs['verify'] = False  # the pin replaces the CA and hostname checks
        return super().send(request, **kwargs)


def session_for(config):
    """A requests session that checks the Nessus certificate the way the server does."""
    session = requests.Session()
    fingerprint = config.get('tls_fingerprint')
    if fingerprint:
        session.mount('https://', PinnedCertAdapter(fingerprint.replace(':', '').lower()))
    else:
        session.verify = config.get('verify_ssl', True)
    return session


def load_config():
    """Load configuration from config.json"""
    config_paths = [
        Path("config.json"),
        Path("config/config.json"),
        Path("/app/config/config.json")
    ]
    
    for config_path in config_paths:
        if config_path.exists():
            with open(config_path) as f:
                return json.load(f)
    
    print("Error: config.json not found")
    print("Searched locations:")
    for path in config_paths:
        print(f"  - {path}")
    sys.exit(1)


def test_connection(config):
    """Test basic connection to Nessus"""
    print("\n" + "="*60)
    print("TEST 1: Connection Test")
    print("="*60)
    
    try:
        headers = {
            'X-ApiKeys': f"accessKey={config['access_key']}; secretKey={config['secret_key']}"
        }
        
        response = session_for(config).get(
            f"{config['nessus_url']}/server/properties",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✓ Connection successful!")
            print(f"  Server Version: {data.get('server_version', 'Unknown')}")
            print(f"  Scanner UUID: {data.get('scanner_uuid', 'Unknown')[:8]}...")
            print(f"  Feed: {data.get('feed', 'Unknown')}")
            return True
        else:
            print(f"✗ Connection failed: HTTP {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False
            
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        return False


def test_list_scans(config):
    """Test listing scans"""
    print("\n" + "="*60)
    print("TEST 2: List Scans")
    print("="*60)
    
    try:
        headers = {
            'X-ApiKeys': f"accessKey={config['access_key']}; secretKey={config['secret_key']}"
        }
        
        response = session_for(config).get(
            f"{config['nessus_url']}/scans",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            scans = data.get('scans', [])
            print(f"✓ Successfully retrieved {len(scans)} scan(s)")
            
            if scans:
                print("\nRecent scans:")
                for scan in scans[:3]:
                    print(f"  - {scan['name']} (Status: {scan['status']})")
            else:
                print("  No scans found (this is normal for a new installation)")
            return True
        else:
            print(f"✗ Failed to list scans: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ List scans failed: {e}")
        return False


def test_list_policies(config):
    """Test listing scan policies"""
    print("\n" + "="*60)
    print("TEST 3: List Policies")
    print("="*60)
    
    try:
        headers = {
            'X-ApiKeys': f"accessKey={config['access_key']}; secretKey={config['secret_key']}"
        }
        
        response = session_for(config).get(
            f"{config['nessus_url']}/policies",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            policies = data.get('policies', [])
            print(f"✓ Successfully retrieved {len(policies)} policy/policies")
            
            if policies:
                print("\nAvailable policies:")
                for policy in policies[:5]:
                    print(f"  - {policy['name']}")
            return True
        else:
            print(f"✗ Failed to list policies: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ List policies failed: {e}")
        return False


def test_list_scanners(config):
    """Test listing scanners"""
    print("\n" + "="*60)
    print("TEST 4: List Scanners")
    print("="*60)
    
    try:
        headers = {
            'X-ApiKeys': f"accessKey={config['access_key']}; secretKey={config['secret_key']}"
        }
        
        response = session_for(config).get(
            f"{config['nessus_url']}/scanners",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            scanners = data.get('scanners', [])
            print(f"✓ Successfully retrieved {len(scanners)} scanner(s)")
            
            for scanner in scanners:
                print(f"  - {scanner['name']} (Status: {scanner['status']})")
            return True
        else:
            print(f"✗ Failed to list scanners: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ List scanners failed: {e}")
        return False


def main():
    """Run all tests"""
    print("="*60)
    print("  Nessus MCP Server - Test Suite")
    print("="*60)
    
    # Load configuration
    config = load_config()
    print(f"\nTesting Nessus at: {config['nessus_url']}")
    tls = 'pinned fingerprint' if config.get('tls_fingerprint') else config.get('verify_ssl', True)
    print(f"SSL Verification: {tls}")
    
    # Run tests
    results = {
        "Connection": test_connection(config),
        "List Scans": test_list_scans(config),
        "List Policies": test_list_policies(config),
        "List Scanners": test_list_scanners(config)
    }
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}  {test_name}")
    
    print(f"\nResults: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! Nessus MCP Server is ready to use.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. Check configuration and Nessus status.")
        return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nTests cancelled.")
        sys.exit(1)
