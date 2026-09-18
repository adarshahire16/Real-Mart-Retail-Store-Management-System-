import json
import os
import shutil
from datetime import datetime

import sys

def get_base_path():
    if getattr(sys, 'frozen', False) and sys.platform == "win32":
        path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'RealMart')
        os.makedirs(path, exist_ok=True)
        return path
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(get_base_path(), "config.json")

DEFAULT_CONFIG = {
    "db_type": "sqlite", # 'sqlite' or 'mysql'
    "db_path": "", # Empty means use default relative path
    "mysql": {
        "host": "localhost",
        "user": "root",
        "password": "",
        "database": "real_mart"
    },
    "role": "host", # 'host' or 'terminal'
    "setup_complete": False,
    "backup_dir": "backups",
    "last_backup": "",
    "auto_backup_on_close": True,
    "backup_retention_days": 30
}

_CONFIG_CACHE = None

def load_config():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    if not os.path.exists(CONFIG_FILE):
        _CONFIG_CACHE = DEFAULT_CONFIG.copy()
        return _CONFIG_CACHE
    try:
        with open(CONFIG_FILE, 'r') as f:
            _CONFIG_CACHE = {**DEFAULT_CONFIG, **json.load(f)}
            return _CONFIG_CACHE
    except:
        return DEFAULT_CONFIG

def save_config(config):
    global _CONFIG_CACHE
    _CONFIG_CACHE = config.copy()
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)


def cleanup_old_backups():
    import time
    config = load_config()
    backup_dir = config.get("backup_dir", "backups")
    if not os.path.isabs(backup_dir):
        backup_dir = os.path.join(get_base_path(), backup_dir)
    retention_days = config.get("backup_retention_days", 30)
    
    if not os.path.exists(backup_dir):
        return
        
    now = time.time()
    for f in os.listdir(backup_dir):
        f_path = os.path.join(backup_dir, f)
        if os.path.isfile(f_path) and f.startswith("store_backup_"):
            # Delete if older than retention days
            if os.stat(f_path).st_mtime < now - (retention_days * 86400):
                try:
                    os.remove(f_path)
                except:
                    pass

def perform_backup():
    config = load_config()
    db_path = config.get("db_path")
    
    # Resolve actual DB path
    if not db_path:
        import db_init
        db_path = db_init.db_path()
        
    if not os.path.exists(db_path):
        return False, "Database file not found."
        
    backup_dir = config.get("backup_dir", "backups")
    if not os.path.isabs(backup_dir):
        backup_dir = os.path.join(get_base_path(), backup_dir)
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # —— RETENTION POLICY ——
    cleanup_old_backups()
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"store_backup_{timestamp}.db")
    
    try:
        shutil.copy2(db_path, backup_file)
        config["last_backup"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_config(config)
        return True, backup_file
    except Exception as e:
        return False, str(e)

def get_local_ip():
    import socket
    try:
        # This approach doesn't require an internet connection
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0)
        # doesn't even have to be reachable
        s.connect(('10.254.254.254', 1))
        IP = s.getsockname()[0]
        s.close()
    except Exception:
        IP = '127.0.0.1'
    return IP
