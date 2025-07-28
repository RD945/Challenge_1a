FROM --platform=linux/amd64 python:3.10-slim

WORKDIR /app

# Copy the processing script
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY process_pdfs.py .

# Run the script
CMD ["python", "process_pdfs.py"] 