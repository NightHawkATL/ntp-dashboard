import os, json, subprocess, tempfile, logging
from flask import Flask, render_template, jsonify, request, send_from_directory
import paramiko
from cryptography.fernet import Fernet

LOG_LEVEL_NAME = os.environ.get('LOG_LEVEL', 'INFO').upper()
LOG_LEVEL = getattr(logging, LOG_LEVEL_NAME, logging.INFO)

logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    force=True
)
log = logging.getLogger(__name__)

if not hasattr(logging, LOG_LEVEL_NAME):
    log.warning('Invalid LOG_LEVEL=%s; defaulting to INFO', LOG_LEVEL_NAME)

app = Flask(__name__)
app.logger.setLevel(LOG_LEVEL)
logging.getLogger('werkzeug').setLevel(LOG_LEVEL)

APP_VERSION = os.environ.get("APP_VERSION", "dev")

# --- Directory and File Paths ---
DATA_DIR = '/app/data'
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
KEY_FILE = os.path.join(DATA_DIR, 'secret.key')

os.makedirs(DATA_DIR, exist_ok=True)

# --- Encryption Logic ---
def get_cipher():
    if not os.path.exists(KEY_FILE):
        log.info('Encryption key not found; generating %s', KEY_FILE)
        key = Fernet.generate_key()
        with open(KEY_FILE, 'wb') as key_file:
            key_file.write(key)
    else:
        with open(KEY_FILE, 'rb') as key_file:
            key = key_file.read()
    return Fernet(key)

def encrypt_pwd(pwd):
    if not pwd: return ""
    return get_cipher().encrypt(pwd.encode()).decode()

def decrypt_pwd(encrypted_pwd):
    if not encrypted_pwd: return ""
    try:
        return get_cipher().decrypt(encrypted_pwd.encode()).decode()
    except Exception as e:
        log.error('Failed to decrypt stored credential: %s', e)
        return ""

# --- Config Handling ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except Exception as e:
            log.error('Failed to read config file %s: %s', CONFIG_FILE, e)
    return {"mode": "local", "host": "", "user": "ubuntu", "password": "", "ssh_key": ""}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)
    log.info('Configuration saved; mode=%r host=%r', config.get('mode'), config.get('host') or 'local')

# --- Command Execution ---
def run_commands_local(cmds):
    results =[]
    for cmd in cmds:
        try:
            proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5)
            if proc.returncode != 0:
                log.warning('Local command failed (rc=%s): %s :: %s', proc.returncode, cmd, proc.stdout.strip())
                results.append(f"Error: {proc.stdout.strip()}")
            else:
                results.append(proc.stdout)
        except Exception as e:
            log.exception('Local command exception for: %s', cmd)
            results.append("Error: An internal error occurred while executing a local command.")
    return results

def run_commands_remote(cmds, config):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    results =[]
    key_filepath = None
    
    try:
        # Decrypt password and SSH key
        enc_pwd = config.get('password')
        pwd = decrypt_pwd(enc_pwd) if enc_pwd else None
        
        enc_key = config.get('ssh_key')
        ssh_key_str = decrypt_pwd(enc_key) if enc_key else None
        
        # Write SSH key to a temp file if it exists
        if ssh_key_str:
            if not ssh_key_str.endswith('\n'):
                ssh_key_str += '\n'
            fd, key_filepath = tempfile.mkstemp()
            with os.fdopen(fd, 'w') as f:
                f.write(ssh_key_str)
        
        log.info('Opening SSH connection to host=%s user=%s', config.get('host'), config.get('user'))
        ssh.connect(config.get('host'), username=config.get('user'), password=pwd, key_filename=key_filepath, timeout=10, banner_timeout=15, auth_timeout=15, look_for_keys=False)
        
        for cmd in cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            err_out = stderr.read().decode('utf-8').strip()
            std_out = stdout.read().decode('utf-8').strip()
            
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                log.warning('Remote command failed on host=%s (rc=%s): %s :: %s', config.get('host'), exit_status, cmd, err_out if err_out else std_out)
                results.append(f"Error: {err_out if err_out else std_out}")
            else:
                results.append(std_out)
    except Exception as e:
        log.exception('Remote command execution failed for host=%s', config.get('host'))
        return ["Error: An internal error occurred while executing a remote command."] * len(cmds)
    finally:
        if key_filepath and os.path.exists(key_filepath):
            os.remove(key_filepath)
        ssh.close()
    return results

# --- PWA Routes ---
@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

# --- API Routes ---
@app.route('/')
def index(): 
    return render_template('index.html', app_version=APP_VERSION)

