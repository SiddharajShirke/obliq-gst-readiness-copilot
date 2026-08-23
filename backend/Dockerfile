FROM python:3.11-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/opt/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/opt/huggingface
WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr libgl1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*
COPY backend/pyproject.toml /app/pyproject.toml
COPY backend/app /app/app
COPY demo_data /app/demo_data
RUN pip install --no-cache-dir .
ARG EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
