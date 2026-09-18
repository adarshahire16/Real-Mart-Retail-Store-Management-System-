import tkinter as tk
from tkinter import messagebox, ttk
import config_manager
import db_manager
import db_init
import theme as T
import os
import hardware_util

class SetupWizard:
    def __init__(self, root, callback):
        self.root = root
        self.callback = callback
        self.win = tk.Toplevel(root)
        self.win.title("Real Mart · Database Setup")
        self.win.geometry("500x580")
        self.win.configure(bg=T.BG_ROOT)
        self.win.resizable(False, False)
        
        # Center the window on the screen
        self.win.update_idletasks()
        width = 500
        height = 580
        screen_width = self.win.winfo_screenwidth()
        screen_height = self.win.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.win.geometry(f"{width}x{height}+{x}+{y}")
        
        # Make it modal
        self.win.transient(root)
        self.win.grab_set()
        
        # Variables
        self.db_type = tk.StringVar(value="sqlite")
        self.host = tk.StringVar(value="localhost")
        self.user = tk.StringVar(value="root")
        self.password = tk.StringVar(value="")
        self.database = tk.StringVar(value="real_mart")
        self.role = tk.StringVar(value="host") # 'host' or 'terminal'
        
        self.setup_ui()
        
    def setup_ui(self):
        # Header
        hdr = tk.Frame(self.win, bg=T.PRIMARY, height=70)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="🌱 Welcome to Real Mart", font=T.FONT_TITLE_MD, bg=T.PRIMARY, fg=T.WHITE).pack(pady=(10, 2))
        tk.Label(hdr, text="Let's configure your database to get started.", font=T.FONT_UI_SM, bg=T.PRIMARY, fg=T.WHITE).pack(pady=(0, 10))

        # Content Card
        card = tk.Frame(self.win, bg=T.CARD, padx=20, pady=10)
        card.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 10))

        tk.Label(card, text="Choose Storage Type", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=tk.W, pady=(0, 2))
        
        # Radio Buttons for Type (Side-by-side)
        rb_f = tk.Frame(card, bg=T.CARD)
        rb_f.pack(fill=tk.X, pady=2)
        
        r1 = tk.Radiobutton(rb_f, text="SQLite (Local)", variable=self.db_type, 
                          value="sqlite", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_ON_LIGHT, command=self.toggle_fields)
        r1.pack(side=tk.LEFT, padx=(0, 20))
        
        r2 = tk.Radiobutton(rb_f, text="MySQL (Multi-PC/LAN)", variable=self.db_type, 
                          value="mysql", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_ON_LIGHT, command=self.toggle_fields)
        r2.pack(side=tk.LEFT)

        # —— Role Selection ——
        tk.Label(card, text="This Computer's Role", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=tk.W, pady=(8, 2))
        role_f = tk.Frame(card, bg=T.CARD)
        role_f.pack(fill=tk.X, pady=2)
        
        tk.Radiobutton(role_f, text="Main PC (Admin + POS)", variable=self.role, value="host", 
                       font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(side=tk.LEFT, padx=(0, 20))
        tk.Radiobutton(role_f, text="Billing Counter (POS Only)", variable=self.role, value="terminal", 
                       font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(side=tk.LEFT)

        # MySQL Fields Container (Grid layout for compactness)
        self.mysql_f = tk.LabelFrame(card, text=" MySQL Settings ", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB, padx=10, pady=5)
        self.mysql_f.pack(fill=tk.X, pady=8)
        self.mysql_f.columnconfigure(0, weight=1)
        self.mysql_f.columnconfigure(1, weight=1)
        
        # Row 0: Host
        tk.Label(self.mysql_f, text="Host IP Address", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).grid(row=0, column=0, columnspan=2, sticky=tk.W)
        self.e_host = tk.Entry(self.mysql_f, textvariable=self.host, font=T.FONT_UI, relief="flat", highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        self.e_host.grid(row=1, column=0, columnspan=2, pady=(1, 5), ipady=3, sticky=tk.EW)
        
        # Row 1: Username & Password
        tk.Label(self.mysql_f, text="Username", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).grid(row=2, column=0, sticky=tk.W)
        tk.Label(self.mysql_f, text="Password", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).grid(row=2, column=1, sticky=tk.W, padx=(10, 0))
        
        e_user = tk.Entry(self.mysql_f, textvariable=self.user, font=T.FONT_UI, relief="flat", highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        e_user.grid(row=3, column=0, pady=(1, 5), ipady=3, sticky=tk.EW)
        
        e_pass = tk.Entry(self.mysql_f, textvariable=self.password, show="*", font=T.FONT_UI, relief="flat", highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        e_pass.grid(row=3, column=1, pady=(1, 5), ipady=3, sticky=tk.EW, padx=(10, 0))
        
        # Row 2: Database Name
        tk.Label(self.mysql_f, text="Database Name", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).grid(row=4, column=0, columnspan=2, sticky=tk.W)
        e_db = tk.Entry(self.mysql_f, textvariable=self.database, font=T.FONT_UI, relief="flat", highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        e_db.grid(row=5, column=0, columnspan=2, pady=(1, 5), ipady=3, sticky=tk.EW)
        
        # Apply entry styling
        for e in [self.e_host, e_user, e_pass, e_db]:
            T.entry_light(e)

        # Buttons (packed at bottom)
        btn_f = tk.Frame(card, bg=T.CARD)
        btn_f.pack(fill=tk.X, side=tk.BOTTOM, pady=(5, 0))

        self.btn_test = tk.Button(btn_f, text="⚡ Test Connection", command=self.test_connection)
        self.btn_test.pack(fill=tk.X, pady=3, ipady=6)
        T.btn_secondary(self.btn_test)

        self.btn_save = tk.Button(btn_f, text="✅ Complete Setup", command=self.save_setup, state=tk.DISABLED)
        self.btn_save.pack(fill=tk.X, pady=3, ipady=8)
        T.btn_primary(self.btn_save)

        self.toggle_fields()

    def toggle_fields(self):
        if self.db_type.get() == "sqlite":
            for child in self.mysql_f.winfo_children():
                if isinstance(child, tk.Entry): child.configure(state=tk.DISABLED)
            self.mysql_f.configure(text=" MySQL Settings (Disabled) ")
            self.btn_save.configure(state=tk.NORMAL) # SQLite always ready
        else:
            for child in self.mysql_f.winfo_children():
                if isinstance(child, tk.Entry): child.configure(state=tk.NORMAL)
            self.mysql_f.configure(text=" MySQL Settings ")
            self.btn_save.configure(state=tk.DISABLED) # Must test MySQL first

    def test_connection(self):
        self.btn_test.configure(text="⏳ Testing...", state=tk.DISABLED)
        self.win.update()
        
        db_type = self.db_type.get()
        if db_type == "sqlite":
            success, msg = True, "SQLite is ready (Local File)."
        else:
            # Temporary config for test
            success, msg = db_manager.check_mysql_connection(
                self.host.get(), self.user.get(), self.password.get(), self.database.get()
            )
            
        self.btn_test.configure(text="⚡ Test Connection", state=tk.NORMAL)
        if success:
            messagebox.showinfo("Success", f"Connection Successful!\n\n{msg}", parent=self.win)
            self.btn_save.configure(state=tk.NORMAL)
        else:
            messagebox.showerror("Failed", f"Could not connect:\n{msg}", parent=self.win)
            self.btn_save.configure(state=tk.DISABLED)

    def save_setup(self):
        config = config_manager.load_config()
        config["db_type"] = self.db_type.get()
        config["setup_complete"] = True
        if config["db_type"] == "mysql":
            config["mysql"] = {
                "host": self.host.get(),
                "user": self.user.get(),
                "password": self.password.get(),
                "database": self.database.get()
            }
        config["role"] = self.role.get()
        
        try:
            config_manager.save_config(config)
            
            # Run initialization
            self.win.title("Initializing Database...")
            db_init.ensure_database()
            
            # —— REGISTRATION LOGIC ——
            # If this is the Main PC, register its hardware ID in the shared DB
            if self.role.get() == "host":
                try:
                    conn = db_manager.connect(db_init.db_path())
                    hwid = hardware_util.get_machine_id()
                    conn.execute("UPDATE settings SET value = ? WHERE `key` = 'master_node_id'", (hwid,))
                    conn.commit()
                    conn.close()
                except Exception as e:
                    print(f"Warning: Failed to register master node hardware: {e}")

            messagebox.showinfo("Setup Complete", "Configuration saved! The application will now start.", parent=self.win)
            self.win.destroy()
            if self.callback: self.callback()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save or initialize:\n{e}", parent=self.win)

def show_wizard(root, on_complete):
    """Entry point to launch the wizard."""
    SetupWizard(root, on_complete)
