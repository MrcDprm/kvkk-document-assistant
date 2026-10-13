FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Dependencies first, so this layer is cached until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

# The trained name model lives in a GitHub Release (too large for git); the build fails if
# its SHA-256 does not match.
ARG NER_MODEL_URL=https://github.com/MrcDprm/kvkk-document-assistant/releases/download/ner-model-v1/kvkk-ner-model-v1.zip
ARG NER_MODEL_SHA256=463ea7aa9dc903b0338a2d168a8751e0f80f9c0db96926ab501474f4536eb50d
COPY scripts/fetch_model.py scripts/
RUN python scripts/fetch_model.py "$NER_MODEL_URL" "$NER_MODEL_SHA256" models/ner

COPY kvkk_mask/ kvkk_mask/
COPY app/ app/

# Run as an unprivileged user.
RUN useradd --create-home --uid 10001 appuser
USER appuser

EXPOSE 10000
# Render passes the port in $PORT. --proxy-headers makes request.client.host the visitor's IP
# behind Render's proxy (used by the rate limiter); only that proxy can reach the container.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*' --no-server-header"]
