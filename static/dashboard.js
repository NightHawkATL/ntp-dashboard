        // 1. UI Modals
        const modal = document.getElementById('settingsModal');
        function openSettings() { modal.classList.remove('hidden'); }
        function closeSettings() { modal.classList.add('hidden'); }
        function toggleRemote() { 
            const isLocal = document.getElementById('mode').value === 'local';
            document.getElementById('remoteFields').classList.toggle('hidden', isLocal); 
        }

        // 2. NEW CLOCK LOGIC (Milliseconds & Live GPS Ticking)
        let baseGpsTimeMs = null;
        let fetchLocalTimeMs = null;

        // Helper function for Local Time
        function formatTimeWithMs(date) {
            const dateStr = date.toLocaleDateString();
            let hours = date.getHours();
            const ampm = hours >= 12 ? 'PM' : 'AM';
            hours = hours % 12;
            hours = hours ? hours : 12; 
            const mins = date.getMinutes().toString().padStart(2, '0');
            const secs = date.getSeconds().toString().padStart(2, '0');
            const ms = date.getMilliseconds().toString().padStart(3, '0');
            return `${dateStr}, ${hours}:${mins}:${secs}.${ms} ${ampm}`;
        }

        // Helper function for strict UTC/GMT Satellite Time
        function formatUTCWithMs(date) {
            const dateStr = date.getUTCFullYear() + "-" + (date.getUTCMonth()+1).toString().padStart(2,'0') + "-" + date.getUTCDate().toString().padStart(2,'0');
            const hours = date.getUTCHours().toString().padStart(2, '0');
            const mins = date.getUTCMinutes().toString().padStart(2, '0');
            const secs = date.getUTCSeconds().toString().padStart(2, '0');
            const ms = date.getUTCMilliseconds().toString().padStart(3, '0');
            return `${dateStr}, ${hours}:${mins}:${secs}.${ms} UTC`;
        }

        function updateClocks() {
            const localNow = new Date();
            
            // Render Local Time
            document.getElementById('localTimeDisplay').innerText = formatTimeWithMs(localNow);

            // Render Ticking GPS Time (if we have a lock)
            if (baseGpsTimeMs !== null) {
                // Calculate elapsed time to push the clock forward
                const elapsed = localNow.getTime() - fetchLocalTimeMs;
                const tickingGpsTime = new Date(baseGpsTimeMs + elapsed);
                
                // Display in strict UTC format
                document.getElementById('gpsTimeDisplay').innerText = formatUTCWithMs(tickingGpsTime);
            }
        }        
        // Run the clock updater every 40ms to make the milliseconds tick rapidly and smoothly
        setInterval(updateClocks, 40);

        // 3. Configuration Setup
        async function loadUI() {
            try {
                const res = await fetch('/api/config');
                const conf = await res.json();
                document.getElementById('mode').value = conf.mode || 'local';
                document.getElementById('host').value = conf.host || '';
                document.getElementById('user').value = conf.user || '';
                
                const modeText = conf.mode === 'local' ? 'Local System (Docker Host)' : `SSH Remote: ${conf.host}`;
                document.getElementById('connMode').innerText = modeText;
                toggleRemote();
            } catch (e) { console.error("Config load error", e); }
        }

        document.getElementById('configForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            const payload = {
                mode: document.getElementById('mode').value,
                host: document.getElementById('host').value,
                user: document.getElementById('user').value,
                password: document.getElementById('password').value
            };
            await fetch('/api/config', {
                method: 'POST', 
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(payload)
            });
            closeSettings(); 
            loadUI(); 
            fetchNTP(); 
            fetchGPS();
        });

        // 4. NTP Data Polling (2 Seconds)
        async function fetchNTP() {
            try {
                const res = await fetch('/api/ntp');
                const d = await res.json();
                
                const offsetEl = document.getElementById('sysOffset');
                if(d.error) {
                    offsetEl.innerText = "Disconnected / Error";
                    offsetEl.className = "text-xl font-mono font-bold text-red-500";
                    document.getElementById('ntpTableBody').innerHTML = `<tr><td colspan="7" class="p-4 text-red-500 whitespace-pre-wrap">${d.error}</td></tr>`;
                    return;
                }
                
                offsetEl.innerText = d.offset || 'Waiting for sync...';
                offsetEl.className = "text-xl font-mono font-bold text-green-500";
                
                document.getElementById('ntpTableBody').innerHTML = (d.sources ||[]).map(s => {
                    const isFocus = s.name.includes('PPS') || s.name.includes('GPS') || s.state.includes('*');
                    const rowCls = isFocus ? 'text-blue-600 dark:text-blue-400 font-bold bg-blue-50/10 dark:bg-blue-900/10' : '';
                    return `<tr class="${rowCls} border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <td class="p-4">${s.state}</td><td class="p-4">${s.name}</td>
                        <td class="p-4">${s.stratum}</td><td class="p-4">${s.poll}</td>
                        <td class="p-4">${s.reach}</td><td class="p-4">${s.lastrx}</td>
                        <td class="p-4">${s.last_sample}</td>
                    </tr>`;
                }).join('');
            } catch(e) {
                console.error("NTP Fetch Failed", e);
            }
        }

        // 5. GPS Data Polling (30 Seconds) & Skyplot Rendering
        let sweepTimer = 30;
        async function fetchGPS() {
            try {
                const res = await fetch('/api/gps');
                const d = await res.json();
                
                // --- CAPTURE THE RAW GPS TIME FOR THE LIVE TICKER ---
                if (d.gps_time && d.gps_time.includes('T')) {
                    const parsed = new Date(d.gps_time);
                    if (!isNaN(parsed)) {
                        baseGpsTimeMs = parsed.getTime();
                        fetchLocalTimeMs = Date.now();
                    }
                } else {
                    baseGpsTimeMs = null;
                    document.getElementById('gpsTimeDisplay').innerText = d.gps_time || 'Waiting for lock...';
                }

                let sats = d.satellites ||[];
                
                let lockedCount = 0;
                let svgContent = '';
                let tableHtml = '';

                for (let i = 0; i < sats.length; i++) {
                    let sat = sats[i];
                    if (sat.used) lockedCount++;

                    let r = 100 * (90 - sat.el) / 90;
                    let azRad = sat.az * (Math.PI / 180);
                    let x = 100 + r * Math.sin(azRad);
                    let y = 100 - r * Math.cos(azRad);
                    let color = sat.used ? '#4ade80' : '#f87171';
                    
                    if (sat.used) {
                        svgContent += `<circle cx="${x}" cy="${y}" r="4" fill="${color}" class="ping-slow" style="transform-origin: ${x}px ${y}px"></circle>`;
                    }
                    svgContent += `<circle cx="${x}" cy="${y}" r="3.5" fill="${color}"></circle>`;
                    svgContent += `<text x="${x+5}" y="${y+3}" font-size="7" font-weight="bold" fill="#ffffff">${sat.PRN}</text>`;

                    let badge = sat.used ? '<span class="text-green-500 font-bold">Locked</span>' : '<span class="text-gray-500">Visible</span>';
                    tableHtml += `<tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <td class="p-4 font-bold">PRN ${sat.PRN}</td>
                        <td class="p-4">${sat.el}°</td>
                        <td class="p-4">${sat.az}°</td>
                        <td class="p-4">${sat.ss ? sat.ss : 0} dB</td>
                        <td class="p-4">${badge}</td>
                    </tr>`;
                }

                document.getElementById('satellitesLayer').innerHTML = svgContent;
                document.getElementById('satTableBody').innerHTML = tableHtml;
                document.getElementById('satCount').innerText = lockedCount + ' Locked';
                sweepTimer = 30;
                
            } catch(e) {
                console.error("GPS Fetch Failed", e);
            }
        }

        // 6. Visual Sweep Progress Bar logic (Updates every 1s)
        setInterval(() => {
            sweepTimer--;
            if (sweepTimer < 0) sweepTimer = 0;
            document.getElementById('sweepBar').style.width = ((sweepTimer / 30) * 100) + '%';
        }, 1000);

        // 7. Initialize
        loadUI();
        fetchNTP();
        fetchGPS();
        setInterval(fetchNTP, 2000);
        setInterval(fetchGPS, 30000);
        // 8. GitHub Version Checker
        async function fetchVersion() {
            try {
                // Queries GitHub's public API for your specific repo's latest release
                const res = await fetch('https://api.github.com/repos/NightHawkATL/ntp-dashboard/releases/latest');
                if (res.ok) {
                    const data = await res.json();
                    if (data.tag_name) {
                        document.getElementById('versionDisplay').innerText = data.tag_name;
                    }
                }
            } catch (e) {
                console.log("Could not fetch version (Offline or no releases yet). Defaulting to v0.0.1");
            }
        }
        
        fetchVersion(); // Run it once on page load