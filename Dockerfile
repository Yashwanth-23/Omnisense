# 1. Using a lightweight Python image
FROM python:3.12-slim

# 2. Set the working directory inside the container
WORKDIR /app

# NEW: Install Tesseract AND ffmpeg at the OS level
RUN apt-get update && apt-get install -y tesseract-ocr ffmpeg && rm -rf /var/lib/apt/lists/*

# 3. Copy our list of libraries and install them
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of our code (main.py, chroma_db folder, etc.)
COPY . .

# 5. Open the port FastAPI runs on
EXPOSE 8000

# 6. Command to start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]