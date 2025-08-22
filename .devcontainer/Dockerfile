# trunk-ignore-all(trivy)
# trunk-ignore-all(checkov)

FROM rommapp/romm-devcontainer:4.1.4

# Install frontend dependencies
COPY frontend/package.json /app/frontend/
WORKDIR /app/frontend
RUN npm install

# Set working directory
WORKDIR /app

# Copy project files (including pyproject.toml and uv.lock)
COPY pyproject.toml uv.lock* .python-version /app/

# Install Python dependencies
RUN uv sync --all-extras
ENV PATH="/app/.venv/bin:${PATH}"