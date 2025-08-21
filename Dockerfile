# Multi-stage build to reduce final image size
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# Production stage
FROM python:3.11-slim

# Install ca-certificates package for corporate CA support
RUN apt-get update && apt-get install -y \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv
# Copy pre-downloaded models from builder stage
#COPY --from=builder /root/.cache /tmp/model_cache
ENV PATH="/opt/venv/bin:$PATH"

# Create non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

WORKDIR /app

# Copy application files
COPY app.py /app/
COPY templates /app/templates/

# Create data directory for ChromaDB persistence and cache directories
RUN mkdir -p /data/chromadb /app/.cache && chown -R appuser:appuser /app /data

USER appuser

# Set cache environment variables
ENV HF_HOME=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/sentence_transformers
ENV PYTHONWARNINGS="ignore:Unverified HTTPS request"

EXPOSE 5300

CMD ["python", "app.py"]
