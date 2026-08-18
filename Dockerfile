FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY tests/ ./tests/
COPY scripts/ ./scripts/
COPY client-secret.json ./client-secret.json

# The bot is a Discord client only - no HTTP server runs, so nothing listens on 8000.
EXPOSE 8000

CMD ["python", "-m", "src.bot"]
