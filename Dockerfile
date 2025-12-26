# Use Python 3.8 slim image
FROM python:3.8-slim

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml .
COPY agent/ ./agent/
COPY tests/ ./tests/
COPY logs/ ./logs/
COPY data/ ./data/
COPY sop/ ./sop/
COPY chroma_db/ ./chroma_db/
COPY drain3_state.bin .

# Install dependencies
RUN pip install --no-cache-dir -e .

# Create necessary directories
RUN mkdir -p logs data sop chroma_db

# Expose port if needed (for web interface or API, but currently not implemented)
# EXPOSE 8000

# Default command to run the agent
CMD ["python", "-m", "agent.agent"]