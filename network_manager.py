import socket
import datetime
import db_manager
import config_manager
import os
import platform

def get_node_id():
    """Unique ID based on hostname and hardware."""
    return f"{socket.gethostname()}-{platform.node()}"

def check_in():
    """Register this counter in the central database."""
    try:
        cfg = config_manager.load_config()
        node_id = get_node_id()
        node_name = socket.gethostname()
        ip = config_manager.get_local_ip()
        role = cfg.get("role", "host")
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        db = db_manager.connect()
        cur = db.cursor()
        
        # MySQL/SQLite compatible UPSERT
        cur.execute("SELECT node_id FROM network_nodes WHERE node_id = ?", (node_id,))
        if cur.fetchone():
            cur.execute(
                "UPDATE network_nodes SET ip_address=?, role=?, last_seen=?, node_name=? WHERE node_id=?",
                (ip, role, now, node_name, node_id)
            )
        else:
            cur.execute(
                "INSERT INTO network_nodes (node_id, node_name, ip_address, role, last_seen) VALUES (?,?,?,?,?)",
                (node_id, node_name, ip, role, now)
            )
        db.commit()
        return True
    except Exception as e:
        print(f"Network check-in failed: {e}")
        return False

def get_active_nodes(minutes=5):
    """Get nodes that have checked in recently."""
    try:
        db = db_manager.connect()
        cur = db.cursor()
        
        threshold = (datetime.datetime.now() - datetime.timedelta(minutes=minutes)).strftime("%Y-%m-%d %H:%M:%S")
        
        cur.execute("SELECT node_name, ip_address, role, last_seen FROM network_nodes WHERE last_seen >= ? ORDER BY last_seen DESC", (threshold,))
        return cur.fetchall()
    except:
        return []
