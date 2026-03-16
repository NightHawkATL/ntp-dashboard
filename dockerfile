FROM python:3.11-slim
# Install tools inside container so we don't pollute the host
RUN apt-get update && apt-get install -y chrony gpsd-clients wget && rm -rf /var/lib/apt/lists/*
WORKDIR /app
# Download Tailwind for offline viewing
RUN mkdir -p /app/static && wget -q https://cdn.tailwindcss.com/ -O /app/static/tailwindcss.js
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 55234
CMD ["python", "app.py"]