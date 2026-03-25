# Nessus MCP Server for Claude Desktop

An implementation of the **Model Context Protocol (MCP)** that allows Claude Desktop to interact directly with **Tenable Nessus**. Perform vulnerability scans, list policies, and generate security reports using natural language.


## ✨ Key Features
* **Natural Language Security:** Ask Claude to "Run a basic network scan on 192.168.1.0/24."
* **Automated Reporting:** Generate and retrieve PDF vulnerability reports via chat.
* **Dockerized Architecture:** Easy deployment with a pre-configured Docker environment.
* **Security First:** Local-only communication using `host.docker.internal` to keep your scan data private.

## 🛠️ Technology Stack
* **Language:** Python 3.11+
* **Interface:** Model Context Protocol (MCP)
* **API:** Tenable Nessus JSON API
* **Containerization:** Docker

## 🚀 Quick Start
1. **Clone the repo:** `git clone https://github.com/your-username/nessus-mcp-server.git`
2. **Setup Config:** Rename `config.json.example` to `config.json` and add your Nessus API keys.
3. **Build:** Run `.\scripts/build-docker.ps1`
4. **Integrate:** Add the server configuration to your `claude_desktop_config.json`.

> **Note:** For full step-by-step instructions, see the [Installation Guide](docs/installation.md).

## 🧪 Usage Examples
* "List my current Nessus scans."
* "What is the status of the 'Web App' scan?"
* "Create a new scan for 10.0.0.5 using the Basic Network Scan policy."