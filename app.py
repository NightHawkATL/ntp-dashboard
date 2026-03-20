import os, json, subprocess
from flask import Flask, render_template, jsonify, request
import paramiko
from cryptography.fernet import Fernet

app = Flask(__name__)

APP_VERSION = "v0.0.7"

# --- Directory and File Paths ---
DATA_DIR = '/app/data'
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
KEY_FILE = os.path.join(DATA_DIR, 'secret.key')
SSH_KEY_DIR = '/app/ssh'
DEFAULT_CONFIG = '/app/config.default.json'

# Ensure the data directory exists and seed default config
os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(CONFIG_FILE) and os.path.exists(DEFAULT_CONFIG):
    import shutil
    shutil.copy2(DEFAULT_CONFIG, CONFIG_FILE)

# --- Encryption Logic ---
def get_cipher():
    if not os.path.exists(KEY_FILE):
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
    except:
        return ""

def find_ssh_key():
    """Look for a mounted SSH private key in /app/ssh/"""
    if not os.path.isdir(SSH_KEY_DIR):
        return None
    for name in ['id_rsa', 'id_ed25519', 'id_ecdsa', 'key']:
        path = os.path.join(SSH_KEY_DIR, name)
        if os.path.isfile(path):
            return path
    # Fall back to first file that isn't .pub
    for name in os.listdir(SSH_KEY_DIR):
        path = os.path.join(SSH_KEY_DIR, name)
        if os.path.isfile(path) and not name.endswith('.pub'):
            return path
    return None

# --- Config Handling ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"mode": "local", "host": "", "user": "ubuntu", "password": "", "auth": "key"}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

def run_commands_local(cmds):
    results = []
    for cmd in cmds:
        try:
            proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=5)
            if proc.returncode != 0:
                results.append(f"Error: {proc.stdout.strip()}")
            else:
                results.append(proc.stdout)
        except Exception as e:
            results.append(f"Error: {str(e)}")
    return results

def run_commands_remote(cmds, config):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    results = []
    try:
        auth_mode = config.get('auth', 'key')
        connect_kwargs = {
            'hostname': config.get('host'),
            'username': config.get('user'),
            'timeout': 10,
            'banner_timeout': 15,
            'auth_timeout': 15,
        }

        if auth_mode == 'password':
            enc_pwd = config.get('password')
            pwd = decrypt_pwd(enc_pwd) if enc_pwd else None
            connect_kwargs['password'] = pwd
            connect_kwargs['look_for_keys'] = False
        else:
            # SSH key auth
            key_path = find_ssh_key()
            if key_path:
                connect_kwargs['key_filename'] = key_path
                connect_kwargs['look_for_keys'] = False
            else:
                connect_kwargs['look_for_keys'] = True

        ssh.connect(**connect_kwargs)
        for cmd in cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            err_out = stderr.read().decode('utf-8').strip()
            std_out = stdout.read().decode('utf-8').strip()

            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                results.append(f"Error: {err_out if err_out else std_out}")
            else:
                results.append(std_out)
    except Exception as e:
        return [f"Error: {str(e)}"] * len(cmds)
    finally:
        ssh.close()
    return results

@app.route('/')
def index():
    return render_template('index.html', app_version=APP_VERSION)

@app.route('/api/ntp')
def get_ntp():
    config = load_config()
    cmds = ["chronyc tracking", "chronyc sources"]

    if config.get("mode") == "local":
        outs = run_commands_local(cmds)
    else:
        outs = run_commands_remote(cmds, config)

    tracking_out = outs[0]
    sources_out = outs[1]

    offset, sources = "Unknown", []

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
    if not err and "Error" in sources_out:
        err = sources_out

    return jsonify({"offset": offset, "sources": sources, "error": err})

@app.route('/api/gps')
def get_gps():
    config = load_config()
    cmd = ["timeout 3 gpspipe -w -n 12"]

    if config.get("mode") == "local":
        gps_out = run_commands_local(cmd)[0]
    else:
        gps_out = run_commands_remote(cmd, config)[0]

    satellites = []
    gps_time = "Waiting for lock..."

    try:
        if gps_out and "Error" not in gps_out:
            for line in gps_out.strip().split('\n'):
                if not line: continue
                try:
                    data = json.loads(line)
                    if data.get("class") == "SKY":
                        satellites = data.get("satellites", [])
                    elif data.get("class") == "TPV" and "time" in data:
                        gps_time = data.get("time")
                except: pass
    except: pass

    return jsonify({"satellites": satellites, "gps_time": gps_time})

@app.route('/api/config', methods=['GET', 'POST'])
def config_endpoint():
    if request.method == 'POST':
        new_conf = request.json
        old_conf = load_config()

        if not new_conf.get('password') and old_conf.get('password'):
            new_conf['password'] = old_conf['password']
        elif new_conf.get('password'):
            new_conf['password'] = encrypt_pwd(new_conf['password'])

        save_config(new_conf)
        return jsonify({"status": "success"})

    conf = load_config()
    conf['password'] = ""
    # Tell the UI if a key file is available
    conf['has_ssh_key'] = find_ssh_key() is not None
    return jsonify(conf)

if __name__ == '__main__':
    is_debug = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
    if is_debug:
        print("DEBUG MODE ENABLED - Detailed errors will be shown in the browser.")
    app.run(host='0.0.0.0', port=55234, debug=is_debug)
