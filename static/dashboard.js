// ── NTP Ground Station Dashboard v0.0.7 ──
// Theme-aware canvas globe + radar

// ═══════════════════════════════════════════
// 1. THEME ENGINE
// ═══════════════════════════════════════════
var THEMES = {
    'ground-station': {
        wire: [34, 211, 238],       // cyan
        locked: [52, 211, 153],     // green
        dim: [100, 116, 139],       // grey
        sweep: [34, 211, 238],
        center: [245, 166, 35],     // amber
        label: [226, 232, 240],
        labelDim: [100, 116, 139],
    },
    'daylight': {
        wire: [30, 80, 144],
        locked: [26, 122, 76],
        dim: [160, 150, 140],
        sweep: [30, 80, 144],
        center: [196, 98, 10],
        label: [26, 26, 46],
        labelDim: [140, 140, 150],
    },
    'phosphor': {
        wire: [0, 255, 65],
        locked: [0, 255, 65],
        dim: [0, 100, 28],
        sweep: [0, 255, 65],
        center: [0, 255, 65],
        label: [0, 220, 56],
        labelDim: [0, 85, 24],
    },
    'solar': {
        wire: [212, 160, 18],
        locked: [212, 160, 18],
        dim: [107, 88, 64],
        sweep: [232, 106, 32],
        center: [232, 106, 32],
        label: [232, 213, 184],
        labelDim: [107, 88, 64],
    },
    'arctic': {
        wire: [58, 124, 189],
        locked: [42, 138, 90],
        dim: [136, 152, 168],
        sweep: [58, 124, 189],
        center: [26, 138, 154],
        label: [28, 45, 63],
        labelDim: [136, 152, 168],
    },
    'amber-terminal': {
        wire: [255, 176, 0],
        locked: [255, 176, 0],
        dim: [102, 68, 0],
        sweep: [255, 176, 0],
        center: [255, 176, 0],
        label: [238, 170, 0],
        labelDim: [102, 68, 0],
    },
    'deep-space': {
        wire: [167, 139, 250],
        locked: [110, 231, 183],
        dim: [74, 68, 88],
        sweep: [167, 139, 250],
        center: [244, 114, 182],
        label: [224, 220, 232],
        labelDim: [74, 68, 88],
    }
};

var currentTheme = 'ground-station';
var TC = THEMES[currentTheme]; // theme colors shorthand

function rgb(c, a) { return 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',' + (a !== undefined ? a : 1) + ')'; }

function setTheme(name) {
    if (!THEMES[name]) return;
    currentTheme = name;
    TC = THEMES[name];
    document.documentElement.setAttribute('data-theme', name);
    localStorage.setItem('ntp-theme', name);

    // Update swatch active states
    var swatches = document.querySelectorAll('.theme-swatch');
    for (var i = 0; i < swatches.length; i++) {
        swatches[i].classList.toggle('active', swatches[i].getAttribute('data-theme') === name);
    }
}

// Init theme from localStorage
(function() {
    var saved = localStorage.getItem('ntp-theme');
    if (saved && THEMES[saved]) setTheme(saved);
})();

// Swatch click handlers
document.getElementById('themePicker').addEventListener('click', function(e) {
    var swatch = e.target.closest('.theme-swatch');
    if (swatch) setTheme(swatch.getAttribute('data-theme'));
});

// ═══════════════════════════════════════════
// 2. MODAL CONTROLS
// ═══════════════════════════════════════════
var modal = document.getElementById('settingsModal');
function openSettings() { modal.classList.add('open'); }
function closeSettings() { modal.classList.remove('open'); }
function toggleRemote() {
    var isLocal = document.getElementById('mode').value === 'local';
    document.getElementById('remoteFields').style.display = isLocal ? 'none' : 'block';
    if (!isLocal) toggleAuthFields();
}
function toggleAuthFields() {
    var isKey = document.getElementById('auth').value === 'key';
    document.getElementById('passwordFields').style.display = isKey ? 'none' : 'block';
    document.getElementById('keyStatus').style.display = isKey ? 'block' : 'none';
}
modal.addEventListener('click', function(e) { if (e.target === modal) closeSettings(); });
document.addEventListener('keydown', function(e) { if (e.key === 'Escape') closeSettings(); });

// ═══════════════════════════════════════════
// 3. CLOCKS
// ═══════════════════════════════════════════
var baseGpsTimeMs = null, fetchLocalTimeMs = null;

