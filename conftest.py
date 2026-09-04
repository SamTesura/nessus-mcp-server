"""Pytest rootdir config for the Nessus MCP server.

The legacy tests/test_nessus_mcp.py is an interactive connectivity script whose
`test_*` functions require a live Nessus instance and a config.json (they take a
`config` positional pytest cannot supply as a fixture). Exclude it from
collection so the deterministic unit tests run without a network.
"""

collect_ignore = ["tests/test_nessus_mcp.py"]
