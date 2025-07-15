from flask import Flask, request, redirect
import requests
import socket
import platform
import os
import psutil
from datetime import datetime
import netifaces
import threading
import sqlite3
import json

app = Flask(__name__)

DB_PATH = 'tracking.db'

IPAPI_BASE_URL = "http://ip-api.com/json/"
IPAPI_FIELDS = "status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"

def get_public_ip():
    try:
        response = requests.get(f"{IPAPI_BASE_URL}?fields=query", timeout=3)
        if response.status_code == 200:
            data = response.json()
            return data.get('query')
        services = [
            'https://api.ipify.org?format=json',
            'https://ifconfig.me/all.json'
        ]
        for service in services:
            try:
                response = requests.get(service, timeout=2)
                if response.status_code == 200:
                    data = response.json()
                    return data.get('ip') or data.get('ip_addr')
            except:
                continue
        return socket.gethostbyname(socket.gethostname())
    except:
        return "127.0.0.1"

def get_geolocation(ip):
    try:
        response = requests.get(f"{IPAPI_BASE_URL}{ip}?fields={IPAPI_FIELDS}", timeout=3)
        data = response.json()
        if data.get('status') == 'success':
            return data
        return {"message": data.get('message', 'موقعیت یافت نشد'), "query": ip}
    except Exception as e:
        return {"message": str(e), "query": ip}

def get_system_info():
    try:
        sys_info = {
            'سیستم عامل': platform.system(),
            'نسخه': platform.release(),
            'معماری': platform.architecture()[0],
            'نام دستگاه': socket.gethostname(),
            'کاربر': os.getlogin() if hasattr(os, 'getlogin') else 'نامشخص',
            'زمان راه‌اندازی': datetime.fromtimestamp(psutil.boot_time()).strftime("%Y-%m-%d %H:%M:%S")
        }
        net_info = {}
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                net_info[iface] = {
                    'IP': addrs[netifaces.AF_INET][0]['addr'],
                    'Netmask': addrs[netifaces.AF_INET][0]['netmask']
                }
        hardware = {
            'CPU': f"{psutil.cpu_percent()}%",
            'حافظه': f"{psutil.virtual_memory().percent}%",
            'هسته‌ها': psutil.cpu_count(logical=False),
            'حافظه کل': f"{psutil.virtual_memory().total // (1024**3)}GB"
        }
        return {
            'system': sys_info,
            'network': net_info,
            'hardware': hardware
        }
    except Exception as e:
        return {"خطا": str(e)}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            ip TEXT,
            client_info TEXT,
            geolocation TEXT,
            system_info TEXT
        )
    ''')
    conn.commit()
    conn.close()

def save_to_db(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT INTO tracking (timestamp, ip, client_info, geolocation, system_info)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            data['timestamp'],
            data['client_info'].get('IP', ''),
            json.dumps(data['client_info'], ensure_ascii=False),
            json.dumps(data['geolocation'], ensure_ascii=False),
            json.dumps(data['system_info'], ensure_ascii=False)
        ))
        conn.commit()
        conn.close()
    except Exception as e:
        print("DB Error:", str(e))

def process_tracking(client_info):
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "client_info": client_info,
        "geolocation": get_geolocation(get_public_ip()),
        "system_info": get_system_info()
    }
    save_to_db(data)

@app.route('/loc', methods=['GET'])
def loc():
    client_info = {
        'IP': request.remote_addr,
        'مرورگر': request.user_agent.browser,
        'ورژن': request.user_agent.version,
        'سیستم': request.user_agent.platform,
        'هدرها': {
            'Accept-Language': request.headers.get('Accept-Language'),
            'User-Agent': request.headers.get('User-Agent')
        }
    }
    threading.Thread(target=process_tracking, args=(client_info,)).start()
    return redirect("https://www.google.com")

@app.route('/logs', methods=['GET'])
def logs():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, timestamp, ip, client_info, geolocation, system_info FROM tracking ORDER BY id DESC LIMIT 20")
        rows = c.fetchall()
        conn.close()
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "timestamp": row[1],
                "ip": row[2],
                "client_info": json.loads(row[3]),
                "geolocation": json.loads(row[4]),
                "system_info": json.loads(row[5])
            })
        return json.dumps(result, ensure_ascii=False, indent=4)
    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
