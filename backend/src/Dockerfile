# 1. Use an official base image (Debian slim — glibc required by pymupdf / onnxruntime)
FROM python:3.12.13-slim

# Build-time argument — override to embed a different embedding model
ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2

# 2. Set the working directory inside the container
WORKDIR /usr/local/app

# HuggingFace / sentence-transformers cache stored inside the image
# (makes the container fully offline-capable at runtime)
ENV HF_HOME=/usr/local/app/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/usr/local/app/.cache/sentence_transformers

# Expose the ARG as an ENV so shell commands in RUN can reference it
ENV EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL}

# 3. Install system dependencies
#    - gcc / build-essential : compilation de psycopg2 et extensions C
#    - libpq-dev             : client PostgreSQL (requis par psycopg2)
#    - curl                  : healthcheck
#    - tesseract-ocr         : OCR pour les PDF scannés et les images de plans BTP
#    - tesseract-ocr-fra     : données linguistiques françaises pour Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        tesseract-ocr \
        tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

# 4. Install Python deps then pre-download ALL models (online phase, build only)
#    After this step the image is fully self-contained — no network needed at runtime.
RUN pip install --no-cache-dir -r requirements.txt \
    # ── spaCy models ──────────────────────────────────────────────────────
    && python -m spacy download fr_core_news_sm \
    && python -m spacy download en_core_web_sm \
    # ── Sentence-transformers embedding model ─────────────────────────────
    # Stored in $SENTENCE_TRANSFORMERS_HOME so the runtime picks it up offline
    && python -c "import os; from sentence_transformers import SentenceTransformer; SentenceTransformer(os.environ['EMBEDDING_MODEL_NAME'], cache_folder=os.environ['SENTENCE_TRANSFORMERS_HOME']); print('Embedding model downloaded.')"

# Once downloaded, we can safely set offline mode for runtime
ENV TRANSFORMERS_OFFLINE=1 \
    HF_HUB_OFFLINE=1

# 5. Copy the rest of the application code
COPY lib ./lib
COPY main.py ./

# 6. Document the port the app listens on
EXPOSE 8742

# 7. Create a non-root user and transfer ownership of the cache
RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /usr/local/app/.cache
USER appuser

# 7. Health check to ensure the application is running
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s \
  CMD curl -f http://localhost:8742/ || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8742", "--workers", "4"]
