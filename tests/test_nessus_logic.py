#!/usr/bin/env python3
"""Unit tests for the pure logic in nessus_mcp_server.

Covered without a network or live Nessus:
  - NessusClient.create_scan template-selection (substring match + fallback)
  - NessusClient thin wrappers return the right slice of an API response
  - severity counting / filtering / sorting and Markdown formatting in the
    async tool methods (driven through a fake client)
  - call_tool dispatch: unknown-tool error and exception-to-text mapping

Skipped (needs a live Nessus / network / MCP stdio transport): NessusMCPServer
construction via load_config(), wait_for_scan/wait_for_export polling loops, and
the real stdio server in main().
"""

import asyncio

import pytest

import nessus_mcp_server as ns


def run(coro):
    return asyncio.run(coro)


def make_client():
    """A NessusClient with no network — _request is stubbed per test."""
    return ns.NessusClient("https://host:8834/", "ak", "sk", verify_ssl=False)


def make_server(fake_nessus):
    """A NessusMCPServer with __init__ bypassed (no config, no connection)."""
    srv = ns.NessusMCPServer.__new__(ns.NessusMCPServer)
    srv.nessus = fake_nessus
    return srv


class FakeNessus:
    """Minimal stand-in exposing just the methods a tool method calls."""
    def __init__(self, **canned):
        self._canned = canned

    def __getattr__(self, name):
        if name in self._canned:
            val = self._canned[name]
            return (lambda *a, **k: val) if not callable(val) else val
        raise AttributeError(name)


# ------------------------------------------------------ client construction
def test_client_normalizes_url_and_headers():
    c = ns.NessusClient("https://host:8834/", "AK", "SK")
    assert c.url == "https://host:8834"
    assert "accessKey=AK" in c.headers["X-ApiKeys"]
    assert "secretKey=SK" in c.headers["X-ApiKeys"]
    assert c.session.verify is False


