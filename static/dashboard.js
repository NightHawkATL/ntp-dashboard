// --- Light/Dark/System Mode Logic ---
function setThemeMode(mode) {
    localStorage.themeMode = mode;
    const isDark = mode === 'dark' || (mode === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
    document.documentElement.classList.toggle('dark', isDark);['light', 'system', 'dark'].forEach(m => {
        const btn = document.getElementById(`btn-${m}`);
        if (btn) {
            if (m === mode) {
                btn.classList.add('bg-white', 'dark:bg-gray-700', 'shadow-sm', 'text-primary-500');
                btn.classList.remove('text-gray-500', 'hover:text-gray-900', 'dark:hover:text-gray-100');
            } else {
                btn.classList.remove('bg-white', 'dark:bg-gray-700', 'shadow-sm', 'text-primary-500');
                btn.classList.add('text-gray-500', 'hover:text-gray-900', 'dark:hover:text-gray-100');
            }
        }
    });
}
setThemeMode(localStorage.themeMode || 'system');
window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if (localStorage.themeMode === 'system') setThemeMode('system');
});

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
        
        // Show asterisks if a key is saved, otherwise leave blank
        document.getElementById('ssh_key').value = conf.ssh_key ? '********' : '';
        
        const modeText = conf.mode === 'local' ? 'Local System (Docker Host)' : `SSH Remote: ${conf.host}`;
        document.getElementById('connMode').innerText = modeText;
        toggleRemote();
    } catch (e) { console.error("Config load error", e); }
}

