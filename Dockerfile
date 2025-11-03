# Multi-platform Dockerfile for creating platform-independent images
#
# This Dockerfile supports multiple platforms:
# - Linux AMD64 (x86_64): Standard Intel/AMD processors on Linux
# - Linux ARM64 (aarch64): Apple Silicon, AWS Graviton, Raspberry Pi 4
# 
# Note: Windows support has been removed as the python:3.11-slim image
# is not available for Windows platforms
#
# To create a multi-architecture image that works on any platform:
#
# 1. Set up Docker BuildKit builder if you haven't already:
#    docker buildx create --name multiarch --driver docker-container --use
#
# 2. Build and push a multi-architecture image to a registry:
#    docker buildx build --platform linux/amd64,linux/arm64 -t username/mcp-instana:latest --push .
#
# 3. Pull and run the image on any platform:
#    docker pull username/mcp-instana:latest
#    docker run -p 8080:8080 username/mcp-instana:latest
#
# The image will automatically use the correct architecture version for the host system.
#
# Note: The --push flag is required for multi-architecture builds as Docker needs to
# create a manifest list in a registry. If you want to load the image locally for testing,
# you can only build for your current architecture:
#    docker buildx build --platform linux/amd64 -t mcp-instana:latest --load .
#
# For CI/CD pipelines (e.g., GitHub Actions):
# ```yaml
# jobs:
#   build-push:
#     runs-on: ubuntu-latest
#     steps:
#       - name: Checkout code
#         uses: actions/checkout@v3
#       
#       - name: Set up QEMU
#         uses: docker/setup-qemu-action@v2
#       
#       - name: Set up Docker Buildx
#         uses: docker/setup-buildx-action@v2
#       
#       - name: Login to DockerHub
#         uses: docker/login-action@v2
#         with:
#           username: ${{ secrets.DOCKERHUB_USERNAME }}
#           password: ${{ secrets.DOCKERHUB_TOKEN }}
#       
#       - name: Build and push
#         uses: docker/build-push-action@v4
#         with:
#           context: .
#           platforms: linux/amd64,linux/arm64
#           push: true
#           tags: username/mcp-instana:latest
# ```
#
# Stage 1: Build stage with minimal runtime dependencies
FROM --platform=${BUILDPLATFORM:-linux/arm64} docker.io/library/python:3.11-slim AS builder

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only the runtime dependency file and source code needed for the build
COPY pyproject-runtime.toml pyproject.toml
COPY src ./src
COPY README.md ./

# Install uv for dependency management
RUN pip install --no-cache-dir uv

# Install only runtime dependencies using the minimal pyproject-runtime.toml
RUN uv pip install --no-cache-dir --system .

# Stage 2: Runtime stage
FROM python:3.11-slim AS runtime

# Set working directory
WORKDIR /app

# Create a non-root user for security
RUN groupadd -r mcpuser && useradd -r -g mcpuser mcpuser

# Copy only the Python packages from builder (no source code needed)
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy only the source code needed for runtime
COPY src ./src

# Set ownership to non-root user
RUN chown -R mcpuser:mcpuser /app

# Switch to non-root user
USER mcpuser

# Expose the default port (configurable via PORT env var)
EXPOSE 8080

# Set environment variables (no hardcoded secrets)
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Health check using container's internal network
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://127.0.0.1:8080/health', timeout=5)" || exit 1

# Run the server
ENTRYPOINT ["python", "-m", "src.core.server"]
CMD ["--transport", "streamable-http"]
