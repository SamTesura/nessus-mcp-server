# Nessus MCP Server Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the MCP server script
COPY nessus_mcp_server.py .

# Create directory for config (will be mounted)
RUN mkdir -p /app/config

# Create directory for reports
RUN mkdir -p /app/reports

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV NESSUS_CONFIG_PATH=/app/config/nessus_mcp_config.json

# Run the MCP server
CMD ["python", "nessus_mcp_server.py"]