function formatLocalTime(d) {
    var h = d.getHours(), ap = h >= 12 ? 'PM' : 'AM';
    h = h % 12 || 12;
    return d.toLocaleDateString() + ', ' + h + ':' +
        String(d.getMinutes()).padStart(2,'0') + ':' +
        String(d.getSeconds()).padStart(2,'0') + '.' +
        String(d.getMilliseconds()).padStart(3,'0') + ' ' + ap;
}

function formatUTC(d) {
    return d.getUTCFullYear() + '-' + String(d.getUTCMonth()+1).padStart(2,'0') + '-' +
        String(d.getUTCDate()).padStart(2,'0') + '  ' +
        String(d.getUTCHours()).padStart(2,'0') + ':' +
        String(d.getUTCMinutes()).padStart(2,'0') + ':' +
        String(d.getUTCSeconds()).padStart(2,'0') + '.' +
        String(d.getUTCMilliseconds()).padStart(3,'0') + ' UTC';
}

function updateClocks() {
    var now = new Date();
    document.getElementById('localTimeDisplay').textContent = formatLocalTime(now);
    if (baseGpsTimeMs !== null) {
        document.getElementById('gpsTimeDisplay').textContent =
            formatUTC(new Date(baseGpsTimeMs + (now.getTime() - fetchLocalTimeMs)));
    }
}
setInterval(updateClocks, 80);

// ═══════════════════════════════════════════
// 4. CONFIG UI
// ═══════════════════════════════════════════
async function loadUI() {
    try {
        var res = await fetch('/api/config');
        var conf = await res.json();
        document.getElementById('mode').value = conf.mode || 'local';
        document.getElementById('host').value = conf.host || '';
        document.getElementById('user').value = conf.user || '';
        document.getElementById('auth').value = conf.auth || 'key';
        var ki = document.getElementById('keyIndicator');
        ki.innerHTML = conf.has_ssh_key
            ? '<span style="color:var(--accent-3);">&#10003;</span> SSH key detected'
            : '<span style="color:var(--accent-bad);">&#10007;</span> No key — mount at /app/ssh/';
        document.getElementById('connMode').textContent = conf.mode === 'local'
            ? 'Local System (Docker Host)'
            : 'SSH \u2192 ' + (conf.host || '???') + ' (' + (conf.auth === 'password' ? 'password' : 'key') + ')';
        toggleRemote();
    } catch (e) { console.error('Config load error', e); }
}

document.getElementById('configForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            mode: document.getElementById('mode').value,
            host: document.getElementById('host').value,
            user: document.getElementById('user').value,
            auth: document.getElementById('auth').value,
            password: document.getElementById('password').value
        })
    });
    closeSettings(); loadUI(); fetchNTP(); fetchGPS();
});

// ═══════════════════════════════════════════
// 5. CANVAS SETUP
// ═══════════════════════════════════════════
var globeCanvas = document.getElementById('globeCanvas');
var gCtx = globeCanvas.getContext('2d');
var GW = 420, GH = 420, GCx = GW/2, GCy = GH/2, GR = 175;
var globeRotY = 0;
var globeTilt = -0.35;
var currentSats = [];

var radarCanvas = document.getElementById('radarCanvas');
var rCtx = radarCanvas.getContext('2d');
var RW = 420, RH = 420, RCx = RW/2, RCy = RH/2, RR = 190;
var sweepAngle = 0;

// DPR scaling
(function() {
    var dpr = window.devicePixelRatio || 1;
    globeCanvas.width = GW * dpr; globeCanvas.height = GH * dpr;
    globeCanvas.style.width = GW + 'px'; globeCanvas.style.height = GH + 'px';
    gCtx.scale(dpr, dpr);
    radarCanvas.width = RW * dpr; radarCanvas.height = RH * dpr;
    radarCanvas.style.width = RW + 'px'; radarCanvas.style.height = RH + 'px';
    rCtx.scale(dpr, dpr);
})();

// ═══════════════════════════════════════════
// 6. 3D GLOBE
// ═══════════════════════════════════════════
function rotX(p, a) { var c=Math.cos(a), s=Math.sin(a); return [p[0], p[1]*c-p[2]*s, p[1]*s+p[2]*c]; }
function rotY(p, a) { var c=Math.cos(a), s=Math.sin(a); return [p[0]*c+p[2]*s, p[1], -p[0]*s+p[2]*c]; }
function project(p) { var d=600, sc=d/(d+p[2]); return {x:GCx+p[0]*sc, y:GCy+p[1]*sc, z:p[2], s:sc}; }
function ll2xyz(la, lo, r) {
    var a=la*Math.PI/180, b=lo*Math.PI/180;
    return [r*Math.cos(a)*Math.sin(b), -r*Math.sin(a), r*Math.cos(a)*Math.cos(b)];
}

