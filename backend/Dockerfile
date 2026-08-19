FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr libgl1 && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
COPY demo_data /app/demo_data
RUN pip install --no-cache-dir .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
