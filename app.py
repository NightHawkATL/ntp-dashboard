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

def run_command(cmd, config):
    if config.get("mode") == "local":
        try:
            return subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4).stdout
        except Exception as e: return f"Error: {str(e)}"
    else:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(config.get('host'), username=config.get('user'), password=config.get('password') or None, timeout=4, look_for_keys=True)
            return ssh.exec_command(cmd, timeout=4)[1].read().decode('utf-8')
        except Exception as e: return f"Error: {str(e)}"
        finally: ssh.close()

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/api/ntp')
def get_ntp():
    config = load_config()
    tracking_out = run_command("chronyc tracking", config)
    offset, sources = "Unknown",[]
    for line in tracking_out.split('\n'):
        if "System time" in line or "Last offset" in line:
            offset = line.split(':', 1)[-1].strip()
            break
            
    lines = run_command("chronyc sources", config).strip().split('\n')
    start_idx = next((i + 1 for i, l in enumerate(lines) if set(l.strip()) == {'='}), -1)
    if start_idx != -1:
        for line in lines[start_idx:]:
            if not line.strip(): continue
            parts = line.split()
            if len(parts) >= 6:
                sources.append({"state": parts[0], "name": parts[1], "stratum": parts[2], "poll": parts[3], "reach": parts[4], "lastrx": parts[5], "last_sample": " ".join(parts[6:])})
    return jsonify({"offset": offset, "sources": sources, "error": tracking_out if "Error" in tracking_out else None})

@app.route('/api/gps')
def get_gps():
    gps_out = run_command("timeout 3 gpspipe -w | grep -m 1 '\"class\":\"SKY\"'", load_config())
    satellites =[]
    try:
        if gps_out and "Error" not in gps_out:
            satellites = json.loads(gps_out).get("satellites",[])
    except: pass
    return jsonify({"satellites": satellites})

@app.route('/api/config', methods=['GET', 'POST'])
def config_endpoint():
    if request.method == 'POST':
        save_config(request.json)
        return jsonify({"status": "success"})
    return jsonify(load_config())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)