function drawGlobe(t) {
    gCtx.clearRect(0, 0, GW, GH);
    var angle = globeRotY + t * 0.0001;

    // Atmosphere glow
    var glow = gCtx.createRadialGradient(GCx, GCy, GR*0.9, GCx, GCy, GR*1.3);
    glow.addColorStop(0, rgb(TC.wire, 0.04));
    glow.addColorStop(1, rgb(TC.wire, 0));
    gCtx.fillStyle = glow;
    gCtx.fillRect(0, 0, GW, GH);

    // Outer rings
    gCtx.beginPath(); gCtx.arc(GCx, GCy, GR+2, 0, Math.PI*2);
    gCtx.strokeStyle = rgb(TC.wire, 0.12); gCtx.lineWidth = 2; gCtx.stroke();
    gCtx.beginPath(); gCtx.arc(GCx, GCy, GR+8, 0, Math.PI*2);
    gCtx.strokeStyle = rgb(TC.wire, 0.04); gCtx.lineWidth = 1; gCtx.stroke();

    // Longitude lines
    for (var lon = -180; lon < 180; lon += 30) {
        gCtx.beginPath(); var first = true;
        for (var lat = -90; lat <= 90; lat += 3) {
            var p = ll2xyz(lat, lon, GR); p = rotX(p, globeTilt); p = rotY(p, angle);
            var pp = project(p);
            if (p[2] > 0) {
                if (first) { gCtx.moveTo(pp.x, pp.y); first = false; }
                else gCtx.lineTo(pp.x, pp.y);
            } else {
                gCtx.strokeStyle = rgb(TC.wire, 0.08); gCtx.lineWidth = 0.5; gCtx.stroke();
                gCtx.beginPath(); first = true;
            }
        }
        gCtx.strokeStyle = rgb(TC.wire, 0.15); gCtx.lineWidth = 0.5; gCtx.stroke();
    }

    // Latitude lines
    for (var lat = -60; lat <= 60; lat += 30) {
        gCtx.beginPath(); var first = true;
        for (var lon = 0; lon <= 360; lon += 3) {
            var p = ll2xyz(lat, lon, GR); p = rotX(p, globeTilt); p = rotY(p, angle);
            var pp = project(p);
            if (p[2] > 0) {
                if (first) { gCtx.moveTo(pp.x, pp.y); first = false; }
                else gCtx.lineTo(pp.x, pp.y);
            } else {
                gCtx.strokeStyle = rgb(TC.wire, 0.08); gCtx.lineWidth = 0.5; gCtx.stroke();
                gCtx.beginPath(); first = true;
            }
        }
        gCtx.strokeStyle = rgb(TC.wire, 0.12); gCtx.lineWidth = 0.5; gCtx.stroke();
    }

    // Equator
    gCtx.beginPath(); var first = true;
    for (var lon = 0; lon <= 360; lon += 2) {
        var p = ll2xyz(0, lon, GR); p = rotX(p, globeTilt); p = rotY(p, angle);
        var pp = project(p);
        if (p[2] > 0) {
            if (first) { gCtx.moveTo(pp.x, pp.y); first = false; }
            else gCtx.lineTo(pp.x, pp.y);
        } else {
            gCtx.strokeStyle = rgb(TC.wire, 0.06); gCtx.lineWidth = 0.5; gCtx.stroke();
            gCtx.beginPath(); first = true;
        }
    }
    gCtx.strokeStyle = rgb(TC.wire, 0.25); gCtx.lineWidth = 0.8; gCtx.stroke();

    // Orbital rings
    var orbitR = GR * 1.18;
    var oTilts = [0.3, -0.4, 0.15, -0.25, 0.5, -0.1];
    for (var oi = 0; oi < oTilts.length; oi++) {
        gCtx.beginPath();
        for (var a = 0; a <= 360; a += 3) {
            var rad = a * Math.PI/180;
            var p = [orbitR*Math.cos(rad), 0, orbitR*Math.sin(rad)];
            p = rotX(p, oTilts[oi]+globeTilt); p = rotY(p, angle+oi*0.5);
            var pp = project(p);
            if (a === 0) gCtx.moveTo(pp.x, pp.y); else gCtx.lineTo(pp.x, pp.y);
        }
        gCtx.closePath();
        gCtx.strokeStyle = rgb(TC.wire, 0.06); gCtx.lineWidth = 0.4; gCtx.stroke();
    }

    // Satellites on orbits
    var satsDraw = [];
    for (var i = 0; i < currentSats.length; i++) {
        var sat = currentSats[i];
        var oi = i % oTilts.length;
        var sa = (sat.az||0)*Math.PI/180 + t*0.00015;
        var sr = GR * (1.05 + ((sat.el||45)/90)*0.25);
        var sp = [sr*Math.cos(sa), 0, sr*Math.sin(sa)];
        sp = rotX(sp, oTilts[oi]+globeTilt); sp = rotY(sp, angle+oi*0.5);
        var spp = project(sp);
        satsDraw.push({x:spp.x, y:spp.y, z:sp[2], s:spp.s, used:sat.used, prn:sat.PRN, ss:sat.ss||0});
    }
    satsDraw.sort(function(a,b) { return b.z - a.z; });

    for (var i = 0; i < satsDraw.length; i++) {
        var s = satsDraw[i];
        var sz = (s.used ? 4 : 2.5) * s.s;
        var col = s.used ? TC.locked : TC.dim;

        if (s.used) {
            // Glow
            gCtx.beginPath(); gCtx.arc(s.x, s.y, sz*3, 0, Math.PI*2);
            gCtx.fillStyle = rgb(col, 0.08); gCtx.fill();
            // Pulse
            var pulse = 1 + 0.5*Math.sin(t*0.003+i);
            gCtx.beginPath(); gCtx.arc(s.x, s.y, sz*1.8*pulse, 0, Math.PI*2);
            gCtx.strokeStyle = rgb(col, 0.3/pulse); gCtx.lineWidth = 0.5; gCtx.stroke();
        }
        gCtx.beginPath(); gCtx.arc(s.x, s.y, sz, 0, Math.PI*2);
        gCtx.fillStyle = rgb(col, s.used ? 1 : 0.6); gCtx.fill();

        if (s.s > 0.7) {
            gCtx.font = (s.used ? '600 ' : '400 ') + '9px IBM Plex Mono, monospace';
            gCtx.fillStyle = rgb(s.used ? TC.label : TC.labelDim, s.used ? 0.8 : 0.5);
            gCtx.textAlign = 'left';
            gCtx.fillText(s.prn, s.x+sz+3, s.y+3);
        }
    }

    // Center dot
    var cg = gCtx.createRadialGradient(GCx, GCy, 0, GCx, GCy, 8);
    cg.addColorStop(0, rgb(TC.center, 0.3)); cg.addColorStop(1, rgb(TC.center, 0));
    gCtx.fillStyle = cg; gCtx.fillRect(GCx-8, GCy-8, 16, 16);
    gCtx.beginPath(); gCtx.arc(GCx, GCy, 2, 0, Math.PI*2);
    gCtx.fillStyle = rgb(TC.center, 1); gCtx.fill();
}