# --------------------------------------------------------- create_scan logic
def test_create_scan_matches_template_by_substring(monkeypatch):
    c = make_client()
    monkeypatch.setattr(c, "list_templates", lambda: [
        {"name": "Advanced Scan", "uuid": "u-adv"},
        {"name": "Basic Network Scan", "uuid": "u-basic"},
    ])
    captured = {}

    def fake_request(method, endpoint, data=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["data"] = data
        return {"scan": {"id": 7}}

    monkeypatch.setattr(c, "_request", fake_request)
    c.create_scan("My Scan", "10.0.0.1", template="basic")
    assert captured["data"]["uuid"] == "u-basic"
    assert captured["data"]["settings"]["text_targets"] == "10.0.0.1"
    assert captured["endpoint"] == "/scans"


def test_create_scan_falls_back_to_first_template(monkeypatch):
    c = make_client()
    monkeypatch.setattr(c, "list_templates", lambda: [
        {"name": "Advanced Scan", "uuid": "u-adv"},
        {"name": "Discovery", "uuid": "u-disc"},
    ])
    captured = {}
    monkeypatch.setattr(c, "_request", lambda method, endpoint, data=None: captured.update(data=data) or {})
    c.create_scan("S", "t", template="nonexistent")
    assert captured["data"]["uuid"] == "u-adv"


def test_create_scan_handles_no_templates(monkeypatch):
    c = make_client()
    monkeypatch.setattr(c, "list_templates", lambda: [])
    captured = {}
    monkeypatch.setattr(c, "_request", lambda method, endpoint, data=None: captured.update(data=data) or {})
    c.create_scan("S", "t")
    assert captured["data"]["uuid"] is None


# --------------------------------------------------- thin response wrappers
def test_list_scans_unwraps_scans_key(monkeypatch):
    c = make_client()
    monkeypatch.setattr(c, "_request", lambda *a, **k: {"scans": [{"id": 1}, {"id": 2}]})
    assert c.list_scans() == [{"id": 1}, {"id": 2}]


def test_list_scans_missing_key_returns_empty(monkeypatch):
    c = make_client()
    monkeypatch.setattr(c, "_request", lambda *a, **k: {})
    assert c.list_scans() == []


def test_export_scan_returns_file_id(monkeypatch):
    c = make_client()
    monkeypatch.setattr(c, "_request", lambda *a, **k: {"file": 42})
    assert c.export_scan(3, "pdf") == 42


def test_get_export_status_returns_status(monkeypatch):
    c = make_client()
    monkeypatch.setattr(c, "_request", lambda *a, **k: {"status": "ready"})
    assert c.get_export_status(1, 2) == "ready"


# ------------------------------------------------ severity counting / format
def test_get_scan_details_counts_severities():
    details = {
        "info": {"name": "S", "status": "completed", "targets": "10.0.0.1"},
        "hosts": [{"hostname": "h1", "critical": 1, "high": 2, "medium": 0, "low": 0}],
        "vulnerabilities": [
            {"severity": 4, "count": 2},
            {"severity": 3, "count": 1},
            {"severity": 2, "count": 5},
            {"severity": 0, "count": 9},
        ],
    }
    srv = make_server(FakeNessus(get_scan_details=details))
    out = run(srv._get_scan_details(1))[0].text
    assert "**Critical:** 2" in out
    assert "**High:** 1" in out
    assert "**Medium:** 5" in out
    assert "**Info:** 9" in out
    assert "h1" in out


def test_get_vulnerabilities_filters_by_min_severity():
    vulns = [
        {"severity": 4, "count": 1, "plugin_name": "Crit bug", "plugin_id": 100},
        {"severity": 3, "count": 2, "plugin_name": "High bug", "plugin_id": 101},
        {"severity": 1, "count": 9, "plugin_name": "Low bug", "plugin_id": 102},
    ]
    srv = make_server(FakeNessus(get_vulnerabilities=vulns))
    out = run(srv._get_vulnerabilities(1, "high", False))[0].text
    assert "Crit bug" in out
    assert "High bug" in out
    assert "Low bug" not in out
    # Summary counts only the filtered (>= high) set.
    assert "**Critical:** 1" in out
    assert "**High:** 2" in out


def test_get_vulnerabilities_none_above_threshold():
    vulns = [{"severity": 1, "count": 3, "plugin_name": "Low", "plugin_id": 1}]
    srv = make_server(FakeNessus(get_vulnerabilities=vulns))
    out = run(srv._get_vulnerabilities(1, "critical", False))[0].text
    assert "No vulnerabilities found" in out


def test_get_vulnerability_details_maps_severity():
    details = {
        "info": {
            "severity": 4,
            "plugindescription": {
                "pluginattributes": {
                    "plugin_name": "RCE",
                    "description": "bad",
                    "solution": "patch",
                    "cve": ["CVE-2024-1", "CVE-2024-2"],
                    "cvss_base_score": "9.8",
                }
            },
        }
    }
    srv = make_server(FakeNessus(get_vulnerability_details=details))
    out = run(srv._get_vulnerability_details(1, 55))[0].text
    assert "**Severity:** Critical" in out
    assert "RCE" in out
    assert "CVE-2024-1, CVE-2024-2" in out
    assert "9.8" in out


@pytest.mark.parametrize("status,needle", [
    ("running", "currently in progress"),
    ("completed", "completed successfully"),
    ("canceled", "was canceled"),
    ("aborted", "was aborted"),
])
def test_get_scan_status_messages(status, needle):
    details = {"info": {"status": status, "scanner_progress": 50}}
    srv = make_server(FakeNessus(get_scan_details=details))
    out = run(srv._get_scan_status(1))[0].text
    assert needle in out


def test_list_scans_empty_message():
    srv = make_server(FakeNessus(list_scans=[]))
    out = run(srv._list_scans())[0].text
    assert "No scans found" in out


# ------------------------------------------------------------ call_tool
def test_call_tool_unknown_returns_error_text():
    srv = make_server(FakeNessus())
    out = run(srv.call_tool("does_not_exist", {}))[0].text
    assert out.startswith("Error:")
    assert "Unknown tool" in out


def test_call_tool_maps_exception_to_text():
    class Boom(FakeNessus):
        def list_scans(self):
            raise RuntimeError("kaboom")

    srv = make_server(Boom())
    out = run(srv.call_tool("list_scans", {}))[0].text
    assert out.startswith("Error:")
    assert "kaboom" in out
