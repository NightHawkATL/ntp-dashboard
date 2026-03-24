import os, json, subprocess
from flask import Flask, render_template, jsonify, request, send_from_directory
import paramiko
from cryptography.fernet import Fernet

app = Flask(__name__)

APP_VERSION = "v0.0.9"          # <--- NEW: Hard-code your version here

# --- NEW: Directory and File Paths ---
DATA_DIR = '/app/data'
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
KEY_FILE = os.path.join(DATA_DIR, 'secret.key')

# Ensure the data directory exists
os.makedirs(DATA_DIR, exist_ok=True)

# --- NEW: Encryption Logic ---
def get_cipher():
    # If a key doesn't exist, generate one and save it
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
    return {"mode": "local", "host": "", "user": "ubuntu", "password": ""}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f: json.dump(config, f)

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
    try:
        # Decrypt the password before sending it to SSH
        enc_pwd = config.get('password')
        pwd = decrypt_pwd(enc_pwd) if enc_pwd else None
        
        ssh.connect(config.get('host'), username=config.get('user'), password=pwd, timeout=10, banner_timeout=15, auth_timeout=15, look_for_keys=False)
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
        ssh.close()
    return results
    
@app.route('/')
def index(): 
    # Pass the version variable directly into the HTML file
    return render_template('index.html', app_version=APP_VERSION)

@app.route('/manifest.json')
def manifest():
    return send_from_directory('static', 'manifest.json')

@app.route('/sw.js')
def service_worker():
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')

@app.route('/api/ntp')
def get_ntp():
    config = load_config()
    cmds = ["chronyc tracking", "chronyc sources"]
    
    # Execute commands based on mode
    if config.get("mode") == "local":
        outs = run_commands_local(cmds)
    else:
        outs = run_commands_remote(cmds, config)
        
    tracking_out = outs[0]
    sources_out = outs[1]
    
    offset, sources = "Unknown",[]
    
    # Parse tracking
    for line in tracking_out.split('\n'):
        if "System time" in line or "Last offset" in line:
            offset = line.split(':', 1)[-1].strip()
            break
            
    # Parse sources
    lines = sources_out.strip().split('\n')
    start_idx = next((i + 1 for i, l in enumerate(lines) if set(l.strip()) == {'='}), -1)
    if start_idx != -1:
        for line in lines[start_idx:]:
            if not line.strip(): continue
            parts = line.split()
            if len(parts) >= 6:
                sources.append({"state": parts[0], "name": parts[1], "stratum": parts[2], "poll": parts[3], "reach": parts[4], "lastrx": parts[5], "last_sample": " ".join(parts[6:])})
    
    # Determine error messages
    err = tracking_out if "Error" in tracking_out else None
    if not err and "Error" in sources_out: 
        err = sources_out
    
    return jsonify({"offset": offset, "sources": sources, "error": err})

@app.route('/api/gps')
def get_gps():
    config = load_config()
    # Read 12 lines of raw GPS JSON output and exit immediately
    cmd =["timeout 3 gpspipe -w -n 12"]
    
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
                    # Grab Satellites
                    if data.get("class") == "SKY":
                        satellites = data.get("satellites",[])
                    # Grab GPS Time
                    elif data.get("class") == "TPV" and "time" in data:
                        gps_time = data.get("time")
                except: pass
    except: pass
    
    return jsonify({"satellites": satellites, "gps_time": gps_time})

@app.route('/api/clients')
def get_clients():
    config = load_config()
    
    # Use sudo for remote SSH, but drop it for local Docker (since the container is already root)
    if config.get("mode") == "local":
        cmd = "chronyc -N clients -k"
        outs = run_commands_local([cmd])
    else:
        cmd = "sudo chronyc -N clients -k"
        outs = run_commands_remote([cmd], config)
        
    out = outs[0]
    clients =[]
    
    # Check if the command ran successfully
    if out and "Error" not in out and "command not found" not in out.lower():
        lines = out.strip().split('\n')
        start_idx = -1
        # Find the line with the '========' borders
        for i, line in enumerate(lines):
            if set(line.strip()) == {'='}:
                start_idx = i + 1
                break
        
        # Parse the clients table
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
        
        # If UI sends a blank password, keep the old encrypted one
        if not new_conf.get('password') and old_conf.get('password'):
            new_conf['password'] = old_conf['password']
        # NEW: If UI sends a new password, encrypt it!
        elif new_conf.get('password'):
            new_conf['password'] = encrypt_pwd(new_conf['password'])
            
        save_config(new_conf)
        return jsonify({"status": "success"})
    
    # Send config to UI but hide password for security
    conf = load_config()
    conf['password'] = ""
    return jsonify(conf)

if __name__ == '__main__':
    # Check if the environment variable DEBUG_MODE is set to "true" (defaults to "false")
    is_debug = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
    
    if is_debug:
        print("⚠️ DEBUG MODE ENABLED - Detailed errors will be shown in the browser.")
        
    # Pass the variable into Flask's run command
    app.run(host='0.0.0.0', port=55234, debug=is_debug)
