FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1

# Install system dependencies including Poppler for PDF processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      # OpenCV dependencies
      libgl1 \
      libglib2.0-0 \
      libsm6 \
      libxrender1 \
      libxext6 \
      # PDF processing dependencies
      poppler-utils \
      # Tesseract OCR (if needed for text extraction)
      tesseract-ocr \
      # Additional utilities
      libgomp1 \
      libmagic1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements from backend folder and install dependencies
COPY backend/requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend application code
COPY backend/ /app/

# Expose port (Railway will override with $PORT)

# Start uvicorn with PORT from environment variable
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]