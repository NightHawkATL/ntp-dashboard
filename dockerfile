FROM python:3.14-alpine

WORKDIR /app

# 1. Install Alpine's lightweight packages (No Desktop GUI bloat!)
# We also install GNU grep just to ensure compatibility with our scripts
RUN apk add --no-cache chrony gpsd-clients grep

# 2. Download Tailwind CSS locally
RUN mkdir -p /app/static && wget -q https://cdn.tailwindcss.com/ -O /app/static/tailwindcss.js

# 3. Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the app files (.dockerignore will block the junk automatically)
COPY . .

# Set version last so dependency layers are not invalidated on version changes
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

# Match your custom port
EXPOSE 55234

CMD ["python", "app.py"]
