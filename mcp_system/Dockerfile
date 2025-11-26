# Dockerfile for MCP System (FastAPI)

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Playwright dependencies (needed for visa tools)
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY mcp_system/requirements.txt ./requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (needed for visa tools)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copy MCP system files
COPY mcp_system/ ./mcp_system/

# Copy memory directory (needed by memory_tools)
COPY memory/ ./memory/

# Set working directory
WORKDIR /app/mcp_system/server

# Expose MCP server port
EXPOSE 8090

# Run MCP server
CMD ["python", "main_server.py"]

