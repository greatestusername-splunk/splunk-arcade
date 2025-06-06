# Use Python 3.12 slim-bullseye as the base image
FROM python:3.12-slim-bullseye

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore
# Expose port 5000
EXPOSE 5000

# Install system dependencies
# hadolint ignore=DL3008
RUN DEBIAN_FRONTEND=noninteractive; \
    apt-get update -y && \
    apt-get install -yq --no-install-recommends \
            curl && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/archive/*.deb

RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_UNMANAGED_INSTALL="/usr/local/bin" sh

# Set the working directory
WORKDIR /app

# Install uv (a faster alternative to pip)
RUN uv venv
ENV PATH="/.venv/bin:$PATH"

# Copy the requirements file
COPY requirements.txt requirements.txt

# Install Python dependencies using uv
RUN uv pip install --system --upgrade pip -r requirements.txt && \
    opentelemetry-bootstrap -a install

# Copy the rest of the application code
COPY . .

# Set the entrypoint command
CMD ["/app/entrypoint.sh"]