@app.route('/api/ntp')
def get_ntp():
    config = load_config()
    cmds =["chronyc tracking", "chronyc sources"]
    
    if config.get("mode") == "local":
        outs = run_commands_local(cmds)
    else:
        outs = run_commands_remote(cmds, config)
        
    tracking_out = outs[0]
    sources_out = outs[1]
    
    offset, sources = "Unknown",[]
    
    for line in tracking_out.split('\n'):
        if "System time" in line or "Last offset" in line:
            offset = line.split(':', 1)[-1].strip()
            break
            
    lines = sources_out.strip().split('\n')
    start_idx = next((i + 1 for i, l in enumerate(lines) if set(l.strip()) == {'='}), -1)
    if start_idx != -1:
        for line in lines[start_idx:]:
            if not line.strip(): continue
            parts = line.split()
            if len(parts) >= 6:
                sources.append({"state": parts[0], "name": parts[1], "stratum": parts[2], "poll": parts[3], "reach": parts[4], "lastrx": parts[5], "last_sample": " ".join(parts[6:])})
    
    err = tracking_out if "Error" in tracking_out else None
    if not err and "Error" in sources_out: err = sources_out
    if err:
        log.warning('NTP API returned error in %s mode: %s', config.get('mode'), err)
    
    return jsonify({"offset": offset, "sources": sources, "error": err})

@app.route('/api/gps')
def get_gps():
    config = load_config()
    cmd = ["timeout 3 gpspipe -w -n 12"]
    
    if config.get("mode") == "local":
        gps_out = run_commands_local(cmd)[0]
    else:
        gps_out = run_commands_remote(cmd, config)[0]
        
    satellites =[]
    gps_time = "Waiting for lock..."
    error = None
    if gps_out and (gps_out.startswith('Error:') or "command not found" in gps_out.lower()):
        error = gps_out
        if config.get("mode") == "local" and "gpspipe" in gps_out and "not found" in gps_out.lower():
            error = "Local GPS support is not installed in this image. Rebuild with INSTALL_GPSD_CLIENTS=true to enable gpspipe, or switch to Remote mode."
            gps_time = "Local GPS support not installed"

    if gps_out and not error:
        for line in gps_out.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                if data.get("class") == "SKY":
                    satellites = data.get("satellites", [])
                elif data.get("class") == "TPV" and "time" in data:
                    gps_time = data.get("time")
            except json.JSONDecodeError as e:
                log.debug('GPS: could not parse line as JSON: %s', e)
            except Exception as e:
                log.exception('GPS: unexpected error parsing line: %s', e)
                error = "GPS parsing error occurred"

    if error:
        log.warning('GPS API returned error in %s mode: %s', config.get('mode'), error)
    return jsonify({"satellites": satellites, "gps_time": gps_time, "error": error})

@app.route('/api/clients')
def get_clients():
    config = load_config()
    
    if config.get("mode") == "local":
        cmd = ["chronyc -N clients -k"]
        outs = run_commands_local(cmd)
    else:
        cmd =["sudo chronyc -N clients -k"]
        outs = run_commands_remote(cmd, config)
        
    out = outs[0]
    clients =[]
    
    if out and "Error" not in out and "command not found" not in out.lower():
        lines = out.strip().split('\n')
        start_idx = -1
        for i, line in enumerate(lines):
            if set(line.strip()) == {'='}:
                start_idx = i + 1
                break
        
        if start_idx != -1:
            for line in lines[start_idx:]:
                if not line.strip(): continue
                parts = line.split()
                if len(parts) >= 6:
                    clients.append({
                        "ip": parts[0],
                        "ntp_hits": parts[1],
                        "ntp_drops": parts[2],
                        "last_seen": parts[5]
                    })
                    
    err = out if ("Error" in out or "command not found" in out.lower()) else None
    if err:
        log.warning('Clients API returned error in %s mode: %s', config.get('mode'), err)
    return jsonify({"clients": clients, "error": err})

@app.route('/api/config', methods=['GET', 'POST'])
def config_endpoint():
    if request.method == 'POST':
        new_conf = request.json
        old_conf = load_config()
        
        if not new_conf.get('password') and old_conf.get('password'):
            new_conf['password'] = old_conf['password']
        elif new_conf.get('password'):
            new_conf['password'] = encrypt_pwd(new_conf['password'])
            
        if not new_conf.get('ssh_key') and old_conf.get('ssh_key'):
            new_conf['ssh_key'] = old_conf['ssh_key']
        elif new_conf.get('ssh_key'):
            new_conf['ssh_key'] = encrypt_pwd(new_conf['ssh_key'])
            
        save_config(new_conf)
        return jsonify({"status": "success"})
    
    conf = load_config()
    conf['password'] = ""
    conf['ssh_key'] = "saved" if conf.get('ssh_key') else ""
    return jsonify(conf)

if __name__ == '__main__':
    debug_mode_env = os.environ.get('DEBUG_MODE', '').lower()
    is_debug = debug_mode_env == 'true' or LOG_LEVEL_NAME == 'DEBUG'
    startup_config = load_config()
    log.info('NTP Dashboard %s starting on port 55234; mode=%s host=%s log_level=%s', APP_VERSION, startup_config.get('mode'), startup_config.get('host') or 'local', LOG_LEVEL_NAME)
    if is_debug:
        log.warning('DEBUG MODE ENABLED - detailed errors and tracebacks will be available in container logs and browser responses. Do not use in production.')
    app.run(host='0.0.0.0', port=55234, debug=is_debug)
