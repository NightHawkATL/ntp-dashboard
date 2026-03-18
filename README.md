<img width="1280" height="640" alt="ntp-dashboard-title" src="https://github.com/user-attachments/assets/199cf686-c90e-45d9-b533-2d5818451ff6" />

**This is a current work in progress. It was coded with AI to see if it was possible and will be later be scanned, updated, and code revised to make sure that the AI aspect of it was just temporary. I want to look over the code now that it is running and working and be able to make updates and modifications myself.**

The default use for this app is to pull the NTP data from your docker host and show the servers that it is using. It will display the current system time and time offset from NTP.

<img width="934" height="786" alt="image" src="https://github.com/user-attachments/assets/cc2b9d4d-8e8b-43f3-92ad-b6e54b274af7" />

When connecting the app to a local NTP GPS-enabled server over SSH, you will then see the NMEA and PTP data, almong with the GPS data visualized. All you have to do is click on the "Connection Setup" button and put in the SSH credentials for your local NTP server and it will make the connection and populate the data correctly.

<img width="946" height="865" alt="image" src="https://github.com/user-attachments/assets/97800d2d-af11-4a9c-972b-3e44c6807005" />

The NTP Sources data will refresh every 2 seconds and the Satellites data will refresh every 30 seconds. The GPS Satellite Time display will update every 30 seconds as the satellite data is updated.

You can deploy the app using the following Docker Compose:
```
services:
  ntp-dashboard:
    image: nighthawkatl/ntp-dashboard:latest
    container_name: ntp-dashboard
    network_mode: "host" # Allows container to query host's chrony/gpsd
    volumes:
      - ./config.json:/app/config.json # Persists UI settings
    restart: unless-stopped
```

# Roadmap
1. PWA conversion
2. Release update notifications
3. Compact image
4. Convert javascript in HTML to a script call as a separate file rather than being in the HTML