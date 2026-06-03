FROM python:3.11-slim

# ── Install Chromium (arm64 compatible) ───────────────────────────────────────
RUN apt-get update && apt-get install -y chromium wget gnupg2 unzip curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── App source ────────────────────────────────────────────────────────────────
COPY . .
RUN mkdir -p /app/data/cv /app/logs /app/chrome_profile

# ── Runtime env ───────────────────────────────────────────────────────────────
ENV DATABASE_URL=sqlite:////app/data/smart_job_assistant.db
ENV CV_UPLOAD_DIR=/app/data/cv
ENV CHROME_USER_DATA_DIR=/app/chrome_profile
ENV PORT_NUM=9222
ENV DOCKER_ENV=1

EXPOSE 8000
CMD ["uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
