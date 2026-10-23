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

## 📋 Prerequisites
* **Docker Desktop (Running).**
* **Nessus Essentials (Installed on host).**
* **Claude Desktop (Installed).**

## 🚀 Quick Start
1. **Clone the repo:** `git clone https://github.com/samtesura/nessus-mcp-server.git`
2. **Setup Config:** Copy `nessus_mcp_config.json.example` to `nessus_mcp_config.json`, add your Nessus API keys, and set `tls_fingerprint` to your Nessus certificate's SHA-256 fingerprint ([how](docs/troubleshooting.md#-problem-ssl-certificate-verify-failed)). The server refuses any other certificate, so the keys only ever go to your Nessus.
3. **Build:** Run `.\scripts/build-docker.ps1`
4. **Integrate:** Add the server configuration to your `claude_desktop_config.json`.

> **Note:** For full step-by-step instructions, see the [Installation Guide](docs/installation.md).

## 🧪 Usage Examples
* "List my current Nessus scans."
* "What is the status of the 'Web App' scan?"
* "Create a new scan for 10.0.0.5 using the Basic Network Scan policy."

## Technical summary 

### The Challenge
Nessus is a powerful vulnerability scanner, but managing it often requires navigating a complex web UI or writing custom scripts for the JSON API. Integrating these capabilities directly into an AI’s context window requires a bridge that handles authentication, networking, and structured data exchange.

### The Solution
This project implements a dedicated MCP Server that acts as an intelligent intermediary between Claude Desktop and a local Nessus Essentials instance. It features:

* Robust Containerization: A Docker-based deployment that uses host.docker.internal to securely bridge the gap between the isolated container and the host-running Nessus service.

* Automated Security Workflows: Logic for launching scans, monitoring progress, and automatically exporting vulnerability summaries in PDF format.

* Error-Resilient Design: Optimized PowerShell build scripts and a simplified Dockerfile to ensure seamless setup on Windows environments.

### Impact
By abstracting the Nessus API into natural language tools, security analysts can perform comprehensive network audits ("Scan 192.168.1.0/24 and summarize the findings") without leaving their primary research environment.
