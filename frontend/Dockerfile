# Multi-stage build for frontend (React + Flask)

# Stage 1: Build React app
FROM node:18-alpine AS react-builder

WORKDIR /app

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY frontend/ ./

# Build React app
RUN npm run build

# Stage 2: Python runtime with Flask
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements files
COPY frontend/requirements.txt ./frontend-requirements.txt
COPY langraph/requirements.txt ./langraph-requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r frontend-requirements.txt && \
    pip install --no-cache-dir -r langraph-requirements.txt

# Copy built React app from builder stage
COPY --from=react-builder /app/dist ./frontend/dist

# Copy frontend Flask app
COPY frontend/app.py ./frontend/

# Copy langraph directory (needed by Flask app)
COPY langraph/ ./langraph/

# Copy memory directory (needed by Flask app)
COPY memory/ ./memory/

# Copy stm directory (needed by Flask app)
COPY stm/ ./stm/

# Copy mcp_system/clients directory (needed by Flask app)
COPY mcp_system/clients/ ./mcp_system/clients/

# Set working directory to frontend
WORKDIR /app/frontend

# Expose Flask port
EXPOSE 5000

# Run Flask app
CMD ["python", "app.py"]

