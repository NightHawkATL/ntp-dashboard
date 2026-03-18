<img width="1280" height="640" alt="ntp-dashboard-title" src="https://github.com/user-attachments/assets/199cf686-c90e-45d9-b533-2d5818451ff6" />

**This is a current work in progress. It was coded with AI to see if it was possible and will be later be scanned, updated, and code revised to make sure that the AI aspect of it was just temporary. I want to look over the code now that it is running and working and be able to make updates and modifications myself. I will also be working on doing actual releases once I get to the point I feel it is ready.**

The default use for this app is to pull the NTP data from your docker host and show the servers that it is using. It will display the current system time and time offset from NTP.

<img width="1162" height="906" alt="image" src="https://github.com/user-attachments/assets/b0686f4a-64fe-4651-948b-4b9ba9a0f897" />

When connecting the app to a local NTP GPS-enabled server over SSH, you will then see the NMEA and PTP data, almong with the GPS data visualized. All you have to do is click on the "Connection Setup" button and put in the SSH credentials for your local NTP server and it will make the connection and populate the data correctly.

<img width="955" height="813" alt="image" src="https://github.com/user-attachments/assets/142e8a9c-e8e5-4ecd-8bdf-c74a1f7d2300" />

The NTP Sources data will refresh every 2 seconds and the Satellites data will refresh every 30 seconds.

You can deploy the app using the following Docker Compose:
```
services:
  ntp-dashboard:
    image: nighthawkatl/ntp-docker-ntp-dashboard:latest
    container_name: ntp-dashboard
    network_mode: "host" # Allows container to query host's chrony/gpsd
    volumes:
      - ./config.json:/app/config.json # Persists UI settings
    restart: unless-stopped
```
