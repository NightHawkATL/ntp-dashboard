<img width="1280" height="640" alt="ntp-dashboard-title" src="https://github.com/user-attachments/assets/199cf686-c90e-45d9-b533-2d5818451ff6" />

**This is a current work in progress. It was coded with AI to see if it was possible and will be later be scanned, updated, and code revised to make sure that the AI aspect of it was just temporary. I want to look over the code now that it is running and working and be able to make updates and modifications myself. I will also be working on doing actual releases once I get to the point I feel it is ready.**

The default use for this app is to pull the NTP data from your docker host and show the servers that it is using. It will display the current system time and time offset from NTP.

<img width="1167" height="879" alt="image" src="https://github.com/user-attachments/assets/5107d45a-f105-4f4c-9a68-10361e8021d9" />

When connecting the app to a local NTP GPS-enabled server over SSH, you will then see the NMEA and PTP data, almong with the GPS data visualized. All you have to do is click on the "Connection Setup" button and put in the SSH credentials for your local NTP server and it will make the connection and populate the data correctly.

<img width="1054" height="894" alt="image" src="https://github.com/user-attachments/assets/f9916aa4-b5d2-4ce7-9d56-5efbaa1fdba9" />

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
