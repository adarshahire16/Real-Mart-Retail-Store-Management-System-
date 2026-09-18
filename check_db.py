import db_manager
import config_manager
import os

cfg = config_manager.load_config()
print(f"Config DB Type: {cfg.get('db_type')}")

try:
    conn = db_manager.connect()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM bill_items")
    count = cur.fetchone()[0]
    print(f"Total items in bill_items table: {count}")
    
    if count > 0:
        cur.execute("SELECT * FROM bill_items LIMIT 5")
        rows = cur.fetchall()
        print("Sample bill items:")
        for r in rows:
            print(r)
            
    conn.close()
except Exception as e:
    print(f"Error: {e}")
