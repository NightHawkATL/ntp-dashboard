<img width="1280" height="640" alt="ntp-dashboard-title" src="https://github.com/user-attachments/assets/fd519072-43d6-4c5e-bb9e-cda729db4bd3" />

When I first built my NTP-PPS server, I followed this blog on how to do it: https://blog.networkprofile.org/gps-backed-local-ntp-server/. Once I was done, I wanted to be able to check on it occasionally to make sure everything was still working as expected. I just wanted to be able to monitor it without doing a bunch of extra work with Grafana and whatever else would be needed. That is where I came up with this app, to fill a need that I had for a dashboard for my NTP server. I couldn't find anything that I liked or was anywhere close to what I wanted, so I had to wait for AI to get good enough and for me to want to use it to come up with this solution. I do hope you enjoy it and consider giving it a star.

The initial deployment for this app is to pull the sources data from Chrony on your docker host and show the servers that it is using. It will display the current system time and time offset from NTP. This is similar to an "NTP Client" that just pulls the time based on how the Docker host is setup for time resolution.

<img width="1045" height="858" alt="image" src="https://github.com/user-attachments/assets/8c26db82-3838-4c46-8c5a-135d765cc5ae" />

When connecting the app to a personal NTP GPS-enabled server over SSH, you will then see the NMEA and PPS data, almong with the GPS data visualized. All you have to do is click on the "Connection Setup" button and put in the SSH credentials for your personal NTP server and it will make the connection and populate the data correctly. The login credentials are stored locally in a "config.json" file that is stored wherever you set the bind mount to (default is `.data:/app/data`). The password is stored as encrypted and a separate key is used to unlock or decrypt the password for use.

<img width="940" height="852" alt="image" src="https://github.com/user-attachments/assets/f33ea67f-cda3-49bb-850a-0d03c18ec7d4" />

Connecting to the remote server with SSH keys is as easy as "copy & paste" just open the connection settings, choose "Remote" and then fill in all the fields except password and then paste in your private key. The remote session will be activated and connected.

<img width="454" height="604" alt="image" src="https://github.com/user-attachments/assets/7bd6cc08-7998-4360-a374-9c63288c7816" />

With the color picker, you can make the interface match your favorite color (as close as possible). All you need to do is locate the "Theme" button and click it. When you select the color, it will automatically change the color scheme to what you pick. You can change it daily or keep it as it is. The color selection is stored locally in the browser so the only time it would revert back is if your browser cache and storage was totally cleared. This does mean that you can have different themes for different browsers on different computers though.

<img width="232" height="442" alt="image" src="https://github.com/user-attachments/assets/1b2a41b7-d02c-4800-838f-9e4cfba7dd2f" />

The NTP Sources data will refresh every 2 seconds and the Satellites data will refresh every 30 seconds. The GPS Satellite Time display will update every 30 seconds as the satellite data is updated.

The "View Clients" button will reveal a list of connected clients when running in "Remote" mode. It will allow you to track all the IP addresses (clients) that are currently connected and getting time from your NTP server, without having to drill into the CLI to get that information! You will get an error for this when in local mode as it is not supported.

<img width="670" height="783" alt="image" src="https://github.com/user-attachments/assets/a870b1c2-ef97-4355-b312-be2144e512a6" />

# Docker Deployment
You can deploy the app using the following Docker Compose:
```yaml
services:
  ntp-dashboard:
    image: ghcr.io/nighthawkatl/ntp-dashboard:latest ## -> Change to "nighthawkatl/ntp-dashboard:latest" to pull from Docker Hub.
    container_name: ntp-dashboard ## you can call it whatever you want. This is just a friendly suggestion.
    network_mode: "host" ## Required to allow direct communication with the chrony package on the host.
    environment:
      - DEBUG_MODE=false ## change to true if you see something strange happening and wish to open an issue and paste logs
    volumes:
      - ./data:/app/data ## Bind mounts are suggested to have easy-access to the data files.
    restart: unless-stopped ## Typical deployment unless you wish to change this.
```
# Prerequisites
In order to get the most out of this app, even for the "local-only" deployment in docker, you will need to install Chrony on your host. For Debian-based or Ubuntu users, this is as simple as `sudo apt install chrony`. There is a link in the wiki for "troubleshooting" on how to install chrony for other distros.

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
6. ~~Color picker to choose your favorite color in light or dark mode~~

# Troublehooting

Please check the [wiki](https://github.com/NightHawkATL/ntp-dashboard/wiki).

# Disclaimer
**This is a current work in progress. It was coded with the help of AI to get the base project running with my ideas.**
