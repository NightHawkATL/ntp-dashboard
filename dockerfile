FROM python:3.11-slim

WORKDIR /app

# 1. Add --no-install-recommends to block the 800MB GUI Desktop bloat!
RUN apt-get update && apt-get install -y --no-install-recommends \
    chrony \
    gpsd-clients \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Download Tailwind CSS locally
RUN mkdir -p /app/static && wget -q https://cdn.tailwindcss.com/ -O /app/static/tailwindcss.js

# 3. (Optional) Purge wget after we use it to save another few megabytes
RUN apt-get purge -y wget ca-certificates && apt-get autoremove -y && apt-get clean

# 4. Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the app files (The .dockerignore file will block the junk automatically)
COPY . .

# Match your custom port
EXPOSE 55234

CMD ["python", "app.py"]
