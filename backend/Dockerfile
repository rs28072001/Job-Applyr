FROM python:3.11-slim

# ── Install Chrome ────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y wget gnupg2 unzip curl \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub \
       | gpg --dearmor > /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] \
       http://dl.google.com/linux/chrome/deb/ stable main" \
       > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
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