// ═══════════════════════════════════════════
// 7. RADAR SCOPE
// ═══════════════════════════════════════════
function drawRadar(t) {
    rCtx.clearRect(0, 0, RW, RH);

    // Background
    var bg = rCtx.createRadialGradient(RCx, RCy, 0, RCx, RCy, RR);
    bg.addColorStop(0, rgb(TC.wire, 0.03));
    bg.addColorStop(1, 'rgba(0,0,0,0.01)');
    rCtx.beginPath(); rCtx.arc(RCx, RCy, RR, 0, Math.PI*2);
    rCtx.fillStyle = bg; rCtx.fill();

    // Outer ring
    rCtx.beginPath(); rCtx.arc(RCx, RCy, RR, 0, Math.PI*2);
    rCtx.strokeStyle = rgb(TC.wire, 0.2); rCtx.lineWidth = 1.5; rCtx.stroke();

    // Elevation rings
    [RR*2/3, RR/3].forEach(function(r) {
        rCtx.beginPath(); rCtx.arc(RCx, RCy, r, 0, Math.PI*2);
        rCtx.strokeStyle = rgb(TC.wire, 0.07); rCtx.lineWidth = 0.5;
        rCtx.setLineDash([3,5]); rCtx.stroke(); rCtx.setLineDash([]);
    });

    // Crosshairs
    for (var ci = 0; ci < 8; ci++) {
        var ca = ci * Math.PI/4;
        rCtx.beginPath(); rCtx.moveTo(RCx, RCy);
        rCtx.lineTo(RCx+RR*Math.sin(ca), RCy-RR*Math.cos(ca));
        rCtx.strokeStyle = rgb(TC.wire, 0.08); rCtx.lineWidth = 0.5; rCtx.stroke();
    }

    // Labels
    rCtx.font = '500 10px IBM Plex Mono, monospace';
    rCtx.fillStyle = rgb(TC.label, 0.25); rCtx.textAlign = 'center';
    rCtx.fillText('N', RCx, RCy-RR-8);
    rCtx.fillText('S', RCx, RCy+RR+15);
    rCtx.fillText('E', RCx+RR+12, RCy+4);
    rCtx.fillText('W', RCx-RR-12, RCy+4);

    rCtx.font = '400 8px IBM Plex Mono, monospace';
    rCtx.fillStyle = rgb(TC.label, 0.12);
    rCtx.fillText('30\u00b0', RCx+RR*2/3+2, RCy-4);
    rCtx.fillText('60\u00b0', RCx+RR/3+2, RCy-4);

    // Sweep
    sweepAngle = (t * 0.0008) % (Math.PI*2);
    for (var ti = 0; ti < 20; ti++) {
        var ta = sweepAngle - 0.5*(ti/20);
        rCtx.beginPath(); rCtx.moveTo(RCx, RCy);
        rCtx.arc(RCx, RCy, RR, ta-0.03, ta+0.03); rCtx.closePath();
        rCtx.fillStyle = rgb(TC.sweep, 0.08*(1-ti/20)); rCtx.fill();
    }
    var sx = RCx+RR*Math.sin(sweepAngle), sy = RCy-RR*Math.cos(sweepAngle);
    rCtx.beginPath(); rCtx.moveTo(RCx, RCy); rCtx.lineTo(sx, sy);
    var sg = rCtx.createLinearGradient(RCx, RCy, sx, sy);
    sg.addColorStop(0, rgb(TC.sweep, 0.5)); sg.addColorStop(1, rgb(TC.sweep, 0.1));
    rCtx.strokeStyle = sg; rCtx.lineWidth = 1; rCtx.stroke();

    // Satellites
    for (var i = 0; i < currentSats.length; i++) {
        var sat = currentSats[i];
        var elR = RR*(90-sat.el)/90;
        var azR = sat.az*Math.PI/180;
        var sx = RCx+elR*Math.sin(azR), sy = RCy-elR*Math.cos(azR);
        var col = sat.used ? TC.locked : TC.dim;

        if (sat.used) {
            var gg = rCtx.createRadialGradient(sx, sy, 0, sx, sy, 12);
            gg.addColorStop(0, rgb(col, 0.15)); gg.addColorStop(1, rgb(col, 0));
            rCtx.fillStyle = gg; rCtx.fillRect(sx-12, sy-12, 24, 24);

            var ping = 1+0.6*Math.sin(t*0.003+i*0.7);
            rCtx.beginPath(); rCtx.arc(sx, sy, 5*ping, 0, Math.PI*2);
            rCtx.strokeStyle = rgb(col, 0.25/ping); rCtx.lineWidth = 0.6; rCtx.stroke();
        }

        rCtx.beginPath(); rCtx.arc(sx, sy, sat.used?3.5:2, 0, Math.PI*2);
        rCtx.fillStyle = rgb(col, sat.used?1:0.5); rCtx.fill();

        rCtx.font = (sat.used?'600 ':'400 ')+'8px IBM Plex Mono, monospace';
        rCtx.fillStyle = rgb(sat.used?TC.label:TC.labelDim, sat.used?0.7:0.4);
        rCtx.textAlign = 'left';
        rCtx.fillText(sat.PRN, sx+6, sy+3);
    }

    // Center
    rCtx.beginPath(); rCtx.arc(RCx, RCy, 2.5, 0, Math.PI*2);
    rCtx.fillStyle = rgb(TC.sweep, 0.5); rCtx.fill();
}

