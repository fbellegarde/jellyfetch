FROM python:3.12-slim

# Prevent interactive prompts during package install
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=5547 \
    HOST=0.0.0.0

# Install system dependencies: FFmpeg, curl, unzip, certificates
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Deno runtime for YouTube challenge evaluation
RUN curl -fsSL https://deno.land/install.sh | sh \
    && ln -s /root/.deno/bin/deno /usr/local/bin/deno

WORKDIR /app

# Copy package definitions first for optimal layer caching
COPY pyproject.toml ./

# Install Python requirements
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir \
        yt-dlp \
        yt-dlp-ejs \
        flask \
        python-dotenv

# Copy full application codebase
COPY . .

# Install JellyFetch package into container environment
RUN pip install --no-cache-dir -e .

EXPOSE 5547

# Start Flask server
CMD ["python", "web/server.py"]