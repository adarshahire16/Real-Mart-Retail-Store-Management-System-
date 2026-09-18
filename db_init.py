"""Create SQLite schema, migrate columns, and seed data for Real Mart."""
import csv
import hashlib
import os
import db_manager as sqlite3

import base64

# --- Reversible Security for Employee Management ---
# This allows the Admin Hub to reveal plain text while keeping the DB obfuscated.
SECURITY_KEY = "REALMART_2024_SECURE_VAULT"

def secure_store(password):
    """Obfuscates password for database storage (reversible)."""
    if not password: return ""
    p_bytes = password.encode('utf-8')
    res = bytearray()
    for i in range(len(p_bytes)):
        key_c = ord(SECURITY_KEY[i % len(SECURITY_KEY)])
        enc_c = (p_bytes[i] + key_c) % 256
        res.append(enc_c)
    return base64.b64encode(res).decode('utf-8')

def secure_reveal(encoded):
    """Restores plain text for Admin Hub visibility."""
    if not encoded: return ""
    try:
        data = base64.b64decode(encoded.encode('utf-8'))
        res = bytearray()
        for i in range(len(data)):
            key_c = ord(SECURITY_KEY[i % len(SECURITY_KEY)])
            dec_c = (data[i] - key_c) % 256
            res.append(dec_c)
        return res.decode('utf-8')
    except Exception:
        return encoded # Fallback if already plain

def hash_password(password):
    """ONE-WAY Secure hashing for Admin Identity verification."""
    if not password: return ""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_admin_password(entered, stored):
    """Checks if entered password matches stored (supports hash or encrypted)."""
    if not entered or not stored: return False
    h = hash_password(entered.strip())
    e = secure_store(entered.strip())
    return str(stored).strip() in (h, e)

def migrate_passwords(conn):
    """Detect plain-text passwords and upgrade them to hashes."""
    cur = conn.cursor()
    cur.execute("SELECT emp_id, password FROM employee")
    users = cur.fetchall()
    for eid, pw in users:
        # SHA-256 hex is exactly 64 characters. If already 64, it's definitely a hash.
        if len(pw) == 64:
            continue
            
        # NEW: Check if it's already secured via reversible encryption
        # secure_reveal returns the same string if it's not valid base64 or fails to decode.
        # If revealed != pw, it means it was successfully decrypted, so it's already secured.
        revealed = secure_reveal(pw)
        if revealed != pw:
            continue

        # If we reached here, it's likely plain text.
        hashed = hash_password(pw)
        cur.execute("UPDATE employee SET password = ? WHERE emp_id = ?", (hashed, eid))
    conn.commit()

# Demo catalog: fresh produce & grocery (category, name, stock, mrp, cost, vendor).
SAMPLE_PRODUCTS = [
    ("Fresh Fruits", "Bananas (Ripe) 1 dozen", 80, 60.0, 42.0, "9876543210"),
    ("Fresh Fruits", "Shimla Apples 1kg", 55, 220.0, 165.0, "9876543210"),
    ("Fresh Fruits", "Alphonso Mangoes 1kg", 40, 320.0, 250.0, "9876543210"),
    ("Fresh Fruits", "Seedless Grapes 500g", 65, 95.0, 68.0, "9876543210"),
    ("Fresh Vegetables", "Farm Tomatoes 1kg", 90, 55.0, 35.0, "9876543210"),
    ("Fresh Vegetables", "Onions (Nasik) 1kg", 120, 42.0, 28.0, "9876543210"),
    ("Fresh Vegetables", "Potatoes 1kg", 100, 38.0, 24.0, "9876543210"),
    ("Fresh Vegetables", "Button Mushrooms 200g", 45, 85.0, 55.0, "9876543210"),
    ("Leafy & Herbs", "Coriander Bunch", 70, 25.0, 12.0, "9876543210"),
    ("Leafy & Herbs", "Curry Leaves 1 pack", 60, 18.0, 8.0, "9876543210"),
    ("Leafy & Herbs", "Baby Spinach 250g", 50, 55.0, 35.0, "9876543210"),
    ("Dairy", "Toned Milk 1L", 85, 60.0, 48.0, "9876543210"),
    ("Dairy", "Farm Fresh Curd 400g", 65, 48.0, 32.0, "9876543210"),
    ("Bakery", "Whole Wheat Bread 400g", 40, 55.0, 38.0, "9876543210"),
    ("Staples", "Basmati Rice 5kg", 35, 520.0, 430.0, "9876543210"),
    ("Staples", "Cold-pressed Mustard Oil 1L", 50, 195.0, 150.0, "9876543210"),
    ("Staples", "Toor Dal 1kg", 60, 145.0, 110.0, "9876543210"),
    ("Beverages", "Packaged Water 1L", 150, 20.0, 12.0, "9876543210"),
    ("Beverages", "Tender Coconut 1 pc", 40, 65.0, 45.0, "9876543210"),
]


