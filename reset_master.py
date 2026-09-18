import db_manager
try:
    db = db_manager.connect()
    db.execute("UPDATE settings SET value = '' WHERE `key` = 'master_node_id'")
    db.commit()
    print("SUCCESS: MASTER LOCK RESET COMPLETED")
except Exception as e:
    print(f"FAILED: {e}")
