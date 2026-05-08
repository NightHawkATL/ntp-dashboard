<img width="1280" height="640" alt="ntp-dashboard-title" src="https://github.com/user-attachments/assets/fd519072-43d6-4c5e-bb9e-cda729db4bd3" />

> **Note:** This GitHub repository is a mirror of the primary self-hosted Gitea instance. All development, CI/CD, and issue tracking occurs on the Gitea instance. The GitHub mirror is provided for visibility and Docker Hub release publishing only. Issues opened here will be reviewed but response times may be slower than on the primary instance.

When I first built my NTP-PPS server, I followed this blog on how to do it: https://blog.networkprofile.org/gps-backed-local-ntp-server/. Once I was done, I wanted to be able to check on it occasionally to make sure everything was still working as expected. I just wanted to be able to monitor it without doing a bunch of extra work with Grafana and whatever else would be needed. That is where I came up with this app, to fill a need that I had for a dashboard for my NTP server. I couldn't find anything that I liked or was anywhere close to what I wanted, so I had to wait for AI to get good enough and for me to want to use it to come up with this solution. I do hope you enjoy it and consider giving it a star.

The initial deployment for this app pulls source data from Chrony on your Docker host and shows the servers it is using. It also displays the current system time and time offset from NTP. This is similar to an "NTP Client" that pulls time based on how the Docker host is set up for time resolution. _If you deploy this locally to your NTP server, it will look similar to the "Remote" host connection, including `PPS`, `NMEA`, satellite data, and connected clients. For a `Local` deployment on a different host than your NTP server, it will look like the image below._

<img width="1045" height="858" alt="image" src="https://github.com/user-attachments/assets/8c26db82-3838-4c46-8c5a-135d765cc5ae" />

When connecting the app to a personal NTP GPS-enabled server over SSH, you will then see the NMEA and PPS data, along with visualized GPS data. All you have to do is click the "Connection Setup" button, enter the SSH credentials for your personal NTP server, and it will connect and populate the data correctly. The login credentials are stored locally in a "config.json" file wherever you set the bind mount (default is `./data:/app/data`). The password is stored encrypted, and a separate key is used to decrypt it when needed.

<img width="940" height="852" alt="image" src="https://github.com/user-attachments/assets/f33ea67f-cda3-49bb-850a-0d03c18ec7d4" />

Connecting to the remote server with SSH keys is as easy as copy and paste: open the connection settings, choose "Remote", fill in all fields except password, and paste in your private key. The remote session will be activated and connected.

<img width="454" height="604" alt="image" src="https://github.com/user-attachments/assets/7bd6cc08-7998-4360-a374-9c63288c7816" />

With the color picker, you can make the interface match your favorite color (as close as possible). All you need to do is locate the "Theme" button and click it. When you select the color, it will automatically change the color scheme to what you pick. You can change it daily or keep it as it is. The color selection is stored locally in the browser so the only time it would revert back is if your browser cache and storage was totally cleared. This does mean that you can have different themes for different browsers on different computers though.

<img width="232" height="442" alt="image" src="https://github.com/user-attachments/assets/1b2a41b7-d02c-4800-838f-9e4cfba7dd2f" />

The NTP Sources data will refresh every 2 seconds and the Satellites data will refresh every 30 seconds. The GPS Satellite Time display will update every 30 seconds as the satellite data is updated.

The "View Clients" button reveals a list of connected clients and lets you track IP addresses currently getting time from your NTP server, without drilling into the CLI. This works in both "Remote" mode and "Local" mode when deployed on the NTP server host with `network_mode: "host"` and `/run/chrony:/run/chrony` mounted.

<img width="670" height="783" alt="image" src="https://github.com/user-attachments/assets/a870b1c2-ef97-4355-b312-be2144e512a6" />

# Docker Deployment
You can deploy the app using the following Docker Compose:
```yaml
services:
  ntp-dashboard:
    image: nighthawkatl/ntp-dashboard:latest
    container_name: ntp-dashboard ## you can call it whatever you want. This is just a friendly suggestion.
    network_mode: "host" ## Required to allow direct communication with the chrony package on the host.
    environment:
      - LOG_LEVEL=INFO # Default level for normal operation
        # Supported levels:
        # - DEBUG    # Most verbose (for troubleshooting)
        # - INFO     # Standard runtime logs (recommended default)
        # - WARNING  # Warnings and errors only
        # - ERROR    # Errors only
        # - CRITICAL # Critical failures only
    volumes:
      - ./data:/app/data ## Bind mounts are suggested to have easy-access to the data files.
      - /run/chrony:/run/chrony # Needed for local-only deployments to access chrony correctly and gather data
    restart: unless-stopped ## Typical deployment unless you wish to change this.
```
# Prerequisites
In order to get the most out of this app, even for the "local-only" deployment in Docker, you will need to install Chrony on your host. For Debian-based or Ubuntu users, this is as simple as `sudo apt install chrony`. There is a link in the wiki for "troubleshooting" on how to install Chrony for other distros.

The network mode must be set to "host" to allow direct access to the chrony service that is running on the host. If this is changed to "bridge" or anything else, it will not work as expected.

Local GPS probing from inside the container is optional. The default build installs Chrony tooling only, which avoids shipping Alpine's gpsd package by default. If you need local `gpspipe` support in the container, build with `INSTALL_GPSD_CLIENTS=true`. It is typically not needed unless you are running the dashboard directly on the NTP server. `gpspipe` currently has a critical CVE, [CVE-2025-67268](https://nvd.nist.gov/vuln/detail/CVE-2025-67268), affecting `apk / alpine/gpsd / 3.26.1-r0`. To keep the default deployment safer, gpsd support is excluded by default for remote-connection installs. If you intend to run the app local to the NTP server, build from source and set the argument to install `gpsd`. See `compose.yaml` [here](https://github.com/NightHawkATL/ntp-dashboard/blob/main/compose.yaml).

# Resource Usage
Usage is low running either the amd64 or the arm64 image. Network is near 0% even if you are using the "remote" mode to access a local NTP server on your network.

arm64 (local):

<img width="642" height="174" alt="Docker resource usage for arm64 in local mode" src="https://github.com/user-attachments/assets/dcf957e5-81bc-4c9a-acc3-2d3562a8ce2b" />

amd64 (remote):

<img width="639" height="192" alt="image" src="https://github.com/user-attachments/assets/861fcf80-19ad-42c8-9b6c-35b8be6fe5c5" />

arm64 (remote):

<img width="637" height="190" alt="image" src="https://github.com/user-attachments/assets/77723948-5d21-48b5-95b4-1259a127a140" />


# Roadmap
These are listed in no particular order

1. ~~Encrypting of password in config.json file~~
2. ~~PWA conversion~~
3. ~~Release update notifications~~
4. ~~Compact image~~
5. ~~Convert javascript in HTML to a script call as a separate file rather than being in the HTML~~
6. ~~Color picker to choose your favorite color in light or dark mode~~
7.  Work on updates and clearing vulnerabilities to get on a good maintenance and release schedule
8.  Come up with a few new features and ideas to improve the UI/UX (keeping the ball rolling)
9.  ~~Fix logging to show in the container logs for those times the app may not load~~

# Troubleshooting

Please check the [wiki](https://github.com/NightHawkATL/ntp-dashboard/wiki).

# Security

Please review the Security Policy for guidance on reporting vulnerabilities and checking remediation status.

# Disclaimer
**This is a current work in progress. It was coded with the help of AI to get the base project running with my ideas.**

## CI Test

This PR is to validate the Ollama PR review pipeline.
