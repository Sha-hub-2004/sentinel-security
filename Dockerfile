# ================================================
# Stage 1: Build stage for compiling dependencies
# ================================================
FROM python:3.10-slim AS builder

WORKDIR /app

# Install build dependencies needed for compiling C-extensions (such as bcrypt or psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file to install dependencies
COPY requirements.txt .

# Install dependencies under the /root/.local path
RUN pip install --no-cache-dir --user -r requirements.txt


# ================================================
# Stage 2: Minimal runtime environment
# ================================================
FROM python:3.10-slim AS runner

WORKDIR /app

# Install bare-minimum runtime dependencies (libpq5 for postgres, curl for healthcheck probes)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed dependencies from the builder stage
COPY --from=builder /root/.local /root/.local

# Ensure packages installed in /root/.local/bin are available on PATH
ENV PATH=/root/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Copy application files (leveraging .dockerignore to skip node modules, virtualenvs, etc.)
COPY . .

# Expose ports: 8000 for FastAPI backend, 8501 for Streamlit UI
EXPOSE 8000
EXPOSE 8501

# Add standard Docker Health Check targeting our new API health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT}/health || exit 1

# Default command runs the FastAPI backend. Can be overridden at launch (e.g. for Streamlit or consumer worker)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
