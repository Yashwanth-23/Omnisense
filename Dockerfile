# =============================================================================
# Omnisense — FastAPI Backend Container
# =============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install OS-level dependencies (Tesseract OCR + FFmpeg for Whisper)
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first (Docker layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip "setuptools<70" wheel \
    && pip install --no-cache-dir --no-build-isolation -r requirements.txt

# Copy application code
COPY config.py .
COPY main.py .

# Create non-root user for security
RUN useradd --create-home appuser \
    && mkdir -p /app/chroma_db \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]