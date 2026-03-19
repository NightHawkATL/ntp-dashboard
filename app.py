import os, json, subprocess
from flask import Flask, render_template, jsonify, request
import paramiko

app = Flask(__name__)
CONFIG_FILE = 'config.json'

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
            out = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5).stdout
            results.append(out)
        except Exception as e:
            results.append(f"Error: {str(e)}")
    return results

def run_commands_remote(cmds, config):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    results =[]
    try:
        # Connect once for all commands
        pwd = config.get('password')
        if not pwd: pwd = None
        
        # look_for_keys=False prevents Docker from crashing while looking for non-existent local keys
        ssh.connect(config.get('host'), username=config.get('user'), password=pwd, timeout=5, look_for_keys=False)
        
        for cmd in cmds:
            stdin, stdout, stderr = ssh.exec_command(cmd, timeout=5)
            results.append(stdout.read().decode('utf-8'))
    except Exception as e:
        # If connection fails, return the error for all requested commands
        return [f"Error: {str(e)}"] * len(cmds)
    finally:
        ssh.close()
    return results

@app.route('/')
def index(): 
    return render_template('index.html')

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

@app.route('/api/config', methods=['GET', 'POST'])
def config_endpoint():
    if request.method == 'POST':
        save_config(request.json)
        return jsonify({"status": "success"})
    return jsonify(load_config())

if __name__ == '__main__':
    # Check if the environment variable DEBUG_MODE is set to "true" (defaults to "false")
    is_debug = os.environ.get('DEBUG_MODE', 'false').lower() == 'true'
    
    if is_debug:
        print("⚠️ DEBUG MODE ENABLED - Detailed errors will be shown in the browser.")
        
    # Pass the variable into Flask's run command
    app.run(host='0.0.0.0', port=55234, debug=is_debug)
