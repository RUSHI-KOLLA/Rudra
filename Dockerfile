# ---- Build stage: install deps ----
FROM python:3.11-slim AS builder

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Runtime stage: minimal image ----
FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the vg package (api/, incidents/, config.py, main.py)
COPY vg/ /app/vg/

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# Hugging Face Spaces / Koyeb expect port 7860
ENV PORT=7860
EXPOSE 7860

# Run the VG web server from /app (parent of vg package)
CMD ["python", "-m", "vg.main", "--web", "--host", "0.0.0.0", "--port", "7860"]
