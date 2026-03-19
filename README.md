<img width="1280" height="640" alt="ntp-dashboard-title" src="https://github.com/user-attachments/assets/199cf686-c90e-45d9-b533-2d5818451ff6" />

**This is a current work in progress. It was coded with AI to see if it was possible and will be scanned, updated, and code revised to make sure that the code stays secure and clean. I want to look over the code now that it is running and working and be able to make updates and modifications myself.**

When I first built my NTP-PPS server, I followed this blog on how to do it: https://blog.networkprofile.org/gps-backed-local-ntp-server/. Once I was done, I wanted to be able to check on it occasionally to make sure everything was still working as expected. I just wanted to be able to monitor it without doing a bunch of extra work with Grafana and whatever else would be needed. That is where I came up with this app, to fill a need that I had for a dashboard for my NTP server. I couldn't find anything that I liked or was anywhere close to what I wanted, so I had to wait for AI to get good enough and for me to want to use it to come up with this solution. I do hope you enjoy it and consider giving it a star.

The standard deployment ("out-of-the-box experience" or "OOBE") for this app is to pull the NTP clock data from Chrony on your docker host and show the servers that it is using. It will display the current system time and time offset from NTP.

<img width="933" height="783" alt="image" src="https://github.com/user-attachments/assets/133a3ce3-d85e-4f36-91f5-881dff9aab09" />

When connecting the app to a local NTP GPS-enabled server over SSH, you will then see the NMEA and PTP data, almong with the GPS data visualized. All you have to do is click on the "Connection Setup" button and put in the SSH credentials for your local NTP server and it will make the connection and populate the data correctly. The login credentials are stored locally in a "config.json" file that is stored whereever you set the bind mount to. The password is stored in plain-text (at the moment) and is never sent to anywhere outside of the app container.

<img width="952" height="867" alt="image" src="https://github.com/user-attachments/assets/15c8e313-4ef1-4af9-9cdc-6eb1b4b25f91" />

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
These are listed in no particular order

1. Hashing of password in config.json file
2. PWA conversion
3. Release update notifications
4. Compact image
5. Convert javascript in HTML to a script call as a separate file rather than being in the HTML
6. Color picker to choose your favorite color for the background in light or dark mode

# Troublehooting

Please check the [wiki](https://github.com/NightHawkATL/ntp-dashboard/wiki).