// Replace your existing configForm submit listener with this:
document.getElementById('configForm').addEventListener('submit', async (e) => {
    // 1. Stop the browser from reloading the page!
    e.preventDefault();
    
    try {
        // 2. Safely check if the SSH Key box exists in the HTML
        const sshKeyEl = document.getElementById('ssh_key');
        let sshKeyVal = sshKeyEl ? sshKeyEl.value : '';
        if (sshKeyVal === '********') sshKeyVal = '';

        const payload = {
            mode: document.getElementById('mode').value,
            host: document.getElementById('host').value,
            user: document.getElementById('user').value,
            password: document.getElementById('password').value,
            ssh_key: sshKeyVal
        };
        
        // 3. Send to Python
        const res = await fetch('/api/config', {
            method: 'POST', 
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) throw new Error("Server rejected the save request.");
        
        closeSettings(); 
        loadUI(); 
        fetchNTP(); 
        fetchGPS();
        
    } catch (err) {
        console.error(err);
        alert("Configuration failed to save! Check the console for errors.");
    }
});

        // 4. NTP Data Polling (2 Seconds)
        async function fetchNTP() {
            try {
                const res = await fetch('/api/ntp', { cache: 'no-store' });
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
                    const rowCls = isFocus ? 'text-primary-600 dark:text-primary-400 font-bold bg-primary-50/10 dark:bg-primary-900/10' : '';
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
                const res = await fetch('/api/gps', { cache: 'no-store' });
                const d = await res.json();
                const satTableBody = document.getElementById('satTableBody');
                const satCountEl = document.getElementById('satCount');

                if (d.error) {
                    baseGpsTimeMs = null;
                    document.getElementById('gpsTimeDisplay').innerText = d.gps_time || 'GPS unavailable';
                    document.getElementById('satellitesLayer').innerHTML = '';
                    // Render error as plain text to avoid HTML/script injection
                    satTableBody.innerHTML = '';
                    const errorRow = document.createElement('tr');
                    const errorCell = document.createElement('td');
                    errorCell.colSpan = 5;
                    errorCell.className = 'p-4 text-red-500 whitespace-pre-wrap';
                    errorCell.textContent = d.error;
                    errorRow.appendChild(errorCell);
                    satTableBody.appendChild(errorRow);
                    satCountEl.innerText = 'Unavailable';
                    sweepTimer = 30;
                    return;
                }
                
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
                satTableBody.innerHTML = tableHtml;
                satCountEl.innerText = lockedCount + ' Locked';
                sweepTimer = 30;
                
            } catch(e) {
                console.error("GPS Fetch Failed", e);
                baseGpsTimeMs = null;
                document.getElementById('gpsTimeDisplay').innerText = 'GPS unavailable';
                document.getElementById('satellitesLayer').innerHTML = '';
                document.getElementById('satTableBody').innerHTML = '<tr><td colspan="5" class="p-4 text-red-500">Failed to communicate with API.</td></tr>';
                document.getElementById('satCount').innerText = 'Unavailable';
            }
        }

// --- NTP Clients Logic & Sorting ---
const clientsModal = document.getElementById('clientsModal');
let clientsData =[];

function openClientsModal() { 
    clientsModal.classList.remove('hidden'); 
    fetchClients(); // Immediately load data when opened
}

function closeClientsModal() { 
    clientsModal.classList.add('hidden'); 
}

async function fetchClients() {
    const tbody = document.getElementById('clientsTableBody');
    tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-gray-500 animate-pulse">Fetching clients...</td></tr>';
    
    try {
        const res = await fetch('/api/clients');
        const d = await res.json();
        
        if (d.error) {
            tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-red-500 whitespace-pre-wrap">${d.error}</td></tr>`;
            return;
        }
        
        clientsData = d.clients ||[];
        renderClientsTable();
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="4" class="p-4 text-red-500">Failed to communicate with API.</td></tr>`;
        console.error("Clients Fetch Failed", e);
    }
}

// Helper to convert IPs to proper integers so "10.0.0.2" comes before "10.0.0.10"
function ipToInt(ip) {
    return ip.split('.').reduce((acc, octet) => (acc << 8) + parseInt(octet, 10), 0) >>> 0;
}

// Helper to convert Chrony's weird time formats ("45", "2m", "10h", "10d") into raw seconds for sorting
function parseLastSeen(val) {
    if (!val || val === '-') return Infinity;
    let num = parseFloat(val);
    if (val.includes('s')) return num;
    if (val.includes('m')) return num * 60;
    if (val.includes('h')) return num * 3600;
    if (val.includes('d')) return num * 86400;
    if (val.includes('y')) return num * 31536000;
    return num; 
}

function renderClientsTable() {
    const tbody = document.getElementById('clientsTableBody');
    const sortMode = document.getElementById('clientSort').value;
    
    if (clientsData.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" class="p-4 text-center text-gray-500">No active clients found.</td></tr>';
        return;
    }

    // Sort the Array based on User Selection
    let sortedData = [...clientsData];
    sortedData.sort((a, b) => {
        if (sortMode === 'hits_desc') {
            return parseInt(b.ntp_hits) - parseInt(a.ntp_hits);
        } else if (sortMode === 'ip_asc') {
            if (a.ip.includes('.') && b.ip.includes('.')) {
                return ipToInt(a.ip) - ipToInt(b.ip); // Standard IPv4 Sort
            }
            return a.ip.localeCompare(b.ip); // Fallback for IPv6 / Hostnames
        } else if (sortMode === 'recent') {
            return parseLastSeen(a.last_seen) - parseLastSeen(b.last_seen);
        }
        return 0;
    });

    // Inject the sorted data using the standard primary Tailwind classes
    tbody.innerHTML = sortedData.map(c => `
        <tr class="border-b dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
            <td class="p-4 font-bold text-primary-600 dark:text-primary-400">${c.ip}</td>
            <td class="p-4">${c.ntp_hits}</td>
            <td class="p-4">${c.ntp_drops}</td>
            <td class="p-4">${c.last_seen}</td>
        </tr>
    `).join('');
}

        // 6. Visual Sweep Progress Bar logic (Updates every 1s)
        setInterval(() => {
            sweepTimer--;
            if (sweepTimer < 0) sweepTimer = 0;
            document.getElementById('sweepBar').style.width = ((sweepTimer / 30) * 100) + '%';
        }, 1000);

        // 7. Initialize
        let ntpIntervalId = null;
        let gpsIntervalId = null;

        function startPolling() {
            if (ntpIntervalId === null) {
                ntpIntervalId = setInterval(fetchNTP, 2000);
            }
            if (gpsIntervalId === null) {
                gpsIntervalId = setInterval(fetchGPS, 30000);
            }
        }

        let lastRefreshTime = 0;
        const REFRESH_DEBOUNCE_MS = 1000;

        function refreshNow() {
            const now = Date.now();
            if (now - lastRefreshTime < REFRESH_DEBOUNCE_MS) return;
            lastRefreshTime = now;
            fetchNTP();
            fetchGPS();
        }

        loadUI();
        refreshNow();
        startPolling();

        // Force fresh data when the tab becomes active again.
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                refreshNow();
                startPolling();
            }
        });

        window.addEventListener('focus', refreshNow);
        window.addEventListener('pageshow', (event) => {
            if (event.persisted) {
                refreshNow();
            }
        });
        window.addEventListener('online', refreshNow);
       
        // 9. Register PWA Service Worker
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                // Capture whether a controller already exists before registering,
                // so controllerchange only triggers a reload when upgrading (not on first install).
                const hadController = !!navigator.serviceWorker.controller;

                let isRefreshing = false;
                navigator.serviceWorker.addEventListener('controllerchange', () => {
                    if (isRefreshing || !hadController) {
                        return;
                    }
                    isRefreshing = true;
                    window.location.reload();
                });

                navigator.serviceWorker.register('/sw.js')
                    .then(reg => {
                        console.log('PWA Service Worker Registered!', reg.scope);

                        if (reg.waiting) {
                            reg.waiting.postMessage({ type: 'SKIP_WAITING' });
                        }

                        reg.addEventListener('updatefound', () => {
                            const newWorker = reg.installing;
                            if (!newWorker) {
                                return;
                            }

                            newWorker.addEventListener('statechange', () => {
                                if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
                                    newWorker.postMessage({ type: 'SKIP_WAITING' });
                                }
                            });
                        });
                    })
                    .catch(err => console.error('PWA Registration Failed!', err));
            });
        }

// --- 10. Theme Dropdown Logic ---
const themesList =[
    { id: 'blue', name: 'Default Blue', color: '#3b82f6' },
    { id: 'emerald', name: 'Emerald Green', color: '#10b981' },
    { id: 'rose', name: 'Rose Red', color: '#f43f5e' },
    { id: 'orange', name: 'Sunset Orange', color: '#f97316' },
    { id: 'amber', name: 'Amber Yellow', color: '#f59e0b' },
    { id: 'violet', name: 'Violet Purple', color: '#8b5cf6' },
    { id: 'midnight', name: 'Midnight Black', color: '#64748b' },
    { id: 'cyan', name: 'Cyan', color: '#06b6d4' },
    { id: 'fuchsia', name: 'Fuchsia', color: '#d946ef' },
    { id: 'lime', name: 'Lime', color: '#84cc16' },
    { id: 'indigo', name: 'Indigo', color: '#6366f1' },
    { id: 'teal', name: 'Teal', color: '#14b8a6' }
];

function renderThemeMenu() {
    const menu = document.getElementById('themeMenu');
    const currentTheme = localStorage.themeColor || 'blue';
    
    // Build the dropdown list (matches the screenshot style)
    menu.innerHTML = themesList.map(t => {
        const isSelected = t.id === currentTheme;
        return `
        <button onclick="applyColorPalette('${t.id}')" class="w-full text-left px-4 py-2.5 flex items-center gap-3 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors ${isSelected ? 'bg-gray-50 dark:bg-gray-800/50' : ''}">
            <span class="w-3 h-3 rounded-full" style="background-color: ${t.color}"></span>
            <span class="flex-1 text-gray-700 dark:text-gray-200">${t.name}</span>
            ${isSelected ? '<svg class="w-4 h-4 text-gray-500 dark:text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>' : ''}
        </button>
        `;
    }).join('');
}

function toggleThemeMenu(event) {
    if(event) event.stopPropagation();
    const menu = document.getElementById('themeMenu');
    menu.classList.toggle('hidden');
    if(!menu.classList.contains('hidden')) {
        renderThemeMenu();
    }
}

// Close the dropdown when clicking anywhere else on the screen
document.addEventListener('click', (event) => {
    const wrapper = document.getElementById('themeDropdownWrapper');
    const menu = document.getElementById('themeMenu');
    if (wrapper && !wrapper.contains(event.target)) {
        menu.classList.add('hidden');
    }
});

function applyColorPalette(colorId) {
    localStorage.themeColor = colorId;
    document.documentElement.setAttribute('data-theme', colorId);
    
    // Update the PWA theme-color meta tag instantly
    const themeColorMeta = document.querySelector('meta[name="theme-color"]');
    const activeTheme = themesList.find(t => t.id === colorId);
    if (themeColorMeta && activeTheme) {
        themeColorMeta.setAttribute("content", activeTheme.color);
    }
    
    renderThemeMenu(); // Re-render to move the checkmark
}

// Initialize on page load
applyColorPalette(localStorage.themeColor || 'blue');

// --- GitHub Update Checker ---
async function checkForUpdates() {
    try {
        // Grab the running version that Python injected into the HTML
        const currentVersion = document.getElementById('versionDisplay').innerText.trim();
        
        // Ask GitHub what the newest released tag is
        const res = await fetch('https://api.github.com/repos/NightHawkATL/ntp-dashboard/releases/latest');
        if (res.ok) {
            const data = await res.json();
            const latestVersion = data.tag_name;
            
            // If GitHub's newest version doesn't match the running version, show the badge!
            if (latestVersion && latestVersion !== currentVersion) {
                const badge = document.getElementById('updateBadge');
                badge.innerText = `Update Available: ${latestVersion}`;
                badge.classList.remove('hidden');
            }
        }
    } catch (e) {
        console.log("Could not check for updates (Offline).");
    }
}
checkForUpdates(); // Run once when the dashboard loads