// ═══════════════════════════════════════════
// 8. ANIMATION LOOP
// ═══════════════════════════════════════════
function animate(t) { drawGlobe(t); drawRadar(t); requestAnimationFrame(animate); }
requestAnimationFrame(animate);

// ═══════════════════════════════════════════
// 9. NTP POLLING
// ═══════════════════════════════════════════
function esc(s) { var el=document.createElement('span'); el.textContent=String(s); return el.innerHTML; }

async function fetchNTP() {
    try {
        var res = await fetch('/api/ntp');
        var d = await res.json();
        var oe = document.getElementById('sysOffset');
        var dot = document.getElementById('statusDot');
        if (d.error) {
            oe.textContent = 'Disconnected'; oe.style.color = 'var(--accent-bad)'; oe.className = 'metric-value';
            dot.classList.add('error');
            document.getElementById('ntpTableBody').innerHTML =
                '<tr><td colspan="7" style="padding:1.2rem;color:var(--accent-bad);">' + esc(d.error) + '</td></tr>';
            return;
        }
        dot.classList.remove('error');
        oe.textContent = d.offset || 'Waiting\u2026'; oe.style.color = ''; oe.className = 'metric-value highlight';

        document.getElementById('ntpTableBody').innerHTML = (d.sources||[]).map(function(s) {
            var a = s.state.includes('*')||s.name.includes('PPS')||s.name.includes('GPS');
            return '<tr class="'+(a?'row-active':'')+'"><td>'+esc(s.state)+'</td><td>'+esc(s.name)+
                '</td><td>'+esc(s.stratum)+'</td><td>'+esc(s.poll)+'</td><td>'+esc(s.reach)+
                '</td><td>'+esc(s.lastrx)+'</td><td>'+esc(s.last_sample)+'</td></tr>';
        }).join('') || '<tr><td colspan="7" style="padding:1.2rem;text-align:center;color:var(--text-tertiary);">No sources</td></tr>';
    } catch(e) { console.error('NTP fail', e); }
}

