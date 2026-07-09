# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

# Defensive: some ML-adjacent transitive deps (grpcio, mmh3, tokenizers) may fall back
# to source builds without a matching prebuilt wheel. Cheap here -- this stage is discarded.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
# CPU-only torch first -- sentence-transformers would otherwise pull the CUDA-bundled
# wheel (multi-GB). This container never touches a GPU; Ollama does all GPU inference
# natively on the host.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

# Pre-warm the embedding model into the image so no container needs network access on
# its first search_corpus call.
ENV HF_HOME=/opt/hf-cache
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/hf-cache /opt/hf-cache
ENV PATH="/opt/venv/bin:$PATH" \
    HF_HOME=/opt/hf-cache \
    PYTHONUNBUFFERED=1

COPY . .

# No CMD/ENTRYPOINT -- docker-compose.yml supplies `command:` per service
# (dashboard vs. simulation) off this one image.