def db_path():
    try:
        import config_manager
        cfg = config_manager.load_config()
        custom_path = cfg.get("db_path")
        if custom_path and os.path.exists(os.path.dirname(custom_path)):
            return custom_path
    except:
        pass
        
    try:
        import config_manager
        base = config_manager.get_base_path()
    except:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "Database", "store.db")


def _table_columns(conn, table):
    import config_manager
    is_mysql = config_manager.load_config().get("db_type") == "mysql"
    if is_mysql:
        db_name = config_manager.load_config().get("mysql", {}).get("database", "real_mart")
        cur = conn.cursor()
        cur.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = '{table}' AND TABLE_SCHEMA = '{db_name}'")
        return {row[0] for row in cur.fetchall()}
    else:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return {row[1] for row in cur.fetchall()}


def migrate_schema(conn):
    """Add bill payment columns; drop use of inventory subcategory."""
    cols = _table_columns(conn, "bill")
    alters = [
        ("payment_method", "TEXT DEFAULT 'Cash'"),
        ("cash_tendered", "REAL"),
        ("change_amount", "REAL"),
        ("bill_time", "TEXT"),
        ("card_no", "TEXT"),
        ("card_holder", "TEXT"),
        ("card_expiry", "TEXT"),
        ("upi_id_used", "TEXT"),
        ("total_amount", "REAL DEFAULT 0.0"),
    ]
    for name, typ in alters:
        if name not in cols:
            conn.execute(f"ALTER TABLE bill ADD COLUMN {name} {typ}")


    # Migrate inventory
    inv_cols = _table_columns(conn, "raw_inventory")
    if "expiry_date" not in inv_cols:
        conn.execute("ALTER TABLE raw_inventory ADD COLUMN expiry_date TEXT DEFAULT 'N/A'")
    if "barcode" not in inv_cols:
        conn.execute("ALTER TABLE raw_inventory ADD COLUMN barcode TEXT DEFAULT ''")
    if "offer_type" not in inv_cols:
        conn.execute("ALTER TABLE raw_inventory ADD COLUMN offer_type TEXT DEFAULT 'None'")
    if "offer_value" not in inv_cols:
        conn.execute("ALTER TABLE raw_inventory ADD COLUMN offer_value REAL DEFAULT 0.0")
    
    # Migrate bill_items cost_price
    bi_cols = _table_columns(conn, "bill_items")
    if "cost_price" not in bi_cols:
        conn.execute("ALTER TABLE bill_items ADD COLUMN cost_price REAL DEFAULT 0.0")

    # Migrate employee approval
    emp_cols = _table_columns(conn, "employee")
    if "approved" not in emp_cols:
        conn.execute("ALTER TABLE employee ADD COLUMN approved INTEGER DEFAULT 0")
        # Existing employees (pre-feature) should probably be approved
        conn.execute("UPDATE employee SET approved = 1")


def parse_bill_row(row):
    """Map SELECT * FROM bill tuple to dict (handles pre-migration 5-tuple rows)."""
    r = list(row)
    out = {
        "bill_no": r[0],
        "date": r[1],
        "customer_name": r[2],
        "customer_no": r[3],
        "bill_details": r[4],
        "payment_method": "Cash",
        "cash_tendered": None,
        "change_amount": None,
        "bill_time": "",
        "card_no": None,
        "card_holder": None,
        "card_expiry": None,
        "upi_id_used": None,
    }
    if len(r) > 5 and r[5] is not None:
        out["payment_method"] = r[5] or "Cash"
    if len(r) > 6:
        out["cash_tendered"] = r[6]
    if len(r) > 7:
        out["change_amount"] = r[7]
    if len(r) > 8 and r[8]:
        out["bill_time"] = r[8]
    if len(r) > 9:
        out["card_no"] = r[9]
    if len(r) > 10:
        out["card_holder"] = r[10]
    if len(r) > 11:
        out["card_expiry"] = r[11]
    if len(r) > 12:
        out["upi_id_used"] = r[12]
    return out


