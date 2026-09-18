import sqlite3
try:
    import pymysql
except ImportError:
    pymysql = None
import config_manager
import os
import threading

_DB_LOCK = threading.Lock()

class SmartCursor:
    def __init__(self, cursor, db_type):
        self.cursor = cursor
        self.db_type = db_type

    def execute(self, query, params=None):
        if self.db_type == "mysql":
            if params is not None:
                query = query.replace("?", "%s")
            try:
                return self.cursor.execute(query, params)
            except (pymysql.err.OperationalError, pymysql.err.InterfaceError):
                # Try to reconnect once if connection was lost
                import db_manager
                manager = db_manager.DBConnection()
                new_db = manager.connect()
                self.cursor = new_db.cursor().cursor # Get raw cursor from new SmartCursor
                return self.cursor.execute(query, params)
        else:
            if params is not None:
                return self.cursor.execute(query, params)
            return self.cursor.execute(query)

    def executemany(self, query, params_list):
        if self.db_type == "mysql":
            query = query.replace("?", "%s")
        return self.cursor.executemany(query, params_list)

    def __getattr__(self, name):
        return getattr(self.cursor, name)

class SmartConn:
    def __init__(self, conn, db_type):
        self.conn = conn
        self.db_type = db_type

    def cursor(self, **kwargs):
        return SmartCursor(self.conn.cursor(**kwargs), self.db_type)

    def execute(self, query, params=None):
        # Convenience method like sqlite3 has
        c = self.cursor()
        c.execute(query, params)
        return c

    def __getattr__(self, name):
        return getattr(self.conn, name)

    def close(self):
        # Ignore close to protect the global connection cache
        pass
        
    def force_close(self):
        # Actually close the connection
        try:
            self.conn.close()
        except:
            pass

    def is_alive(self):
        try:
            if self.db_type == "mysql":
                self.conn.ping(reconnect=True)
            else:
                self.conn.execute("SELECT 1")
            return True
        except:
            return False

class DBConnection:
    def __init__(self):
        self.config = config_manager.load_config()
        self.db_type = self.config.get("db_type", "sqlite")
        self.conn = None

    def connect(self, *args, **kwargs):
        if self.db_type == "mysql":
            m_cfg = self.config.get("mysql", {})
            try:
                raw_conn = pymysql.connect(
                    host=m_cfg.get("host", "localhost"),
                    user=m_cfg.get("user", "root"),
                    password=m_cfg.get("password", ""),
                    database=m_cfg.get("database", "real_mart")
                )
                self.conn = SmartConn(raw_conn, "mysql")
            except Exception as err:
                # Safely check for pymysql error even if library is missing
                if pymysql and isinstance(err, pymysql.Error):
                    print(f"MySQL Error: {err}")
                else:
                    print(f"Database Error: {err}")
                raise err
        else:
            import db_init
            db_path = args[0] if args else db_init.db_path()
            raw_conn = sqlite3.connect(db_path, check_same_thread=False)
            self.conn = SmartConn(raw_conn, "sqlite")
        return self.conn

    def test_current_config(self):
        try:
            if self.db_type == "mysql":
                m_cfg = self.config.get("mysql", {})
                conn = pymysql.connect(
                    host=m_cfg.get("host", "localhost"),
                    user=m_cfg.get("user", "root"),
                    password=m_cfg.get("password", ""),
                    database=m_cfg.get("database", "real_mart"),
                    connect_timeout=5
                )
                conn.close()
                return True, f"Successfully connected to MySQL at {m_cfg.get('host')}"
            else:
                import db_init
                path = db_init.db_path()
                # For SQLite, if the directory is valid, we consider it "ready" or "ready to create"
                db_dir = os.path.dirname(path)
                if not db_dir or os.path.exists(db_dir):
                    return True, "Local SQLite is ready."
                return False, f"Database directory not found: {db_dir}"
        except Exception as e:
            return False, str(e)

_THREAD_LOCAL = threading.local()

def get_cached_conn():
    return getattr(_THREAD_LOCAL, 'connection', None)

def get_cached_config():
    return getattr(_THREAD_LOCAL, 'config', None)

def set_cached_conn(conn, config):
    _THREAD_LOCAL.connection = conn
    _THREAD_LOCAL.config = config

def connect(*args, **kwargs):
    current_config = config_manager.load_config()
    db_type = current_config.get("db_type", "sqlite")
    
    cached_conn = get_cached_conn()
    cached_config = get_cached_config()
    
    # If we have a cached connection in this thread and config hasn't changed, check if it's still alive
    if cached_conn and cached_config == current_config:
        try:
            if db_type == "mysql":
                cached_conn.conn.ping(reconnect=True)
            else:
                cached_conn.conn.execute("SELECT 1")
            return cached_conn
        except:
            pass # Connection died, proceed to reconnect
            
    manager = DBConnection()
    conn = manager.connect(*args, **kwargs)
    
    set_cached_conn(conn, current_config)
    return conn

# Unified Error class
try:
    _cfg = config_manager.load_config()
    if _cfg.get("db_type") == "sqlite":
        Error = sqlite3.Error
    else:
        Error = pymysql.Error if pymysql else sqlite3.Error
except:
    Error = sqlite3.Error

def translate_mysql_error(error):
    """Translates cryptic MySQL errors into human-friendly troubleshooting advice."""
    err_str = str(error)
    if "10061" in err_str:
        return "Connection Refused: MySQL is not running on the target PC, or it is being blocked by a Firewall. If this is a Client PC, ensure you entered the Host PC's IP address, not 'localhost'."
    if "1045" in err_str:
        return "Access Denied: Incorrect Username or Password. Ensure the MySQL user has permissions to connect from this PC."
    if "1044" in err_str:
        return "Database Not Found: The database name you entered does not exist on the server."
    if "2003" in err_str:
        return "Server Unreachable: Cannot find the host. Check the IP address and ensure both PCs are on the same network."
    return err_str

# Utility to check if MySQL is configured and working
def check_mysql_connection(host, user, password, database=None):
    try:
        conn = pymysql.connect(
            host=host,
            user=user,
            password=password,
            database=database,
            connect_timeout=5
        )
        conn.close()
        return True, "Connected"
    except Exception as e:
        return False, translate_mysql_error(e)

def log_audit(event_type, description, user_name="System"):
    """Global system for tracking network events, security changes, and admin actions.
    OPTIMIZED: Runs in a background thread to prevent UI blocking during DB write."""
    import threading
    def _task():
        import socket
        try:
            pc_name = socket.gethostname()
            conn = connect()
            conn.execute(
                "INSERT INTO audit_trail (event_type, description, pc_name, user_name) VALUES (?, ?, ?, ?)",
                (event_type, description, pc_name, user_name)
            )
            conn.commit()
        except:
            pass
    threading.Thread(target=_task, daemon=True).start()
