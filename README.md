<img size="25%" alt="ntp-dashboard-title" src="https://github.com/user-attachments/assets/fd519072-43d6-4c5e-bb9e-cda729db4bd3" />

When I first built my NTP-PPS server, I followed this blog on how to do it: https://blog.networkprofile.org/gps-backed-local-ntp-server/. Once I was done, I wanted to be able to check on it occasionally to make sure everything was still working as expected. I just wanted to be able to monitor it without doing a bunch of extra work with Grafana and whatever else would be needed. That is where I came up with this app, to fill a need that I had for a dashboard for my NTP server. I couldn't find anything that I liked or was anywhere close to what I wanted, so I had to wait for AI to get good enough and for me to want to use it to come up with this solution. I do hope you enjoy it and consider giving it a star.

The initial deployment for this app is to pull the sources data from Chrony on your docker host and show the servers that it is using. It will display the current system time and time offset from NTP. This is similar to an "NTP Client" that just pulls the time based on how the Docker host is setup for time resolution.

<img width="1060" height="900" alt="image" src="https://github.com/user-attachments/assets/9c0103c1-5263-481e-88e8-e87d0d46b90d" />

When connecting the app to a local NTP GPS-enabled server over SSH, you will then see the NMEA and PPS data, almong with the GPS data visualized. All you have to do is click on the "Connection Setup" button and put in the SSH credentials for your local NTP server and it will make the connection and populate the data correctly. The login credentials are stored locally in a "config.json" file that is stored wherever you set the bind mount to. The password is stored as encrypted and a separate key is used to unlock or decrypt the password for use.

<img width="981" height="933" alt="image" src="https://github.com/user-attachments/assets/b8581948-d6a0-4fe3-b154-085af3ea9371" />

The NTP Sources data will refresh every 2 seconds and the Satellites data will refresh every 30 seconds. The GPS Satellite Time display will update every 30 seconds as the satellite data is updated.

The new "View Clients" button will reveal a list of connected clients when running in "Remote" mode. It will allow you to track all the IP addresses (clients) that are currently connected and getting time from your NTP server, without having to drill into the CLI to get that information!

<img width="670" height="783" alt="image" src="https://github.com/user-attachments/assets/a870b1c2-ef97-4355-b312-be2144e512a6" />

# Docker Deployment
You can deploy the app using the following Docker Compose:
```yaml
services:
  ntp-dashboard:
    image: nighthawkatl/ntp-dashboard:latest ## -> Change to "ghcr.io/nighthawkatl/ntp-dashboard:latest" to pull the image from GitHub
    container_name: ntp-dashboard
    network_mode: "host"
    environment:
      - DEBUG_MODE=false
    volumes:
      - ./data:/app/data
    restart: unless-stopped
```
# Prerequisites
In order to get the most out of this app, even for the "local-only" deployment in docker, you will need to install Chrony on your host. for Debian or Ubuntu users, this is as simple as `sudo apt install chrony`. There is a link in the wiki for "troubleshooting" on how to install chrony for other distros.

The network mode must be set to "host" to allow direct access to the chrony service that is running on the host. If this is changed to "bridge" or anything else, it will not work as expected.

# Resource Usage
Usage is low running either the amd64 or the arm 64 image. Network is near 0% even if you are using the "remote" mode to access a local NTP server on your network.

amd64:

<img width="639" height="192" alt="image" src="https://github.com/user-attachments/assets/861fcf80-19ad-42c8-9b6c-35b8be6fe5c5" />

arm64:

<img width="637" height="190" alt="image" src="https://github.com/user-attachments/assets/77723948-5d21-48b5-95b4-1259a127a140" />


# Roadmap
These are listed in no particular order

1. ~~Encrypting of password in config.json file~~
2. ~~PWA conversion~~
3. ~~Release update notifications~~
4. ~~Compact image~~
5. ~~Convert javascript in HTML to a script call as a separate file rather than being in the HTML~~
6. Color picker to choose your favorite color for the background in light or dark mode

# Troublehooting

Please check the [wiki](https://github.com/NightHawkATL/ntp-dashboard/wiki).

# Disclaimer
**This is a current work in progress. It was coded with the help of AI to get the base project running with my ideas.**
