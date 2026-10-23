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

# pip and mcp's HTTP client also trust the OS store, so make sure it no longer
# trusts the two roots behind the compromised eMudhra (emSign) CAs, even when
# the apt layer above comes from cache or Debian's fix (ca-certificates
# 20250419+deb13u1) has not reached this base yet. '!' deselects a listed
# root; once the fixed package has deselected or dropped one, sed finds no
# plain line to change. The check fails the build if either root is still
# trusted.
RUN sed -i -e 's|^mozilla/emSign_ECC_Root_CA_-_G3\.crt$|!&|' \
           -e 's|^mozilla/Comodo_AAA_Services_root\.crt$|!&|' \
           /etc/ca-certificates.conf && \
    update-ca-certificates && \
    subjects="$(openssl crl2pkcs7 -nocrl -certfile /etc/ssl/certs/ca-certificates.crt \
        | openssl pkcs7 -print_certs -noout)" && \
    if printf '%s\n' "$subjects" | grep -E \
        '^subject=.*CN ?= ?(emSign ECC Root CA - G3|AAA Certificate Services)(,|$)'; then \
        echo "ERROR: the system CA store still trusts a root behind the compromised eMudhra CAs" >&2; \
        exit 1; \
    fi

# Upgrade pip before it downloads anything else. pip always trusts its own
# vendored CA bundle on top of the OS store, so an older pip in the base image
# still trusts the compromised eMudhra (emSign) CAs; 26.2.2 ships the fixed
# bundle. The exact URL plus SHA-256 keeps this one download safe even over
# that older trust.
RUN python -m pip install --no-cache-dir \
    "pip @ https://files.pythonhosted.org/packages/3f/06/3e4420302363fbb71be3c7f35ce042f54bfca330e3e66b3a2e3c4cca579f/pip-26.2.2-py3-none-any.whl#sha256=fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70"

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
