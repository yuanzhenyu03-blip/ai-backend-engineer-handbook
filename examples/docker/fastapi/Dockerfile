# =============================================================================
# EXAMPLE ONLY — Day23 (Docker Fundamentals): production-oriented FastAPI image
#
# Copy this into a real FastAPI project (with requirements.txt and an `app/`
# package exposing `app.main:app`) and adjust as needed. This documentation
# repository has no FastAPI app, so this image is a teaching template.
#
# Cache-friendly order: stable steps first (deps), changing app code last.
# Lesson: docs/devops/day23-docker-fundamentals.md
# =============================================================================

# Pin a slim base line for a predictable build (not an unqualified `latest`).
FROM python:3.12-slim

# Working directory inside the image/container.
WORKDIR /app

# Copy the dependency manifest FIRST so the install layer is cached when the
# manifest is unchanged (the app code below changes far more often).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code last (changes most frequently -> smallest cache busting).
COPY app ./app

# Run as a non-root user (least privilege).
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

# Document the port the app listens on inside the container.
EXPOSE 8000

# Runtime health check against the app's health endpoint (adjust the path).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0) if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else sys.exit(1)"

# Default runtime process (image metadata). --host 0.0.0.0 lets the service
# listen on the container's network interfaces, not loopback only.
# Secrets/config are injected at runtime (docker run -e / --env-file / secret
# manager), never baked into the image.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