def sync_catalog_products(cur):
    """Insert sample SKUs when missing (keeps catalog relevant without wiping user data)."""
    for cat, name, stock, mrp, cost, vendor in SAMPLE_PRODUCTS:
        cur.execute("SELECT 1 FROM raw_inventory WHERE product_name = ?", (name,))
        if cur.fetchone():
            continue
        cur.execute(
            "INSERT INTO raw_inventory(product_name, product_cat, stock, mrp, cost_price, vendor_phn) VALUES(?,?,?,?,?,?)",
            (name, cat, stock, mrp, cost, vendor),
        )


def ensure_database():
    import config_manager
    config = config_manager.load_config()
    is_mysql = config.get("db_type") == "mysql"

    # Always resolve db_dir globally to avoid NameErrors when seeding
    try:
        base = config_manager.get_base_path()
    except:
        base = os.path.dirname(os.path.abspath(__file__))
    db_dir = os.path.join(base, "Database")

    if not is_mysql:
        db_p = db_path()
        os.makedirs(db_dir, exist_ok=True)
        
        # Copy bundled DB to AppData on first run
        import sys
        if getattr(sys, 'frozen', False) and not os.path.exists(db_p):
            bundled_db = os.path.join(os.path.dirname(sys.executable), "Database", "store.db")
            if os.path.exists(bundled_db):
                import shutil
                shutil.copy2(bundled_db, db_p)

    conn = sqlite3.connect(db_path())
    try:
        # Define table creation SQL statements compatible with both SQLite and MySQL
        tables_to_create = [
            # 1. coupons (the actual used coupons table)
            """
            CREATE TABLE IF NOT EXISTS coupons (
                coupon_code VARCHAR(255) PRIMARY KEY,
                discount_value REAL NOT NULL,
                discount_type VARCHAR(255) DEFAULT 'Amount',
                min_bill REAL DEFAULT 0.0,
                expiry_date VARCHAR(255) NOT NULL,
                is_used INTEGER DEFAULT 0,
                created_at VARCHAR(255)
            )
            """,
            # 2. employee
            """
            CREATE TABLE IF NOT EXISTS employee (
                emp_id VARCHAR(255) PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                contact_num VARCHAR(255) NOT NULL,
                address TEXT NOT NULL,
                aadhar_num VARCHAR(255) NOT NULL,
                password VARCHAR(255) NOT NULL,
                designation VARCHAR(255) NOT NULL,
                approved INTEGER DEFAULT 0
            )
            """,
            # 3. raw_inventory
            """
            CREATE TABLE IF NOT EXISTS raw_inventory (
                product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name VARCHAR(255) NOT NULL,
                product_cat VARCHAR(255) NOT NULL,
                stock INTEGER NOT NULL,
                mrp REAL NOT NULL,
                cost_price REAL NOT NULL,
                vendor_phn VARCHAR(255),
                expiry_date VARCHAR(255) DEFAULT 'N/A',
                barcode VARCHAR(255) DEFAULT '',
                offer_type VARCHAR(255) DEFAULT 'None',
                offer_value REAL DEFAULT 0.0
            )
            """,
            # 4. bill
            """
            CREATE TABLE IF NOT EXISTS bill (
                bill_no VARCHAR(255) PRIMARY KEY,
                date VARCHAR(255) NOT NULL,
                customer_name VARCHAR(255) NOT NULL,
                customer_no VARCHAR(255) NOT NULL,
                bill_details TEXT NOT NULL,
                total_amount REAL DEFAULT 0.0
            )
            """,
            # 5. payment_config
            """
            CREATE TABLE IF NOT EXISTS payment_config (
                qr_id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename VARCHAR(255) NOT NULL,
                upi_id VARCHAR(255),
                payee_name VARCHAR(255)
            )
            """,
            # 6. settings
            """
            CREATE TABLE IF NOT EXISTS settings (
                `key` VARCHAR(255) PRIMARY KEY,
                value TEXT NOT NULL
            )
            """,
            # 7. bill_items
            """
            CREATE TABLE IF NOT EXISTS bill_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                bill_no VARCHAR(255) NOT NULL,
                product_id INTEGER,
                product_name VARCHAR(255) NOT NULL,
                quantity INTEGER NOT NULL,
                mrp REAL NOT NULL,
                cost_price REAL DEFAULT 0.0,
                total_price REAL NOT NULL,
                FOREIGN KEY (bill_no) REFERENCES bill (bill_no)
            )
            """,
            # 8. coupon_tiers
            """
            CREATE TABLE IF NOT EXISTS coupon_tiers (
                tier_id INTEGER PRIMARY KEY AUTOINCREMENT,
                min_bill REAL NOT NULL,
                reward_value REAL NOT NULL,
                discount_type VARCHAR(255) DEFAULT 'Amount'
            )
            """
        ]

        for sql in tables_to_create:
            if is_mysql:
                sql = sql.replace("AUTOINCREMENT", "AUTO_INCREMENT")
            conn.execute(sql)

        if not is_mysql:
            # Add Indices for SQLite performance (MySQL indices managed differently or skipped for speed)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inv_barcode ON raw_inventory(barcode)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_inv_name ON raw_inventory(product_name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_emp_designation ON employee(designation)")

        migrate_schema(conn)
        migrate_passwords(conn)
        cur = conn.cursor()

        # —— NETWORK TABLES (Shared across all DB types) ——
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS network_nodes (
                    node_id VARCHAR(100) PRIMARY KEY,
                    node_name VARCHAR(100),
                    ip_address VARCHAR(45),
                    role VARCHAR(20),
                    last_seen VARCHAR(30)
                )
                """
            )

            # --- NEW: ACTIVE SESSIONS MONITOR ---
            st_sql = """
                CREATE TABLE IF NOT EXISTS active_sessions (
                    session_id VARCHAR(100) PRIMARY KEY,
                    pc_name VARCHAR(100) NOT NULL,
                    pc_ip VARCHAR(45) NOT NULL,
                    role VARCHAR(50) NOT NULL,
                    user_name VARCHAR(100) NOT NULL,
                    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            if is_mysql:
                # MySQL optimization
                st_sql = st_sql.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", 
                                        "TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP")
            conn.execute(st_sql)

            # --- NEW: BROADCAST SYSTEM ---
            b_sql = """
                CREATE TABLE IF NOT EXISTS broadcast_messages (
                    msg_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message TEXT NOT NULL,
                    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1
                )
            """
            if is_mysql:
                b_sql = b_sql.replace("AUTOINCREMENT", "AUTO_INCREMENT")
            conn.execute(b_sql)

            # --- NEW: NETWORK AUDIT TRAIL ---
            a_sql = """
                CREATE TABLE IF NOT EXISTS audit_trail (
                    audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type VARCHAR(50) NOT NULL,
                    description TEXT,
                    pc_name VARCHAR(100),
                    user_name VARCHAR(100),
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            if is_mysql:
                a_sql = a_sql.replace("AUTOINCREMENT", "AUTO_INCREMENT")
            conn.execute(a_sql)

            # --- NEW: FLASH SALES & HAPPY HOURS ---
            f_sql = """
                CREATE TABLE IF NOT EXISTS flash_sales (
                    sale_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category VARCHAR(100) NOT NULL,
                    discount_percent REAL NOT NULL,
                    start_time VARCHAR(5) NOT NULL, -- HH:MM
                    end_time VARCHAR(5) NOT NULL,   -- HH:MM
                    is_active INTEGER DEFAULT 1
                )
            """
            if is_mysql:
                f_sql = f_sql.replace("AUTOINCREMENT", "AUTO_INCREMENT")
            conn.execute(f_sql)

            # --- NEW: LOYALTY POINT SYSTEM ---
            l_sql = """
                CREATE TABLE IF NOT EXISTS loyalty_points (
                    phone VARCHAR(15) PRIMARY KEY,
                    points REAL DEFAULT 0,
                    total_spent REAL DEFAULT 0,
                    last_visit TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
            conn.execute(l_sql)

            lc_sql = """
                CREATE TABLE IF NOT EXISTS loyalty_config (
                    `key` VARCHAR(50) PRIMARY KEY,
                    `value` VARCHAR(100)
                )
            """
            conn.execute(lc_sql)
            
            # Default Config
            if is_mysql:
                conn.execute("INSERT IGNORE INTO loyalty_config (`key`, `value`) VALUES ('points_per_100', '1')")
                conn.execute("INSERT IGNORE INTO loyalty_config (`key`, `value`) VALUES ('point_value_rs', '0.5')") # 1 point = 0.5 Rs
            else:
                conn.execute("INSERT OR IGNORE INTO loyalty_config (`key`, `value`) VALUES ('points_per_100', '1')")
                conn.execute("INSERT OR IGNORE INTO loyalty_config (`key`, `value`) VALUES ('points_per_100', '1')")
                conn.execute("INSERT OR IGNORE INTO loyalty_config (`key`, `value`) VALUES ('point_value_rs', '0.5')")

            # Last Chance Config
            lc_config_sql = """
                CREATE TABLE IF NOT EXISTS last_chance_config (
                    `key` VARCHAR(50) PRIMARY KEY,
                    `value` VARCHAR(100)
                )
            """
            conn.execute(lc_config_sql)
            if is_mysql:
                conn.execute("INSERT IGNORE INTO last_chance_config (`key`, `value`) VALUES ('threshold_days', '7')")
                conn.execute("INSERT IGNORE INTO last_chance_config (`key`, `value`) VALUES ('discount_percent', '50')")
                conn.execute("INSERT IGNORE INTO last_chance_config (`key`, `value`) VALUES ('enabled', '1')")
            else:
                conn.execute("INSERT OR IGNORE INTO last_chance_config (`key`, `value`) VALUES ('threshold_days', '7')")
                conn.execute("INSERT OR IGNORE INTO last_chance_config (`key`, `value`) VALUES ('discount_percent', '50')")
                conn.execute("INSERT OR IGNORE INTO last_chance_config (`key`, `value`) VALUES ('enabled', '1')")
            
        except Exception as e:
            print(f"Notice: network_nodes check skipped or failed: {e}")
        cur.execute("SELECT 1 FROM settings WHERE `key` = 'master_node_id'")
        if not cur.fetchone():
            cur.execute("INSERT INTO settings (`key`, value) VALUES ('master_node_id', '')")

        cur.execute("SELECT 1 FROM settings WHERE `key` = 'payment_pin'")
        if not cur.fetchone():
            cur.execute("INSERT INTO settings (`key`, value) VALUES ('payment_pin', '1234')")
        
        cur.execute("SELECT 1 FROM settings WHERE `key` = 'coupon_threshold'")
        if not cur.fetchone():
            cur.execute("INSERT INTO settings (`key`, value) VALUES ('coupon_threshold', '2000')")
            
        cur.execute("SELECT 1 FROM settings WHERE `key` = 'coupon_discount'")
        if not cur.fetchone():
            cur.execute("INSERT INTO settings (`key`, value) VALUES ('coupon_discount', '100')")

        # Seed Default Coupon Tiers
        cur.execute("SELECT COUNT(*) FROM coupon_tiers")
        if cur.fetchone()[0] == 0:
            tiers = [
                (1000, 50, "Amount"),
                (2000, 150, "Amount"),
                (5000, 500, "Amount")
            ]
            cur.executemany("INSERT INTO coupon_tiers (min_bill, reward_value, discount_type) VALUES (?,?,?)", tiers)
        
        cur.execute("SELECT COUNT(*) FROM employee")
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO employee(emp_id, name, contact_num, address, aadhar_num, password, designation, approved) VALUES(?,?,?,?,?,?,?,?)",
                (
                    "EMP0000",
                    "Master Admin",
                    "9876543210",
                    "Store HQ",
                    "123456789012",
                    hash_password("admin"),
                    "Admin",
                    1,
                ),
            )
        else:
            cur.execute(
                "SELECT COUNT(*) FROM employee WHERE designation = ?",
                ("Admin",),
            )
            if cur.fetchone()[0] == 0:
                cur.execute(
                    """REPLACE INTO employee(
                        emp_id, name, contact_num, address, aadhar_num, password, designation, approved
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        "EMP0000",
                        "Master Admin",
                        "9876543210",
                        "Store HQ",
                        "123456789012",
                        hash_password("admin"),
                        "Admin",
                        1,
                    ),
                )

        cur.execute("SELECT COUNT(*) FROM raw_inventory")
        if cur.fetchone()[0] == 0:
            csv_file = os.path.join(db_dir, "raw_inventory.csv")
            import sys
            if getattr(sys, 'frozen', False) and not os.path.isfile(csv_file):
                csv_file = os.path.join(os.path.dirname(sys.executable), "Database", "raw_inventory.csv")
            if os.path.isfile(csv_file):
                with open(csv_file, newline="", encoding="utf-8") as f:
                    for row in csv.DictReader(f):
                        vendor = (row.get("vendor_phn") or "").strip() or "9876543210"
                        cp = row.get("cost_price") or "0"
                        try:
                            cost_price = float(cp)
                        except ValueError:
                            cost_price = 0.0
                        cur.execute(
                            "INSERT INTO raw_inventory(product_name, product_cat, stock, mrp, cost_price, vendor_phn, barcode) VALUES(?,?,?,?,?,?,?)",
                            (
                                row["product_name"],
                                row["product_cat"],
                                int(row["stock"]),
                                float(row["mrp"]),
                                cost_price,
                                vendor,
                                "",
                            ),
                        )
        sync_catalog_products(cur)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_database()