// ═══════════════════════════════════════════
// 10. GPS POLLING
// ═══════════════════════════════════════════
var sweepTimer = 30;

async function fetchGPS() {
    try {
        var res = await fetch('/api/gps');
        var d = await res.json();

        if (d.gps_time && d.gps_time.includes('T')) {
            var p = new Date(d.gps_time);
            if (!isNaN(p)) { baseGpsTimeMs = p.getTime(); fetchLocalTimeMs = Date.now(); }
        } else {
            baseGpsTimeMs = null;
            document.getElementById('gpsTimeDisplay').textContent = d.gps_time || 'Acquiring lock\u2026';
        }

        currentSats = d.satellites || [];
        var locked = 0, rows = [];
        for (var i = 0; i < currentSats.length; i++) {
            var s = currentSats[i];
            if (s.used) locked++;
            var snr = s.ss||0, pct = Math.min(snr/50*100, 100);
            var sc = snr>30 ? 'var(--accent-3)' : snr>15 ? 'var(--accent-2)' : 'var(--accent-bad)';
            rows.push('<tr><td style="font-weight:600;">PRN '+esc(s.PRN)+'</td><td>'+s.el+'\u00b0</td><td>'+s.az+
                '\u00b0</td><td><span class="snr-bar-bg"><span class="snr-bar-fill" style="width:'+pct+'%;background:'+sc+
                '"></span></span>'+snr+' dB</td><td>'+(s.used?'<span class="sat-status-locked">LOCKED</span>':
                '<span class="sat-status-visible">visible</span>')+'</td></tr>');
        }

        document.getElementById('satTableBody').innerHTML = rows.join('') ||
            '<tr><td colspan="5" style="padding:1.2rem;text-align:center;color:var(--text-tertiary);">Waiting\u2026</td></tr>';
        document.getElementById('satCountNum').textContent = locked;
        var badge = currentSats.length + ' tracked \u00b7 ' + locked + ' locked';
        document.getElementById('satCount').textContent = badge;
        document.getElementById('satCountBadge').textContent = badge;
        sweepTimer = 30;
    } catch(e) { console.error('GPS fail', e); }
}

// Sweep bar
setInterval(function() {
    sweepTimer--; if (sweepTimer<0) sweepTimer=0;
    document.getElementById('sweepBar').style.width = ((sweepTimer/30)*100)+'%';
}, 1000);

// ═══════════════════════════════════════════
// 11. INIT
// ═══════════════════════════════════════════
loadUI(); fetchNTP(); fetchGPS();
setInterval(fetchNTP, 2000);
setInterval(fetchGPS, 30000);
