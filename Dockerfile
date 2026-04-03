FROM python:3.15.0a6-alpine

WORKDIR /app

# 1. Install the default local runtime tools
ARG INSTALL_GPSD_CLIENTS=false
RUN set -eux; \
	apk add --no-cache chrony zlib=1.3.2-r0; \
	if [ "$INSTALL_GPSD_CLIENTS" = "true" ]; then \
		apk add --no-cache gpsd-clients; \
	fi

# 2. Download Tailwind CSS locally
RUN mkdir -p /app/static && wget -q https://cdn.tailwindcss.com/ -O /app/static/tailwindcss.js

# 3. Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip==26.0 \
	&& pip install --no-cache-dir -r requirements.txt

# 4. Copy the app files (.dockerignore will block the junk automatically)
COPY . .

# Set version last so dependency layers are not invalidated on version changes
ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

# Match your custom port
EXPOSE 55234

CMD ["python", "app.py"]
