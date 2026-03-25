import os, json, subprocess, tempfile
from flask import Flask, render_template, jsonify, request, send_from_directory
import paramiko
from cryptography.fernet import Fernet

app = Flask(__name__)

APP_VERSION = "v0.0.91"

# --- Directory and File Paths ---
DATA_DIR = '/app/data'
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
KEY_FILE = os.path.join(DATA_DIR, 'secret.key')

os.makedirs(DATA_DIR, exist_ok=True)

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

# --- Config Handling ---
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: return json.load(f)
        except: pass
    return {"mode": "local", "host": "", "user": "ubuntu", "password": "", "ssh_key": ""}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

# --- Command Execution ---
def run_commands_local(cmds):
    results =[]
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
        
        ssh.connect(config.get('host'), username=config.get('user'), password=pwd, key_filename=key_filepath, timeout=10, banner_timeout=15, auth_timeout=15, look_for_keys=False)
        
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
        return[f"Error: {str(e)}"] * len(cmds)
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
    try:
        if gps_out and "Error" not in gps_out:
            for line in gps_out.strip().split('\n'):
                if not line: continue
                try:
                    data = json.loads(line)
                    if data.get("class") == "SKY":
                        satellites = data.get("satellites",[])
                    elif data.get("class") == "TPV" and "time" in data:
                        gps_time = data.get("time")
                except: pass
    except: pass
    
    return jsonify({"satellites": satellites, "gps_time": gps_time})

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
    is_debug = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
    if is_debug:
        print("⚠️ DEBUG MODE ENABLED - Detailed errors will be shown in the browser.")
    app.run(host='0.0.0.0', port=55234, debug=is_debug)