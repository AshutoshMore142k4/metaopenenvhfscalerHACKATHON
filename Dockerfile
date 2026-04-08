FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port for FastAPI
EXPOSE 8000

# Run the OpenEnv server
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
