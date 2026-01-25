FROM python:3.10-slim

# Install system dependencies (needed for Pillow/Barcodes and Postgres)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Force bcrypt 3.2.2 compatibility fix (passlib issue)
RUN pip install --no-cache-dir "bcrypt==3.2.2"

# Copy Application Code
COPY . .

# Create directory for barcodes if not exists
RUN mkdir -p static/barcodes && chmod 777 static/barcodes

# Expose Port (Render uses $PORT env var, but uvicorn needs explicit bind)
EXPOSE 8000

# Start Command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
