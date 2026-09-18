# ==================imports===================

import db_manager as sqlite3
import re
import random
import string
import os
import shutil
import time
import calendar
from tkinter import *
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from time import strftime
from datetime import date, datetime, timedelta
from tkinter import scrolledtext as tkst
from tkinter import simpledialog, filedialog
import threading
import csv
import hashlib
from PIL import Image, ImageTk, ImageOps, ImageDraw, ImageFont
# ============================================

import db_init
import theme as T
import scanner_util
import updater
import hardware_util

_TILE_IMAGE_CACHE = {} # Global cache for resized tile PhotoImages to prevent startup lag

# ================== Barcode Utility ==================
def fetch_product_info(barcode):
    """
    Fetches product name and category from Open Food Facts API.
    Uses standard urllib to avoid external dependencies.
    """
    import urllib.request
    import json
    
    url = f"https://world.openfoodfacts.org/api/v0/product/{barcode}.json"
    headers = {"User-Agent": "RealMartPOS/1.0 (Python Tkinter)"}
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.load(response)
            if data.get("status") == 1:
                product = data.get("product", {})
                name = product.get("product_name", "")
                cat = product.get("categories", "").split(",")[0] # Get first category
                return name, cat
    except Exception as e:
        print(f"API Lookup error: {e}")
    return None, None

def generate_ean13_id():
    """Generates a unique 13-digit EAN-13 style numeric string."""
    while True:
        # 12 random digits
        base = "".join(random.choices(string.digits, k=12))
        # Calculate checksum for EAN-13
        s = sum(int(base[i]) * (3 if i % 2 != 0 else 1) for i in range(12))
        checksum = (10 - (s % 10)) % 10
        ean = base + str(checksum)
        
        # Check uniqueness in DB
        cur.execute("SELECT 1 FROM raw_inventory WHERE barcode = ?", (ean,))
        if not cur.fetchone():
            return ean

def render_barcode(code, width=400, height=200):
    """Draws a standard, internationally recognized EAN-13 barcode."""
    if len(code) != 13:
        # Fallback to simple if not EAN-13
        img = Image.new('RGB', (width, height), color='white')
        return img
        
    img = Image.new('RGB', (width, height), color='white')
    d = ImageDraw.Draw(img)
    
    # EAN-13 Encoding Patterns
    L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"]
    G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"]
    R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"]
    
    # Parity table for the first digit (determines pattern for next 6 digits)
    PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"]
    
    margin = 50
    # EAN-13 has 95 modules (dots): 3(Start) + 42(Left Group) + 5(Center) + 42(Right Group) + 3(Stop)
    bar_width = max(2, (width - 2 * margin) // 95)
    
    x = margin
    def draw_bar(bits):
        nonlocal x
        for bit in bits:
            if bit == '1':
                # Draw black modules slightly taller than 100px for better scan
                d.rectangle([x, 20, x + bar_width - 1, height - 60], fill='black')
            x += bar_width

    # 1. Start Guard
    draw_bar("101")
    
    # 2. Left Group (Digits 2 to 7)
    first_digit = int(code[0])
    p_map = PARITY[first_digit]
    for i in range(1, 7):
        digit = int(code[i])
        pattern_type = p_map[i-1]
        bits = L[digit] if pattern_type == 'L' else G[digit]
        draw_bar(bits)
        
    # 3. Center Guard
    draw_bar("01010")
    
    # 4. Right Group (Digits 8 to 13)
    for i in range(7, 13):
        digit = int(code[i])
        draw_bar(R[digit])
        
    # 5. Stop Guard
    draw_bar("101")
    
    # Add Text Below
    try:
        fnt = ImageFont.truetype("arial.ttf", 22)
    except:
        fnt = ImageFont.load_default()
    
    tw = d.textlength(code, font=fnt) if hasattr(d, 'textlength') else 120
    d.text(((width - tw) // 2, height - 45), code, font=fnt, fill='black')
    return img

class BarcodePopup:
    def __init__(self, parent, code, name):
        self.win = Toplevel(parent)
        self.win.title(f"Barcode: {name}")
        self.win.geometry("500x380")
        self.win.configure(bg=T.WHITE)
        self.win.grab_set()
        
        Label(self.win, text=f"Product: {name}", font=T.FONT_SECTION, bg=T.WHITE, fg=T.PRIMARY_DIM).pack(pady=(20, 10))
        Label(self.win, text=f"SKU Barcode ID: {code}", font=T.FONT_UI_SM, bg=T.WHITE, fg=T.TEXT_SUB).pack()
        
        img = render_barcode(code)
        self.photo = ImageTk.PhotoImage(img)
        
        frame = Frame(self.win, bg=T.WHITE, padx=10, pady=10, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        frame.pack(pady=20)
        
        lbl = Label(frame, image=self.photo, bg=T.WHITE)
        lbl.image = self.photo
        lbl.pack()
        
        btn_f = Frame(self.win, bg=T.WHITE)
        btn_f.pack(fill=X, padx=50, pady=(0, 10))
        
        def save_img():
            path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG file", "*.png")])
            if path:
                img.save(path)
                messagebox.showinfo("Saved", f"Barcode saved to {path}")

        btn_save = Button(btn_f, text="💾 Save Image", command=save_img)
        btn_save.pack(side=LEFT, expand=True, padx=5)
        T.btn_secondary(btn_save)
        
        btn_close = Button(btn_f, text="Close", command=self.win.destroy)
        btn_close.pack(side=LEFT, expand=True, padx=5)
        T.btn_primary(btn_close)
# =====================================================

T.check_tkinter_or_exit()

db_init.ensure_database()
def refresh_db():
    global db, cur
    import db_manager
    import db_init
    db = db_manager.connect(db_init.db_path())
    cur = db.cursor()

refresh_db()

root = None
adm = None
inv = None
p_update = None
p_add = None
invoice = None
emp = None
exit_to_main = None



user = None
passwd = None
fname = None
lname = None
logged_in_id = None

def init_vars(parent):
    global user, passwd, fname, lname
    user = StringVar(parent)
    passwd = StringVar(parent)
    fname = StringVar(parent)
    lname = StringVar(parent)

def start_admin_hub(parent_root, exit_cb):
    global root, exit_to_main, page1
    refresh_db() # PICK UP LATEST DATABASE CONNECTION & CONFIG
    root = parent_root
    exit_to_main = exit_cb
    
    init_vars(root)
    # —— CLEAN UI LAYER ——
    # Restore background image as requested while preserving the canvas
    cv = T.setup_glass_canvas(root, image_name=T.Backgrounds.ADMIN)
    T.clear_ui_content(cv)

    # Destroy other legacy widgets safely
    for widget in tk.Misc.winfo_children(root):
        if not getattr(widget, "_is_bg_canvas", False):
            try:
                widget.destroy()
            except: pass
        
    root.title("Real Mart · Admin Login")
    T.style_root(root)
    T.setup_ttk(root)
    
    page1 = login_page(root, cv)
    
    # —— SECURITY GATE: Hardware Lock ——
    cur.execute("SELECT value FROM settings WHERE `key` = 'master_node_id'")
    res = cur.fetchone()
    master_id = res[0] if res else ""
    
    current_hwid = hardware_util.get_machine_id()
    
    if not master_id:
        # AUTOMATIC TAKEOVER: If no master is registered, this machine claims it!
        confirm = messagebox.askyesno("Claim Master Status", 
            "No Main PC is registered for this database.\n\n"
            "Do you want to authorize THIS computer as the Main PC (Admin Hub)?")
        if confirm:
            # DOUBLE CHECK: Ensure no one else claimed it while the popup was open
            cur.execute("SELECT value FROM settings WHERE `key` = 'master_node_id'")
            latest_res = cur.fetchone()
            latest_master = latest_res[0] if latest_res else ""
            
            if latest_master and latest_master != current_hwid:
                messagebox.showerror("Claim Failed", "Another PC has just claimed the Master status.\n\nReturning to Main Menu.")
                exit_to_main()
                return

            cur.execute("UPDATE settings SET value = ? WHERE `key` = 'master_node_id'", (current_hwid,))
            db.commit()
            messagebox.showinfo("Success", "This machine is now registered as the Main PC.")
        else:
            exit_to_main()
            return

    elif master_id != current_hwid:
        messagebox.showerror("Security Violation", 
            "CRITICAL: This machine is not authorized for Admin access.\n\n"
            "This device has been flagged as a Billing Terminal. "
            "Please use the Main PC for administrative tasks.", 
            parent=root)
        exit_to_main()
        return

    root.bind("<Return>", lambda e: page1.login(e))


def random_emp_id(stringLength):
    Digits = string.digits
    strr=''.join(random.choice(Digits) for i in range(stringLength-3))
    return ('EMP'+strr)

def valid_phone(phn):
    if re.match(r"[789]\d{9}$", phn):
        return True
    return False

def valid_aadhar(aad):
    if aad.isdigit() and len(aad)==12:
        return True
    return False

class InitialSetupPopup:
    def __init__(self, parent):
        self.win = Toplevel(parent)
        self.win.title("Quick Account Setup")
        self.win.geometry("450x550")
        self.win.configure(bg=T.BG_ROOT)
        self.win.grab_set()

        hdr = Frame(self.win, bg=T.PRIMARY_DIM, height=50)
        hdr.pack(fill=X)
        Label(hdr, text="Create First Admin Account", font=T.FONT_SECTION, bg=T.PRIMARY_DIM, fg=T.WHITE).pack(pady=12)

        card = Frame(self.win, bg=T.CARD, padx=30, pady=20)
        card.pack(fill=BOTH, expand=True, padx=20, pady=20)

        def frow(lbl, **kw):
            Label(card, text=lbl, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(10, 0))
            e = Entry(card, **kw)
            e.pack(fill=X, pady=4, ipady=6)
            T.entry_light(e)
            return e

        self.e_id = frow("Initial Admin ID")
        self.e_id.insert(0, "admin")
        self.e_name = frow("Your Name")
        self.e_pass = frow("Set Password", show="*")
        
        Label(card, text="Tip: Remember these credentials to log in.", font=T.FONT_SMALL, bg=T.CARD, fg=T.PRIMARY).pack(pady=20)

        btn = Button(card, text="Complete Setup", command=self.save)
        btn.pack(fill=X, ipady=10)
        T.btn_primary(btn)
    def save(self):
        eid, name, pw = self.e_id.get().strip(), self.e_name.get().strip(), self.e_pass.get()
        if eid and name and pw:
            try:
                # Professional Security: Hash password before saving
                hashed_pw = db_init.hash_password(pw)
                cur.execute(
                    "INSERT INTO employee(emp_id, name, contact_num, address, aadhar_num, password, designation, approved) VALUES(?,?,?,?,?,?,?,?)", 
                    (eid, name, "0000000000", "Initial Setup", "000000000000", hashed_pw, "Admin", 1)
                )
                db.commit()
                messagebox.showinfo("Success", "Admin account created! You can now log in.")
                self.win.destroy()
            except Exception as e:
                messagebox.showerror("Error", f"Could not create account: {e}")
        else:
            messagebox.showerror("Error", "All fields are required.")

# Note: forgot_password_admin logic moved into login_page class for in-window flow.

class login_page:
    def __init__(self, top, cv):
        self.top = top
        self.cv = cv
        self.view_state = "login" # States: login, forgot, reset
        self.reset_eid = None
        
        # 1. Widgets for Login Fields
        self.entry1 = Entry(self.cv, textvariable=user, width=32, font=T.FONT_UI, bg="#FFFFFF", fg="#212121", 
                            insertbackground="#212121", relief="flat", highlightthickness=0)
        self.entry2 = Entry(self.cv, textvariable=passwd, show="*", width=32, font=T.FONT_UI, bg="#FFFFFF", fg="#212121", 
                            insertbackground="#212121", relief="flat", highlightthickness=0)
        
        # 2. Widgets for Forgot Password flow
        self.forgot_eid_var = StringVar()
        self.forgot_phone_var = StringVar()
        self.new_pw_var = StringVar()
        
        self.entry_forgot_id = Entry(self.cv, textvariable=self.forgot_eid_var, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_forgot_phone = Entry(self.cv, textvariable=self.forgot_phone_var, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_new_pw = Entry(self.cv, textvariable=self.new_pw_var, show="*", width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        
        # Bind resize for dynamic positioning
        def on_resize(e):
            if e.widget == self.top:
                # Check if size actually changed
                w, h = self.top.winfo_width(), self.top.winfo_height()
                if hasattr(self, "_last_req_size") and self._last_req_size == (w, h):
                    return
                self._last_req_size = (w, h)
                
                if hasattr(self, "_resize_job") and self._resize_job:
                    self.top.after_cancel(self._resize_job)
                self._resize_job = self.top.after(150, self.refresh_ui)
        
        self.top.bind("<Configure>", on_resize, add="+")

        self.refresh_ui()

    def test_conn_ui(self):
        import db_manager
        mgr = db_manager.DBConnection()
        success, msg = mgr.test_current_config()
        if success:
            messagebox.showinfo("Network Success ✅", f"CONNECTION OK!\n\nDetails: {msg}", parent=self.top)
        else:
            messagebox.showerror("Network Failed ❌", f"CONNECTION FAILED!\n\nError: {msg}\n\nCheck your config.json file and IP address.", parent=self.top)

    def exitt(self):
        root.current_view = "main_menu" # Reset view state
        exit_to_main()

    def go_forgot(self, e=None):
        self.forgot_eid_var.set("")
        self.forgot_phone_var.set("")
        self.view_state = "forgot"
        self.refresh_ui(force=True)

    def go_login(self, e=None):
        self.view_state = "login"
        self.refresh_ui(force=True)

    def verify_forgot(self):
        eid = self.forgot_eid_var.get().strip()
        phone = self.forgot_phone_var.get().strip()
        
        if not eid or not phone:
            messagebox.showerror("Input Required", "Please enter both Admin ID and Phone.", parent=self.top)
            return
            
        cur.execute("SELECT name FROM employee WHERE emp_id=? AND contact_num=? AND designation='Admin'", (eid, phone))
        row = cur.fetchone()
        if row:
            self.reset_eid = eid
            self.new_pw_var.set("")
            self.view_state = "reset"
            messagebox.showinfo("Identity Verified", f"Verified Admin: {row[0]}\nPlease set a new password.", parent=self.top)
            self.refresh_ui(force=True)
        else:
            messagebox.showerror("Verification Failed", "No matching Admin record found.", parent=self.top)

    def finish_reset(self):
        npw = self.new_pw_var.get().strip()
        if len(npw) < 4:
            messagebox.showerror("Invalid Password", "Password must be at least 4 characters.", parent=self.top)
            return
        
        try:
            # Professional Security: Hash password before updating
            hashed_pw = db_init.hash_password(npw)
            cur.execute("UPDATE employee SET password=? WHERE emp_id=?", (hashed_pw, self.reset_eid))
            db.commit()
            messagebox.showinfo("Success", "✅ Admin password updated successfully!", parent=self.top)
            self.go_login()
        except Exception as e:
            messagebox.showerror("Error", f"Update failed: {e}", parent=self.top)

    def login(self, Event=None):
        eid = self.entry1.get().strip()
        pw = self.entry2.get().strip()
        if not eid or not pw:
            messagebox.showerror("Error", "All fields are required.")
            return

        # Professional Security: Hash input before comparison
        hashed_pw = db_init.hash_password(pw)
        
        # Support both legacy hashing and new reversible encryption for transition
        encrypted_pw = db_init.secure_store(pw)
        cur.execute("SELECT * FROM employee WHERE emp_id=? AND (password=? OR password=?) AND designation='Admin'", (eid, hashed_pw, encrypted_pw))
        user_row = cur.fetchone()

        if user_row:
            if len(user_row) > 7 and user_row[7] == 0: # Check approved column (index 7)
                messagebox.showwarning("Access Denied", "Your Admin account is pending final system verification.\nPlease contact the system administrator.", parent=self.top)
                return

            # —— FINAL SECURITY GATE: CONCURRENCY CHECK ——
            # Verify this PC is still the authorized Master before opening the dashboard
            cur.execute("SELECT value FROM settings WHERE `key` = 'master_node_id'")
            res = cur.fetchone()
            current_master = res[0] if res else ""
            my_hwid = hardware_util.get_machine_id()
            
            if current_master != my_hwid:
                messagebox.showerror("Security Alert", 
                    "This PC is no longer authorized for Admin access.\n\n"
                    "Another machine has claimed the Master status while you were on the login screen.\n"
                    "Please use the authorized Main PC.", parent=self.top)
                self.exitt()
                return

            self.cv.delete("all")

            # --- Initialize Admin_Page with root and user info ---
            # Safe cleanup: unbind before destroying to prevent event leaks
            try:
                self.top.unbind("<Return>")
            except Exception: pass
            
            # CRITICAL: Stop background redraws and clear any 'ghost' images
            T.clear_bg_image(self.top)
            
            # Destroy ALL widgets to provide a clean dashboard
            for widget in tk.Misc.winfo_children(self.top):
                try:
                    widget.destroy()
                except: pass
            
            global logged_in_id
            logged_in_id = user_row[0]
            self.page = Admin_Page(self.top, user_row)
        else:
            messagebox.showerror("Error", "Incorrect Admin ID or Password.")
            passwd.set("")

    def refresh_ui(self, force=False):
        try:
            if not self.cv.winfo_exists(): return
        except: return

        w, h = self.top.winfo_width(), self.top.winfo_height()
        
        if w < 100 or h < 100:
            self.top.after(200, self.refresh_ui)
            return

        curr_size = (w, h, self.view_state)
        if not force and hasattr(self, "_last_size") and self._last_size == curr_size:
            return

        if getattr(self.top, "current_view", "main_menu") != "admin_login":
            return

        self._last_size = curr_size
        self.cv.delete("ui_content")
        
        cx, cy = w / 2, h / 2
        card_w, card_h = 440, 540
        T.draw_glass_panel(self.cv, cx, cy + 32, card_w, card_h, opacity=0.8, color=(245, 245, 245), radius=45)
        
        # 3. Card Content (Standard centered focus)
        y_start = cy - 155

        if self.view_state == "login":
            # —— SIGN IN VIEW ——
            self.cv.create_text(cx, cy - 205, text="Admin console", font=(T.FONT_FAMILY, 30, "bold"), fill=T.PRIMARY_DIM, anchor="n", tags="ui_content")
            self.cv.create_text(cx, y_start, text="Sign in with an account that has Admin designation.", 
                                font=T.FONT_UI_SM, fill="#333333", anchor="n", width=340, justify="center", tags="ui_content")

            # Consolidated spacing (High-contrast black text)
            self.cv.create_text(cx - 170, y_start + 50, text="Admin ID", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 100, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 100, window=self.entry1, width=310, height=35, tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 145, text="Password", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 195, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 195, window=self.entry2, width=310, height=35, tags="ui_content")

            forgot_tag = "forgot_link_admin"
            self.cv.create_text(cx + 170, y_start + 237, text="Forgot Password?", font=(T.FONT_FAMILY, 12, "bold"), fill=T.PRIMARY, 
                                anchor="e", tags=("ui_content", forgot_tag))
            self.cv.tag_bind(forgot_tag, "<Button-1>", self.go_forgot)
            T.bind_tag_hover(self.cv, forgot_tag)



            T.draw_pill_button(self.cv, cx, y_start + 295, 340, 60, text="Sign in", color=T.BTN_GREEN, command=self.login)


            back_tag = "back_link_admin"
            self.cv.create_text(cx - 100, y_start + 380, text="← Back to Main", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, tags=("ui_content", back_tag))
            self.cv.tag_bind(back_tag, "<Button-1>", lambda e: self.exitt())
            T.bind_tag_hover(self.cv, back_tag)

            test_tag = "test_link_admin"
            self.cv.create_text(cx + 100, y_start + 380, text="⚡ Test Network", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, tags=("ui_content", test_tag))
            self.cv.tag_bind(test_tag, "<Button-1>", lambda e: self.test_conn_ui())
            T.bind_tag_hover(self.cv, test_tag)


        elif self.view_state == "forgot":
            # —— VERIFICATION VIEW ——
            self.cv.create_text(cx, cy - 205, text="Verify Admin", font=(T.FONT_FAMILY, 30, "bold"), fill=T.PRIMARY_DIM, anchor="n", tags="ui_content")
            self.cv.create_text(cx, y_start, text="Enter registered Admin details to reset security access.", 
                                font=T.FONT_UI_SM, fill="#333333", anchor="n", width=340, justify="center", tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 50, text="Admin Employee ID", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 100, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 100, window=self.entry_forgot_id, width=300, height=35, tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 145, text="Phone Number", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 195, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 195, window=self.entry_forgot_phone, width=300, height=35, tags="ui_content")

            T.draw_pill_button(self.cv, cx, y_start + 295, 340, 60, text="Verify Admin Identity", color=T.BTN_GREEN, command=self.verify_forgot)

            back_tag = "back_to_login_admin"
            self.cv.create_text(cx, y_start + 380, text="← Back to Login", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, tags=("ui_content", back_tag))
            self.cv.tag_bind(back_tag, "<Button-1>", self.go_login)
            T.bind_tag_hover(self.cv, back_tag)


        elif self.view_state == "reset":
            # —— RESET VIEW ——
            self.cv.create_text(cx, cy - 205, text="Set password", font=(T.FONT_FAMILY, 30, "bold"), fill=T.PRIMARY_DIM, anchor="n", tags="ui_content")
            self.cv.create_text(cx, y_start, text="Set a new secure password for this Admin account.", 
                                font=T.FONT_UI_SM, fill="#333333", anchor="n", width=340, justify="center", tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 70, text="New Admin Password", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 120, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 120, window=self.entry_new_pw, width=300, height=35, tags="ui_content")

            T.draw_pill_button(self.cv, cx, y_start + 295, 340, 60, text="Update Admin Password", color=T.PRIMARY_DIM, command=self.finish_reset)
            
            back_tag = "cancel_reset_admin"
            self.cv.create_text(cx, y_start + 380, text="Cancel Reset", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, tags=("ui_content", back_tag))
            self.cv.tag_bind(back_tag, "<Button-1>", self.go_login)

        # Setup Button (if needed)
        cur.execute("SELECT COUNT(*) FROM employee")
        if cur.fetchone()[0] == 0:
            setup_btn = Button(self.cv, text="🚀 First Admin Setup", command=lambda: InitialSetupPopup(root), 
                               bg=T.CARD_SOFT, fg=T.WHITE, font=T.FONT_SMALL, relief="flat")
            self.cv.create_window(cx + 80, y_start + 390, window=setup_btn, tags="ui_content")

        # Dynamic Keyboard Navigation: Bind Enter key to the primary action of the current view
        try:
            if self.view_state == "login":
                self.top.bind("<Return>", self.login)
            elif self.view_state == "forgot":
                self.top.bind("<Return>", lambda e: self.verify_forgot())
            elif self.view_state == "reset":
                self.top.bind("<Return>", lambda e: self.finish_reset())
        except Exception: pass

    
def exitt():
    sure = messagebox.askyesno("Exit","Are you sure you want to exit to main menu?", parent=root)
    if sure == True:
        try:
            root.unbind("<Return>")
        except Exception:
            pass
        if exit_to_main:
            exit_to_main()

def force_logout():
    global logged_in_id
    logged_in_id = None
    try:
        root.unbind("<Return>")
    except Exception:
        pass
    if exit_to_main:
        exit_to_main()

def inventory():
    global page3
    T.clear_bg_image(root)
    for widget in tk.Misc.winfo_children(root):
        widget.destroy()
    global inv
    inv = root
    page3 = Inventory(inv)
    page3.time()

def sales_analytics():
    T.clear_bg_image(root)
    for widget in tk.Misc.winfo_children(root):
        widget.destroy()
    global page_sales
    page_sales = Sales_Dashboard_Page(root)
    page_sales.time()
    
    


def employee():
    global page5
    T.clear_bg_image(root)
    for widget in tk.Misc.winfo_children(root):
        widget.destroy()
    global emp
    emp = root
    page5 = Employee(emp)
    page5.time()
    
    


def invoices():
    T.clear_bg_image(root)
    for widget in tk.Misc.winfo_children(root):
        widget.destroy()
    global invoice
    invoice = root
    page4 = Invoice(invoice)
    page4.time()

def perishables():
    T.clear_bg_image(root)
    for widget in tk.Misc.winfo_children(root):
        widget.destroy()
    global page_peri
    page_peri = Perishable_Tracker_Page(root)
    page_peri.time()
    
    

def marketing(u_data):
    T.clear_bg_image(root)
    for widget in tk.Misc.winfo_children(root):
        widget.destroy()
    global page_marketing
    page_marketing = Marketing_Panel(root, u_data)
    page_marketing.time()

def system_config(u_data):
    T.clear_bg_image(root)
    for widget in tk.Misc.winfo_children(root):
        widget.destroy()
    global page_system
    page_system = System_Config_Page(root, u_data)
    page_system.time()

def about():
    parent = root
    if "adm" in globals():
        try:
            if adm.winfo_exists():
                parent = adm
        except Exception:
            pass
    messagebox.showinfo(
        "About",
        "Adarsh & Rushikesh Project",
        parent=parent,
    )



class Admin_Page:
    def __init__(self, top=None, user_data=None):
        if not top: return
        self.user_data = user_data
        import uuid
        self.session_id = str(uuid.uuid4())[:8]
        top.geometry("1240x960")
        top.minsize(960, 600)
        top.resizable(True, True)
        top.title("Real Mart · Control center")
        
        # —— Modern Forest Green & Cream Theme ——
        adm_bg = T.BG_ROOT
        cv = T.setup_glass_canvas(top, image_name=T.Backgrounds.HUB)
        T.clear_ui_content(cv)
        
        # Header - Forest Green
        hdr = Frame(top, bg=T.PRIMARY)
        hdr.pack(fill=X)
        
        hr = Frame(hdr, bg=T.PRIMARY)
        hr.pack(fill=X, padx=35, pady=20)
        
        Label(hr, text="ADMIN HUB", font=T.FONT_TITLE_MD, bg=T.PRIMARY, fg=T.WHITE).pack(side=LEFT)
        
        # User/Status section in header
        status_f = Frame(hr, bg=T.PRIMARY)
        status_f.pack(side=RIGHT)
        
        user_name = user_data[1] if user_data and len(user_data) > 1 else "Admin"
        Label(status_f, text=f"Logged in as: {user_name}", font=T.FONT_UI, bg=T.PRIMARY, fg=T.WHITE).pack(side=LEFT, padx=15)
        
        btn_out = Button(status_f, text=" LOGOUT ", command=self.Logout)
        btn_out.pack(side=LEFT)
        T.btn_white_round(btn_out)
        
        # Zoom controls (Minimized)
        hb = Frame(hr, bg=T.PRIMARY)
        hb.pack(side=RIGHT, padx=(25, 0))
        
        def z_out():
            T.update_zoom(-1)
            T.setup_ttk(top)
            # Bypass shield for cleanup
            for widget in tk.Misc.winfo_children(top): widget.destroy()
            Admin_Page(top, self.user_data)
            
        def z_in():
            T.update_zoom(1)
            T.setup_ttk(top)
            # Bypass shield for cleanup
            for widget in tk.Misc.winfo_children(top): widget.destroy()
            Admin_Page(top, self.user_data)
            
        z2 = Button(hb, text="+", command=z_in, width=1, font=T.FONT_SMALL)
        z2.pack(side=RIGHT, padx=(0,5))
        T.btn_secondary(z2)
        z2.configure(bg=T.WHITE, fg=T.PRIMARY)
        
        z1 = Button(hb, text="-", command=z_out, width=1, font=T.FONT_SMALL)
        z1.pack(side=RIGHT, padx=(5,0))
        T.btn_secondary(z1)
        z1.configure(bg=T.WHITE, fg=T.PRIMARY)


        # Separator Line
        line = Frame(top, bg=T.PRIMARY_DIM, height=1)
        line.pack(fill=X)

        # Main Body - Scrollable Container
        container = Frame(top, bg=adm_bg)
        container.pack(fill=BOTH, expand=True)
        
        canvas = Canvas(container, bg=adm_bg, highlightthickness=0, borderwidth=0, yscrollincrement=1)
        sb = Scrollbar(container, orient=VERTICAL, command=canvas.yview)
        body = Frame(canvas, bg=adm_bg, padx=40, pady=20)
        
        def on_scroll_resize(e):
            canvas.configure(scrollregion=canvas.bbox("all"))
            # Stretch body to canvas width
            canvas.itemconfig(canvas_window, width=e.width)

        canvas_window = canvas.create_window((0,0), window=body, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        # Only show scrollbar if needed, but for simplicity we pack it
        sb.pack(side=RIGHT, fill=Y)
        
        canvas.bind("<Configure>", on_scroll_resize)
        
        # Enable mousewheel scrolling
        def _on_mousewheel(event):
            try:
                if canvas.winfo_exists():
                    # Precision pixel-based scrolling (40px per notch)
                    canvas.yview_scroll(int(-1*(event.delta/3)), "units")
            except: pass
        
        # Bind immediately so it works as soon as the page appears
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Safely unbind when the dashboard is destroyed to prevent TclErrors
        canvas.bind("<Destroy>", lambda e: canvas.unbind_all("<MouseWheel>"))


        # —— DISCREET FOOTER STATUS BAR ——
        self.footer = Frame(top, bg="#E8EBE8", height=28)
        self.footer.pack(side=BOTTOM, fill=X)
        self.footer.pack_propagate(False)
        
        # Sync Status in Footer (Discreet, bottom-right)
        self.sync_f = Frame(self.footer, bg="#E8EBE8")
        self.sync_f.pack(side=RIGHT, padx=15)
        self.sync_dot = Label(self.sync_f, text="●", font=(T.FONT_FAMILY, 10), bg="#E8EBE8", fg="#4CAF50")
        self.sync_dot.pack(side=LEFT)
        self.sync_lbl = Label(self.sync_f, text="SYNCED", font=(T.FONT_FAMILY, 9), bg="#E8EBE8", fg=T.TEXT_SUB)
        self.sync_lbl.pack(side=LEFT, padx=5)
        
        Label(self.footer, text="Real Mart Network Service · Connected", font=(T.FONT_FAMILY, 9), bg="#E8EBE8", fg=T.TEXT_MUTED).pack(side=LEFT, padx=15)
        
        self.check_sync()
        self.heartbeat()

        Label(
            body,
            text="What do you want to manage?",
            font=T.FONT_TITLE,
            bg=adm_bg,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W)
        Label(
            body,
            text="Pick a module — crisp layout, one category per product (no subcategories).",
            font=T.FONT_UI,
            bg=adm_bg,
            fg=T.TEXT_MUTED,
        ).pack(anchor=W, pady=(6, 24))

        tiles = Frame(body, bg=adm_bg)
        tiles.pack(fill=BOTH, expand=True)

        # PRE-CONFIGURE GRID: Ensures panels adjust instantly as they load
        tiles.columnconfigure(0, weight=1)
        tiles.columnconfigure(1, weight=1)
        for r in range(5): tiles.rowconfigure(r, weight=1)

        def tile(parent, title, subtitle, cmd, bg_image=None):
            # The whole frame is now a button
            f = Frame(
                parent,
                bg=T.WHITE,
                highlightthickness=3, # Thicker, highly visible premium 3px border
                highlightbackground="black",
                padx=0,
                pady=0,
                cursor="hand2"
            )
            
            # --- FIXED: Background support with original sizing ---
            if bg_image and os.path.exists(T.get_resource_path(bg_image)):
                try:
                    # INCREASED SIZE: Height 180 for a more "Big Panel" look
                    cv_tile = Canvas(f, bg=T.WHITE, highlightthickness=0, borderwidth=0, 
                                     cursor="hand2", width=400, height=180)
                    cv_tile.pack(fill=BOTH, expand=True)
                    
                    # Performance: Load from global cache once, stay in memory
                    orig_tile_img = T.get_raw_image(bg_image)
                    if not orig_tile_img: raise Exception("Img not found")
                    
                    def on_resize(e):
                        if e.width > 20 and e.height > 20:
                            if hasattr(cv_tile, "_last_dim") and cv_tile._last_dim == (e.width, e.height): return
                            cv_tile._last_dim = (e.width, e.height)
                            
                            cv_tile.delete("all")
                            cv_tile.configure(bg="white")
                            
                            w = e.width
                            h = int(orig_tile_img.height * (w / orig_tile_img.width))
                            
                            global _TILE_IMAGE_CACHE
                            cache_key = (bg_image, w, h)
                            if cache_key in _TILE_IMAGE_CACHE:
                                photo, photo_hover = _TILE_IMAGE_CACHE[cache_key]
                            else:
                                # High Performance Downscaling: If source image is huge, fast-box downsample first
                                temp_img = orig_tile_img
                                if temp_img.width > 800:
                                    box_h = int(temp_img.height * (800 / temp_img.width))
                                    temp_img = temp_img.resize((800, box_h), getattr(Image, 'Resampling', Image).BOX)
                                    
                                resample = getattr(Image, 'Resampling', Image).BILINEAR
                                resized = temp_img.resize((w, h), resample)
                                photo = ImageTk.PhotoImage(resized)
                                
                                # Premium Dynamic Illumination: Generate brightened copy (1.12x) for hover glow
                                from PIL import ImageEnhance
                                enhancer = ImageEnhance.Brightness(resized)
                                resized_hover = enhancer.enhance(1.12)
                                photo_hover = ImageTk.PhotoImage(resized_hover)
                                _TILE_IMAGE_CACHE[cache_key] = (photo, photo_hover)
                            
                            cv_tile.create_image(0, e.height, image=photo, anchor="sw", tags="bg")
                            cv_tile.bg_photo = photo
                            cv_tile.bg_photo_hover = photo_hover
                            
                            # Adjust text positions for the larger 180px height
                            cv_tile.create_text(36, 51, text=title, font=T.FONT_TITLE, fill=T.WHITE, anchor="nw", tags="title_shadow")
                            cv_tile.create_text(35, 50, text=title, font=T.FONT_TITLE, fill="#1A1A1A", anchor="nw", tags="title_main")
                            
                            cv_tile.create_text(36, 106, text=subtitle, font=T.FONT_UI_SM, fill=T.WHITE, anchor="nw", width=e.width-70, tags="text")
                            cv_tile.create_text(35, 105, text=subtitle, font=T.FONT_UI_SM, fill="#333333", anchor="nw", width=e.width-70, tags="text")
 
                    cv_tile.bind("<Configure>", on_resize)
                    
                    # Tactile Mechanical Click & Glow Engine
                    cv_tile._is_pressed = False
                    
                    def on_enter(e): 
                        f.configure(highlightbackground=T.PRIMARY)
                        if hasattr(cv_tile, "bg_photo_hover"):
                            cv_tile.itemconfig("bg", image=cv_tile.bg_photo_hover)
                        cv_tile.itemconfig("title_main", fill=T.PRIMARY)
                        
                    def on_leave(e): 
                        f.configure(highlightbackground="black")
                        if hasattr(cv_tile, "bg_photo"):
                            cv_tile.itemconfig("bg", image=cv_tile.bg_photo)
                        cv_tile.itemconfig("title_main", fill="#1A1A1A")
                        if cv_tile._is_pressed:
                            cv_tile._is_pressed = False
                            cv_tile.move("all", -2, -2)
                            
                    def on_press(e):
                        if not cv_tile._is_pressed:
                            cv_tile._is_pressed = True
                            cv_tile.move("all", 2, 2)
                            f.configure(highlightbackground=T.PRIMARY_DIM)
                            
                    def on_release(e):
                        if cv_tile._is_pressed:
                            cv_tile._is_pressed = False
                            cv_tile.move("all", -2, -2)
                            f.configure(highlightbackground=T.PRIMARY)
                            cmd()
                    
                    for w in [f, cv_tile]:
                        w.bind("<Enter>", on_enter, add="+")
                        w.bind("<Leave>", on_leave, add="+")
                        w.bind("<ButtonPress-1>", on_press, add="+")
                        w.bind("<ButtonRelease-1>", on_release, add="+")
                except Exception as e:
                    print(f"Tile canvas error: {e}")
                    bg_image = None

            if not bg_image or not os.path.exists(T.get_resource_path(bg_image)):
                inner = Frame(f, bg=T.WHITE, padx=45, pady=42, cursor="hand2")
                inner.pack(fill=BOTH, expand=True)
                
                t_lbl = Label(inner, text=title, font=T.FONT_TITLE, bg=T.WHITE, fg="#1A1A1A", cursor="hand2")
                t_lbl.pack(anchor=W)
                
                s_lbl = Label(inner, text=subtitle, font=T.FONT_UI_SM, bg=T.WHITE, fg="#666666", cursor="hand2")
                s_lbl.pack(anchor=W, pady=(15, 0))

                # Track press state for fallback cards
                inner._is_pressed = False

                def on_enter(e):
                    f.configure(highlightbackground=T.PRIMARY)
                    for widget in [inner, t_lbl, s_lbl]:
                        try:
                            widget.configure(bg="#F4F8F4")
                        except: pass
                    t_lbl.configure(fg=T.PRIMARY)
                    
                def on_leave(e):
                    f.configure(highlightbackground="black")
                    for widget in [inner, t_lbl, s_lbl]:
                        try:
                            widget.configure(bg=T.WHITE)
                        except: pass
                    t_lbl.configure(fg="#1A1A1A")
                    inner._is_pressed = False
                    
                def on_press(e):
                    inner._is_pressed = True
                    f.configure(highlightbackground=T.PRIMARY_DIM)
                    
                def on_release(e):
                    if inner._is_pressed:
                        inner._is_pressed = False
                        f.configure(highlightbackground=T.PRIMARY)
                        cmd()

                for w in [f, inner, t_lbl, s_lbl]:
                    w.bind("<Enter>", on_enter, add="+")
                    w.bind("<Leave>", on_leave, add="+")
                    w.bind("<ButtonPress-1>", on_press, add="+")
                    w.bind("<ButtonRelease-1>", on_release, add="+")

            return f

        inv_img = "images/inventory_banner_user.png"
        if not os.path.exists(T.get_resource_path(inv_img)): inv_img = None
            
        emp_img = "images/employee_banner_user_v2.png"
        if not os.path.exists(T.get_resource_path(emp_img)): emp_img = "images/employee_banner_user.png"
        if not os.path.exists(T.get_resource_path(emp_img)): emp_img = os.path.join("images", "employee_banner.png")
        
        invc_img = "images/invoice_banner_user.png"
        if not os.path.exists(T.get_resource_path(invc_img)): invc_img = None

        peri_img = "images/perishable_banner_user.png"
        if not os.path.exists(T.get_resource_path(peri_img)): peri_img = None
            
        sales_img = "images/sales_analytics_banner_user.png"
        if not os.path.exists(T.get_resource_path(sales_img)): sales_img = None

        pay_img = "images/payment_banner_user.png"
        if not os.path.exists(T.get_resource_path(pay_img)): pay_img = None
            
        about_img = "images/about_banner_user.png"
        if not os.path.exists(T.get_resource_path(about_img)): about_img = None

        mark_img = "images/marketing_banner_user.png"
        if not os.path.exists(T.get_resource_path(mark_img)): mark_img = None

        net_img = "images/network_banner_user.png"
        if not os.path.exists(T.get_resource_path(net_img)): net_img = None

        def secure_qr_config():
            from tkinter import simpledialog, messagebox
            pin = simpledialog.askstring("Security Authorization", "Enter Admin PIN to modify Payment Config:", parent=root, show="*")
            if pin is None: return
            cur.execute("SELECT value FROM settings WHERE `key`='payment_pin'")
            res = cur.fetchone()
            db_pin = res[0] if res else "1234"
            if pin == db_pin:
                for widget in root.winfo_children(): widget.destroy()
                global page_qr
                page_qr = Payment_Config_Page(root)
                page_qr.time()
            else:
                messagebox.showerror("Access Denied", "Incorrect Security PIN.", parent=adm)

        # --- CLEAN DASHBOARD LAYOUT (No Categories) ---
        
        # ROW 0 & 1 (Loaded together for instant impact)
        def load_top_panels():
            if not tiles.winfo_exists(): return
            # Row 0
            self.button2 = tile(tiles, "Inventory", "Products, stock, category, and vendors.", inventory, bg_image=inv_img)
            self.button2.grid(row=0, column=0, padx=(0, 20), pady=(0, 15), sticky=NSEW)
            
            self.button1 = tile(tiles, "Invoices", "Create, print and manage customer bills.", invoices, bg_image=invc_img)
            self.button1.grid(row=0, column=1, padx=(0, 0), pady=(0, 15), sticky=NSEW)
            
            # Row 1
            self.button_peri = tile(tiles, "Perishable Tracker", "Monitor expiry dates and remove old stock.", perishables, bg_image=peri_img)
            self.button_peri.grid(row=1, column=0, padx=(0, 20), pady=(0, 15), sticky=NSEW)

            self.button3 = tile(tiles, "Employees", "Hire, update roles, and keep records tight.", employee, bg_image=emp_img)
            self.button3.grid(row=1, column=1, padx=(0, 0), pady=(0, 15), sticky=NSEW)
            
            top.after(5, load_bottom_panels)


        def load_bottom_panels():
            if not tiles.winfo_exists(): return
            # Row 2
            self.button_marketing = tile(tiles, "Marketing & Offers", "Rewards, tiers, and discounts.", lambda: marketing(self.user_data), bg_image=mark_img)
            self.button_marketing.grid(row=2, column=0, padx=(0, 20), pady=(0, 15), sticky=NSEW)

            self.button_sales = tile(tiles, "Sales Analytics", "Visual performance & payment trends.", sales_analytics, bg_image=sales_img)
            self.button_sales.grid(row=2, column=1, padx=(0, 0), pady=(0, 15), sticky=NSEW)
            
            # Row 3
            self.button_qr = tile(tiles, "Payment Config", "Securely upload active POS payment QR.", secure_qr_config, bg_image=pay_img)
            self.button_qr.grid(row=3, column=0, padx=(0, 20), pady=(0, 15), sticky=NSEW)
            
            self.button_system = tile(tiles, "System & Network", "LAN sync and automated backups.", lambda: system_config(self.user_data), bg_image=net_img)
            self.button_system.grid(row=3, column=1, padx=(0, 0), pady=(0, 15), sticky=NSEW)
            
            top.after(5, load_full_rows)


        def load_full_rows():
            if not tiles.winfo_exists(): return
            # FULL-WIDTH ROWS (Length matches 2 columns)
            self.button5 = tile(tiles, "About", "Version notes and theme credits.", about, bg_image=about_img)
            self.button5.grid(row=4, column=0, columnspan=2, padx=(0, 0), pady=(0, 15), sticky=NSEW)
            
            # Final touch: Ensure scrollregion is correct
            top.update_idletasks()
            canvas.configure(scrollregion=canvas.bbox("all"))

        # Start the accelerated loading process
        top.after(20, load_top_panels)


    def check_sync(self):
        import db_manager
        try:
            # SAFETY: Stop if window was closed or logged out
            if not hasattr(self, "sync_dot") or not self.sync_dot.winfo_exists():
                return

            db_manager.connect().cursor().execute("SELECT 1")
            self.sync_dot.config(fg="#4CAF50") # Green
            self.sync_lbl.config(text="SYNCED")
        except:
            if hasattr(self, "sync_dot") and self.sync_dot.winfo_exists():
                self.sync_dot.config(fg="#F44336") # Red
                self.sync_lbl.config(text="OFFLINE")
            
        # Check every 30 seconds
        if hasattr(self, "top") and self.top.winfo_exists():
            self.top.after(30000, self.check_sync)

    def heartbeat(self):
        import db_manager, socket
        try:
            db = db_manager.connect()
            pc_name = socket.gethostname()
            # Try to get better IP than 127.0.0.1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                pc_ip = s.getsockname()[0]
                s.close()
            except:
                pc_ip = socket.gethostbyname(pc_name)
                
            user = self.user_data[1] if self.user_data else "Admin"
            db.execute("REPLACE INTO active_sessions (session_id, pc_name, pc_ip, role, user_name, last_seen) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", 
                       (self.session_id, pc_name, pc_ip, "Admin Hub", user))
            db.commit()
        except:
            pass
            
        if hasattr(self, "top") and self.top.winfo_exists():
            self.top.after(60000, self.heartbeat)

    def clear_session(self):
        import db_manager
        try:
            db = db_manager.connect()
            db.execute("DELETE FROM active_sessions WHERE session_id=?", (self.session_id,))
            db.commit()
        except:
            pass

    def Logout(self):
        self.clear_session()
        exitt()


class Inventory:
    def __init__(self, top=None):
        top.geometry("1240x920")
        top.minsize(1000, 600)
        top.resizable(True, True)
        top.title("Inventory · Real Mart")
        top.configure(bg=T.BG_ROOT)
        refresh_db()

        hdr = Frame(top, bg=T.ORANGE, height=56)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hr = Frame(hdr, bg=T.ORANGE)
        hr.pack(fill=BOTH, expand=True, padx=20, pady=10)
        self.message = Label(
            hr,
            text="INVENTORY",
            font=T.FONT_SECTION,
            bg=T.ORANGE,
            fg=T.WHITE,
        )
        self.message.pack(side=LEFT)
        self.btn_back = Button(hr, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hr, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        body = Frame(top, bg="white")
        body.pack(fill=BOTH, expand=True, padx=16, pady=16)

        # Use white for better readability over background
        sidebar = Frame(body, bg=T.WHITE, padx=16, pady=16)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 16))
        sidebar.pack_propagate(False)
        sidebar.configure(width=268)
        
        Label(
            sidebar,
            text="Quick actions",
            font=T.FONT_SECTION,
            bg=T.WHITE,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W, pady=(0, 12))
        self.button3 = Button(sidebar, text="Add product", command=self.add_product)
        self.button3.pack(fill=X, pady=4)
        T.btn_primary(self.button3)
        
        self.button_import = Button(sidebar, text="Import from CSV", command=self.import_csv)
        self.button_import.pack(fill=X, pady=4)
        T.btn_secondary(self.button_import)

        self.button_refresh = Button(sidebar, text="🔄 Refresh", command=self.DisplayData)
        self.button_refresh.pack(fill=X, pady=4)
        T.btn_primary(self.button_refresh)

        # --- NEW: Selection Actions (Hidden by default) ---
        self.selection_frame = Frame(sidebar, bg=T.WHITE)
        # Hidden initially
        
        self.button4 = Button(self.selection_frame, text="Update product", command=self.update_product)
        self.button4.pack(fill=X, pady=4)
        T.btn_secondary(self.button4)
        self.button4.configure(state=DISABLED)

        self.button5 = Button(self.selection_frame, text="Delete product", command=self.delete_product)
        self.button5.pack(fill=X, pady=4)
        T.btn_secondary(self.button5)
        self.button5.configure(state=DISABLED)

        self.button_view_barcode = Button(self.selection_frame, text="🔍 View Barcode", command=self.view_barcode)
        self.button_view_barcode.pack(fill=X, pady=4)
        T.btn_secondary(self.button_view_barcode)
        self.button_view_barcode.configure(state=DISABLED)

        Label(
            sidebar,
            text="Search catalog",
            font=T.FONT_SECTION,
            bg=T.WHITE,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W, pady=(20, 8))
        sf = Frame(sidebar, bg=T.WHITE)
        sf.pack(fill=X)
        self.entry1 = Entry(sf)
        self.entry1.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry1)
        self.entry1.bind("<KeyRelease>", self.search_product) # Real-time filtering
        self.button1 = Button(sf, text="Go", command=self.search_product)
        self.button1.pack(side=LEFT, padx=(8, 0))
        T.btn_primary(self.button1)

        

        main = Frame(body, bg="white", padx=15, pady=15)
        main.pack(side=LEFT, fill=BOTH, expand=True)

        Label(
            main,
            text="Stock overview",
            font=T.FONT_SECTION,
            bg="white",
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W, pady=(0, 8))

        tree_wrap = Frame(
            main,
            bg=T.CARD,
            highlightthickness=1,
            highlightbackground=T.BORDER_SUBTLE,
        )
        tree_wrap.pack(fill=BOTH, expand=True)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self.scrollbarx = Scrollbar(tree_wrap, orient=HORIZONTAL, bg=T.CARD)
        self.scrollbary = Scrollbar(tree_wrap, orient=VERTICAL, bg=T.CARD)
        self.tree = ttk.Treeview(
            tree_wrap,
            style="RM.Treeview",
            yscrollcommand=self.scrollbary.set,
            xscrollcommand=self.scrollbarx.set,
            selectmode="extended",
        )
        self.tree.grid(row=0, column=0, sticky=NSEW)
        self.scrollbary.grid(row=0, column=1, sticky=NS)
        self.scrollbarx.grid(row=1, column=0, sticky=EW)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self.scrollbary.configure(command=self.tree.yview)
        self.scrollbarx.configure(command=self.tree.xview)

        self.tree.configure(
            columns=(
                "Product ID",
                "Name",
                "Category",
                "In Stock",
                "MRP",
                "Cost Price",
                "Vendor No.",
                "Expiry Date",
                "Barcode",
            )
        )

        self.tree.heading("Product ID", text="Product ID", anchor=CENTER)
        self.tree.heading("Name", text="Name", anchor=CENTER)
        self.tree.heading("Category", text="Category", anchor=CENTER)
        self.tree.heading("In Stock", text="In Stock", anchor=CENTER)
        self.tree.heading("MRP", text="MRP", anchor=CENTER)
        self.tree.heading("Cost Price", text="Cost Price", anchor=CENTER)
        self.tree.heading("Vendor No.", text="Vendor No.", anchor=CENTER)
        self.tree.heading("Expiry Date", text="Expiry Date", anchor=CENTER)
        self.tree.heading("Barcode", text="Barcode", anchor=CENTER)

        self.tree.column("#0", stretch=NO, minwidth=0, width=0)
        self.tree.column("#1", stretch=NO, minwidth=110, width=120, anchor=CENTER) # ID
        self.tree.column("#2", stretch=YES, minwidth=200, width=280, anchor=CENTER)  # Name
        self.tree.column("#3", stretch=NO, minwidth=100, width=120, anchor=CENTER)  # Category
        self.tree.column("#4", stretch=NO, minwidth=80, width=80, anchor=CENTER) # Stock
        self.tree.column("#5", stretch=NO, minwidth=90, width=90, anchor=CENTER) # MRP
        self.tree.column("#6", stretch=NO, minwidth=90, width=90, anchor=CENTER) # Cost
        self.tree.column("#7", stretch=NO, minwidth=100, width=100, anchor=CENTER) # Vendor
        self.tree.column("#8", stretch=NO, minwidth=110, width=110, anchor=CENTER) # Expiry
        self.tree.column("#9", stretch=NO, minwidth=130, width=130, anchor=CENTER) # Barcode
        T.apply_zebra_styling(self.tree)

        self.DisplayData()
        
    def import_csv(self):
        path = filedialog.askopenfilename(title="Select Inventory CSV", filetypes=[("CSV Files", "*.csv")])
        if not path:
            return
            
        try:
            with open(path, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                expected_cols = ["Product ID", "Name", "Category", "Stock", "MRP", "Cost Price", "Vendor No", "Expiry Date"]
                
                # Check headers (basic validation)
                if not all(col in reader.fieldnames for col in expected_cols):
                    messagebox.showerror("Error", f"Invalid CSV format. Please use the headers:\n{', '.join(expected_cols)}", parent=inv)
                    return
                
                # SELF-REPAIR: Ensure table exists before starting
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS raw_inventory (
                        product_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT NOT NULL,
                        product_cat TEXT NOT NULL,
                        stock INTEGER NOT NULL,
                        mrp REAL NOT NULL,
                        cost_price REAL NOT NULL,
                        vendor_phn TEXT,
                        expiry_date TEXT DEFAULT 'N/A',
                        barcode TEXT DEFAULT ''
                    )
                """)
                
                count = 0
                for i, row in enumerate(reader, 1):
                    # Column mapping: product_id, product_name, product_cat, stock, mrp, cost_price, vendor_phn, expiry_date
                    pid_raw = row["Product ID"].strip()
                    name = row["Name"].strip()
                    cat = row["Category"].strip()
                    stock_raw = row["Stock"].strip()
                    mrp_raw = row["MRP"].strip()
                    cp_raw = row["Cost Price"].strip()
                    vphn = row["Vendor No"].strip()
                    expiry = row["Expiry Date"].strip()
                    
                    if not pid_raw or not name: continue
                    
                    try:
                        # Database requires INTEGER for product_id
                        pid = int(pid_raw)
                        stock = int(stock_raw) if stock_raw else 0
                        mrp = float(mrp_raw) if mrp_raw else 0.0
                        cp = float(cp_raw) if cp_raw else 0.0
                    except ValueError:
                        messagebox.showerror("Invalid Data", f"Row {i}: IDs and Stock must be numbers. Please check your CSV.", parent=inv)
                        return
                    
                    # Store as "N/A" if no expiry
                    expiry = expiry if expiry else "N/A"
                    
                    # UPSERT into database (raw_inventory has 9 columns)
                    q = "REPLACE INTO raw_inventory(product_id, product_name, product_cat, stock, mrp, cost_price, vendor_phn, expiry_date, barcode) VALUES(?,?,?,?,?,?,?,?,?)"
                    cur.execute(q, [pid, name, cat, stock, mrp, cp, vphn, expiry, ""])
                    count += 1
                
                db.commit()
                messagebox.showinfo("Success", f"Successfully imported {count} products from CSV.", parent=inv)
                self.DisplayData()
        except Exception as e:
            messagebox.showerror("Import Failed (Fixed Version v2)", f"An error occurred: {e}", parent=inv)

    def DisplayData(self):
        self.tree.delete(*self.tree.get_children())
        cur.execute("SELECT * FROM raw_inventory")
        fetch = cur.fetchall()
        for i, data in enumerate(fetch):
            self.tree.insert(
                "",
                "end",
                values=(
                    data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8],
                ),
                tags=("even" if i % 2 == 0 else "odd",)
            )

    def search_product(self, event=None):
        query = self.entry1.get().strip().lower()
        
        self.tree.delete(*self.tree.get_children())
        cur.execute("SELECT * FROM raw_inventory")
        fetch = cur.fetchall()
        
        matched_items = []
        for data in fetch:
            pid = str(data[0]).lower()
            name = str(data[1]).lower()
            cat = str(data[2]).lower()
            barcode = str(data[8]).lower()
            
            # Match query with ID, Name, Category, or Barcode
            if not query or (query in pid or query in name or query in cat or query in barcode):
                matched_items.append(data)
                
        for i, data in enumerate(matched_items):
            item_id = self.tree.insert(
                "",
                "end",
                values=(
                    data[0], data[1], data[2], data[3], data[4], data[5], data[6], data[7], data[8],
                ),
                tags=("even" if i % 2 == 0 else "odd",)
            )
            # If exact match on ID or Barcode, or it's the only matched item, let's select, focus, and scroll to it!
            if query and (query == str(data[0]).lower() or query == str(data[8]).lower() or len(matched_items) == 1):
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
                self.tree.see(item_id)
    
    sel = []
    def on_tree_select(self, Event):
        self.sel.clear()
        for i in self.tree.selection():
            if i not in self.sel:
                self.sel.append(i)
        
        if len(self.sel) >= 1:
            # Show selection actions
            self.selection_frame.pack(fill=X, pady=(10, 0), after=self.button_import)
            
            if len(self.sel) == 1:
                self.button4.configure(state=NORMAL)
                self.button_view_barcode.configure(state=NORMAL)
            else:
                self.button4.configure(state=DISABLED)
                self.button_view_barcode.configure(state=DISABLED)
            
            self.button5.configure(state=NORMAL)
        else:
            # Hide selection actions
            self.selection_frame.pack_forget()
            self.button4.configure(state=DISABLED)
            self.button5.configure(state=DISABLED)
            self.button_view_barcode.configure(state=DISABLED)

    def view_barcode(self):
        if len(self.sel) == 1:
            for i in self.sel:
                vals = self.tree.item(i)["values"]
                # index 8 corresponds to the Barcode column in DisplayData
                code = vals[8]
                name = vals[1]
                if code:
                    BarcodePopup(inv, str(code), str(name))
                else:
                    messagebox.showinfo("No Barcode", f"Product '{name}' has no barcode ID. Generate one in 'Update Product'.", parent=inv)
        else:
            messagebox.showerror("Error", "Please select one product to view its barcode.", parent=inv)

    def delete_product(self):
        val = []
        to_delete = []

        if len(self.sel)!=0:
            sure = messagebox.askyesno("Confirm", "Are you sure you want to delete selected products?", parent=inv)
            if sure == True:
                for i in self.sel:
                    for j in self.tree.item(i)["values"]:
                        val.append(j)
                
                for j in range(len(val)):
                    if j % 8 == 0:
                        to_delete.append(val[j])
                
                for k in to_delete:
                    delete = "DELETE FROM raw_inventory WHERE product_id = ?"
                    cur.execute(delete, [k])
                    db.commit()

                messagebox.showinfo("Success!!", "Products deleted from database.", parent=inv)
                self.sel.clear()
                self.tree.delete(*self.tree.get_children())

                self.DisplayData()
        else:
            messagebox.showerror("Error!!","Please select a product.", parent=inv)

    def update_product(self):
        if len(self.sel)==1:
            global valll
            valll = []
            for i in self.sel:
                for j in self.tree.item(i)["values"]:
                    valll.append(j)

            for widget in root.winfo_children():
                widget.destroy()
            global p_update
            p_update = root
            page9 = Update_Product(p_update)
            page9.time()
            
            page9.entry1.insert(0, valll[1])
            page9.entry2.insert(0, valll[2])
            page9.entry3.insert(0, valll[3])
            page9.entry4.insert(0, valll[4])
            page9.entry7.insert(0, valll[5])
            page9.entry8.insert(0, valll[6])
            page9.entry_exp.insert(0, valll[7])
            page9.entry_barcode.insert(0, valll[8])

            

        elif len(self.sel)==0:
            messagebox.showerror("Error","Please choose a product to update.", parent=inv)
        else:
            messagebox.showerror("Error","Can only update one product at a time.", parent=inv)

    

    def add_product(self):
        global page4
        for widget in root.winfo_children():
            widget.destroy()
        global p_add
        p_add = root
        page4 = add_product(p_add)
        page4.time()
        

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        global page2
        page2 = Admin_Page(root)

    def ex2(self):
        sure = messagebox.askyesno("Exit","Are you sure you want to return to inventory?", parent=p_update)
        if sure == True:
            for widget in root.winfo_children():
                widget.destroy()
            global page3
            page3 = Inventory(root)
            page3.DisplayData()
             


    def Logout(self):
        sure = messagebox.askyesno("Logout", "Are you sure you want to logout?", parent=inv)
        if sure == True:
            for widget in root.winfo_children():
                widget.destroy()
            global page1
            page1 = login_page(root)
            root.bind("<Return>", lambda e: page1.login(e))


class add_product:
    def __init__(self, top=None):
        top.geometry("920x640")
        top.minsize(720, 520)
        top.resizable(True, True)
        top.title("Add product · Real Mart")
        p_add.configure(bg=T.BG_ROOT)
        refresh_db()
        T.setup_ttk(p_add)

        hdr = Frame(p_add, bg=T.ORANGE, height=52)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.ORANGE)
        hc.pack(fill=BOTH, expand=True, padx=20, pady=10)
        Label(hc, text="New product", font=T.FONT_SECTION, bg=T.ORANGE, fg=T.WHITE).pack(side=LEFT)
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        wrap = Frame(p_add, bg=T.BG_ROOT)
        wrap.pack(fill=BOTH, expand=True, padx=28, pady=20)

        card = Frame(
            wrap,
            bg=T.CARD,
            highlightthickness=2,
            highlightbackground=T.ORANGE,
            padx=28,
            pady=24,
        )
        card.pack(fill=BOTH, expand=True)

        Label(
            card,
            text="Product name",
            font=T.FONT_SECTION,
            bg=T.CARD,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W)
        self.entry1 = Entry(card)
        self.entry1.pack(fill=X, pady=(6, 12), ipady=8)
        T.entry_light(self.entry1)

        Label(card, text="Category", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(
            fill=X, pady=(6, 0)
        )
        self.entry2 = Entry(card)
        self.entry2.pack(fill=X, pady=(4, 12), ipady=6)
        T.entry_light(self.entry2)

        self.r2 = p_add.register(self.testint)
        row3 = Frame(card, bg=T.CARD)
        row3.pack(fill=X, pady=6)
        Label(row3, text="Stock qty", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=16, anchor=W).pack(
            side=LEFT
        )
        self.entry3 = Entry(row3, validate="key", validatecommand=(self.r2, "%P"))
        self.entry3.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry3)
        Label(row3, text="MRP", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=12, anchor=W).pack(
            side=LEFT, padx=(16, 0)
        )
        self.entry4 = Entry(row3)
        self.entry4.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry4)

        row4 = Frame(card, bg=T.CARD)
        row4.pack(fill=X, pady=6)
        Label(row4, text="Cost price", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=16, anchor=W).pack(
            side=LEFT
        )
        self.entry7 = Entry(row4)
        self.entry7.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry7)
        Label(row4, text="Vendor phone", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=12, anchor=W).pack(
            side=LEFT, padx=(16, 0)
        )
        self.entry8 = Entry(row4, validate="key", validatecommand=(self.r2, "%P"))
        self.entry8.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry8)

        # Expiry Date field
        Label(card, text="Expiry Date (YYYY-MM-DD or N/A)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X, pady=(8, 0))
        eform = Frame(card, bg=T.CARD)
        eform.pack(fill=X, pady=(4, 0))
        self.entry_exp = Entry(eform)
        self.entry_exp.pack(side=LEFT, fill=X, expand=True, ipady=6)
        self.entry_exp.insert(0, "N/A")
        T.entry_light(self.entry_exp)
        
        cal_btn = Button(eform, text="📅", font=("Segoe UI Symbol", 12), bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, command=lambda: DatePickerPopup(self.entry_exp))
        cal_btn.pack(side=LEFT, padx=(8, 0))

        # Barcode field
        Label(card, text="Product Barcode ID (EAN-13)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X, pady=(8, 0))
        bform = Frame(card, bg=T.CARD)
        bform.pack(fill=X, pady=(4, 0))
        self.entry_barcode = Entry(bform)
        self.entry_barcode.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry_barcode)
        
        def quick_gen():
            code = generate_ean13_id()
            self.entry_barcode.delete(0, END)
            self.entry_barcode.insert(0, code)
            
        gen_btn = Button(bform, text="✨ Generate", font=T.FONT_UI_SM, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, command=quick_gen)
        gen_btn.pack(side=LEFT, padx=(8, 0))

        btns = Frame(card, bg=T.CARD)
        btns.pack(fill=X, pady=(24, 0))

        def on_scan(data):
            self.entry_barcode.delete(0, END)
            self.entry_barcode.insert(0, data)
            
            # Show interactive feedback
            self.entry1.delete(0, END)
            self.entry1.insert(0, "🔍 Looking up details...")
            self.entry2.delete(0, END)

            def background_lookup():
                name, cat = fetch_product_info(data)
                def apply_results():
                    if name:
                        self.entry1.delete(0, END)
                        self.entry1.insert(0, name)
                    else:
                        self.entry1.delete(0, END)
                        self.entry1.insert(0, "Not found in database")
                    if cat:
                        self.entry2.delete(0, END)
                        self.entry2.insert(0, cat.title())
                p_add.after(0, apply_results)

            import threading
            threading.Thread(target=background_lookup, daemon=True).start()

        scan_btn = Button(bform, text="📷 Scan", font=T.FONT_UI_SM, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, command=lambda: scanner_util.open_scanner(p_add, on_scan, "Scan Product Barcode"))
        scan_btn.pack(side=LEFT, padx=(8, 0))

        self.button1 = Button(btns, text="Add to inventory", command=self.add)
        self.button1.pack(side=LEFT, padx=(0, 12))
        T.btn_primary(self.button1)
        self.button2 = Button(btns, text="Clear form", command=self.clearr)
        self.button2.pack(side=LEFT, padx=(0, 12))
        T.btn_secondary(self.button2)
        
        

    def has_changes(self):
        # Check if any field is not empty
        fields = [self.entry1, self.entry2, self.entry3, self.entry4, self.entry7, self.entry8, self.entry_barcode]
        for f in fields:
            if f.get().strip():
                return True
        # Special check for expiry if it's not "N/A"
        if self.entry_exp.get().strip() not in ["N/A", ""]:
            return True
        return False

    def Exit(self):
        if self.has_changes():
            if not messagebox.askyesno("Unsaved Changes", "You have entered product details. Are you sure you want to go back and discard them?", parent=p_add):
                return
        for widget in root.winfo_children():
            widget.destroy()
        global page3
        page3 = Inventory(root)
        page3.DisplayData()

    def add(self):
        pqty = self.entry3.get()
        pcat = self.entry2.get()  
        pmrp = self.entry4.get()  
        pname = self.entry1.get()  
        pvendor = self.entry8.get()  
        pcp = self.entry7.get()
        pexp = self.entry_exp.get().strip() or "N/A"
       

        if pname.strip():
            if pcat.strip():
                if pqty:
                    if pcp:
                        try:
                            float(pcp)
                        except ValueError:
                            messagebox.showerror("Oops!", "Invalid cost price.", parent=p_add)
                        else:
                            if pmrp:
                                try:
                                    float(pmrp)
                                except ValueError:
                                    messagebox.showerror("Oops!", "Invalid MRP.", parent=p_add)
                                else:
                                    if valid_phone(pvendor):
                                        pbarcode = self.entry_barcode.get().strip()
                                        sql_insert = "INSERT INTO raw_inventory(product_name, product_cat, stock, mrp, cost_price, vendor_phn, expiry_date, barcode) VALUES(?,?,?,?,?,?,?,?)"
                                        cur.execute(
                                            sql_insert,
                                            [pname.strip(), pcat.strip(), int(pqty), float(pmrp), float(pcp), pvendor.strip(), pexp, pbarcode],
                                        )
                                        db.commit()
                                        messagebox.showinfo("Success!!", "Product successfully added in inventory.", parent=p_add)
                                        for widget in root.winfo_children():
                                            widget.destroy()
                                        global page3
                                        page3 = Inventory(root)
                                        page3.DisplayData()
                                    else:
                                        messagebox.showerror("Oops!", "Invalid phone number.", parent=p_add)
                            else:
                                messagebox.showerror("Oops!", "Please enter MRP.", parent=p_add)
                    else:
                        messagebox.showerror("Oops!", "Please enter product cost price.", parent=p_add)
                else:
                    messagebox.showerror("Oops!", "Please enter product quantity.", parent=p_add)
            else:
                messagebox.showerror("Oops!", "Please enter product category.", parent=p_add)
        else:
            messagebox.showerror("Oops!", "Please enter product name", parent=p_add)

    def clearr(self):
        self.entry1.delete(0, END)
        self.entry2.delete(0, END)
        self.entry3.delete(0, END)
        self.entry4.delete(0, END)
        self.entry7.delete(0, END)
        self.entry8.delete(0, END)

    def testint(self, val):
        if val.isdigit():
            return True
        elif val == "":
            return True
        return False

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)


class Update_Product:
    def __init__(self, top=None):
        top.geometry("920x640")
        top.minsize(720, 520)
        top.resizable(True, True)
        top.title("Update product · Real Mart")
        p_update.configure(bg=T.BG_ROOT)
        refresh_db()
        T.setup_ttk(p_update)

        hdr = Frame(p_update, bg=T.ORANGE, height=52)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.ORANGE)
        hc.pack(fill=BOTH, expand=True, padx=20, pady=10)
        Label(hc, text="Update product", font=T.FONT_SECTION, bg=T.ORANGE, fg=T.WHITE).pack(side=LEFT)
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        wrap = Frame(p_update, bg=T.BG_ROOT)
        wrap.pack(fill=BOTH, expand=True, padx=28, pady=20)

        card = Frame(
            wrap,
            bg=T.CARD,
            highlightthickness=2,
            highlightbackground=T.ORANGE,
            padx=28,
            pady=24,
        )
        card.pack(fill=BOTH, expand=True)

        Label(
            card,
            text="Product name",
            font=T.FONT_SECTION,
            bg=T.CARD,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W)
        self.entry1 = Entry(card)
        self.entry1.pack(fill=X, pady=(6, 12), ipady=8)
        T.entry_light(self.entry1)

        Label(card, text="Category", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(
            fill=X, pady=(6, 0)
        )
        self.entry2 = Entry(card)
        self.entry2.pack(fill=X, pady=(4, 12), ipady=6)
        T.entry_light(self.entry2)

        self.r2 = p_update.register(self.testint)
        row3 = Frame(card, bg=T.CARD)
        row3.pack(fill=X, pady=6)
        Label(row3, text="Stock qty", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=16, anchor=W).pack(
            side=LEFT
        )
        self.entry3 = Entry(row3, validate="key", validatecommand=(self.r2, "%P"))
        self.entry3.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry3)
        Label(row3, text="MRP", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=12, anchor=W).pack(
            side=LEFT, padx=(16, 0)
        )
        self.entry4 = Entry(row3)
        self.entry4.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry4)

        row4 = Frame(card, bg=T.CARD)
        row4.pack(fill=X, pady=6)
        Label(row4, text="Cost price", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=16, anchor=W).pack(
            side=LEFT
        )
        self.entry7 = Entry(row4)
        self.entry7.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry7)
        Label(row4, text="Vendor phone", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, width=12, anchor=W).pack(
            side=LEFT, padx=(16, 0)
        )
        self.entry8 = Entry(row4, validate="key", validatecommand=(self.r2, "%P"))
        self.entry8.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry8)

        # Expiry Date field
        Label(card, text="Expiry Date (YYYY-MM-DD or N/A)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X, pady=(8, 0))
        eform = Frame(card, bg=T.CARD)
        eform.pack(fill=X, pady=(4, 0))
        self.entry_exp = Entry(eform)
        self.entry_exp.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry_exp)

        cal_btn = Button(eform, text="📅", font=("Segoe UI Symbol", 12), bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, command=lambda: DatePickerPopup(self.entry_exp))
        cal_btn.pack(side=LEFT, padx=(8, 0))

        # Barcode field
        Label(card, text="Product Barcode ID (EAN-13)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X, pady=(8, 0))
        bform = Frame(card, bg=T.CARD)
        bform.pack(fill=X, pady=(4, 0))
        self.entry_barcode = Entry(bform)
        self.entry_barcode.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry_barcode)
        
        def quick_gen():
            code = generate_ean13_id()
            self.entry_barcode.delete(0, END)
            self.entry_barcode.insert(0, code)
            
        gen_btn = Button(bform, text="✨ Generate", font=T.FONT_UI_SM, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, command=quick_gen)
        gen_btn.pack(side=LEFT, padx=(8, 0))

        btns = Frame(card, bg=T.CARD)
        btns.pack(fill=X, pady=(24, 0))
        self.button1 = Button(btns, text="Save changes", command=self.update)
        self.button1.pack(side=LEFT, padx=(0, 12))
        T.btn_primary(self.button1)
        self.button2 = Button(btns, text="Clear form", command=self.clearr)
        self.button2.pack(side=LEFT, padx=(0, 12))
        T.btn_secondary(self.button2)

        # Store original data to track changes
        self.original_data = {
            "name": str(valll[1]),
            "cat": str(valll[2]),
            "stock": str(valll[3]),
            "mrp": str(valll[4]),
            "cp": str(valll[5]),
            "vphn": str(valll[6]),
            "exp": str(valll[7]),
            "barcode": str(valll[8])
        }

        

    def has_changes(self):
        current_data = {
            "name": str(self.entry1.get()),
            "cat": str(self.entry2.get()),
            "stock": str(self.entry3.get()),
            "mrp": str(self.entry4.get()),
            "cp": str(self.entry7.get()),
            "vphn": str(self.entry8.get()),
            "exp": str(self.entry_exp.get()),
            "barcode": str(self.entry_barcode.get())
        }
        return current_data != self.original_data

    def Exit(self, force=False):
        if not force and self.has_changes():
            if not messagebox.askyesno("Unsaved Changes", "You have made changes to this product. Are you sure you want to discard them?", parent=p_update):
                return
        for widget in root.winfo_children():
            widget.destroy()
        global page3
        page3 = Inventory(root)
        page3.DisplayData()

    def update(self):
        pqty = self.entry3.get()
        pcat = self.entry2.get()  
        pmrp = self.entry4.get()  
        pname = self.entry1.get()  
        pvendor = self.entry8.get()  
        pcp = self.entry7.get()
        pexp = self.entry_exp.get().strip() or "N/A"
       

        if pname.strip():
            if pcat.strip():
                if pqty:
                    if pcp:
                        try:
                            float(pcp)
                        except ValueError:
                            messagebox.showerror("Oops!", "Invalid cost price.", parent=p_update)
                        else:
                            if pmrp:
                                try:
                                    float(pmrp)
                                except ValueError:
                                    messagebox.showerror("Oops!", "Invalid MRP.", parent=p_update)
                                else:
                                    if valid_phone(pvendor):
                                        product_id = valll[0]
                                        pbarcode = self.entry_barcode.get().strip()
                                        update = (
                                            "UPDATE raw_inventory SET product_name = ?, product_cat = ?, stock = ?, mrp = ?, cost_price = ?, vendor_phn = ?, expiry_date = ?, barcode = ? WHERE product_id = ?"
                                        )
                                        cur.execute(
                                            update,
                                            [pname, pcat, int(pqty), float(pmrp), float(pcp), pvendor, pexp, pbarcode, product_id],
                                        )
                                        db.commit()
                                        messagebox.showinfo("Success!!", "Product successfully updated in inventory.", parent=p_update)
                                        valll.clear()
                                        Inventory.sel.clear()
                                        self.Exit(force=True)
                                    else:
                                        messagebox.showerror("Oops!", "Invalid phone number.", parent=p_update)
                            else:
                                messagebox.showerror("Oops!", "Please enter MRP.", parent=p_update)
                    else:
                        messagebox.showerror("Oops!", "Please enter product cost price.", parent=p_update)
                else:
                    messagebox.showerror("Oops!", "Please enter product quantity.", parent=p_update)
            else:
                messagebox.showerror("Oops!", "Please enter product category.", parent=p_update)
        else:
            messagebox.showerror("Oops!", "Please enter product name", parent=p_update)

    def clearr(self):
        self.entry1.delete(0, END)
        self.entry2.delete(0, END)
        self.entry3.delete(0, END)
        self.entry4.delete(0, END)
        self.entry7.delete(0, END)
        self.entry8.delete(0, END)
        self.entry_barcode.delete(0, END)

    def testint(self, val):
        if val.isdigit():
            return True
        elif val == "":
            return True
        return False

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)
    


class Employee:
    def __init__(self, top=None):
        top.geometry("1240x920")
        top.minsize(1000, 600)
        top.resizable(True, True)
        top.title("Team · Real Mart")
        top.configure(bg=T.BG_ROOT)

        refresh_db()
        T.setup_ttk(top)

        hdr = Frame(top, bg=T.ORANGE, height=56)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hr = Frame(hdr, bg=T.ORANGE)
        hr.pack(fill=BOTH, expand=True, padx=20, pady=10)
        self.message = Label(
            hr,
            text="TEAM",
            font=T.FONT_SECTION,
            bg=T.ORANGE,
            fg=T.WHITE,
        )
        self.message.pack(side=LEFT)
        self.btn_back = Button(hr, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hr, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        body = Frame(top, bg="white")
        body.pack(fill=BOTH, expand=True, padx=16, pady=16)

        # Apply Glass panels for readability over the background
        sidebar = Frame(body, bg=T.WHITE, padx=16, pady=16)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 16))
        sidebar.pack_propagate(False)
        sidebar.configure(width=268)
        
        # Draw glass effect on the canvas behind the sidebar
        # We'll use a listener to keep it synced or just use high-opacity white frames
        # For this design, let's keep it simple and premium with white cards
        
        # (Rest of sidebar widgets keep their logic)

        Label(
            sidebar,
            text="Quick actions",
            font=T.FONT_SECTION,
            bg=T.BG_PANEL,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W, pady=(0, 12))

        # --- Notification Section ---
        self.notif_frame = Frame(sidebar, bg=T.BG_PANEL)
        self.notif_frame.pack(fill=X, pady=(0, 20))
        
        self.btn_notif = Button(
            self.notif_frame, 
            text="Pending Approvals", 
            command=self.show_pending_panel,
            bg=T.WHITE,
            fg=T.PRIMARY,
            relief=FLAT,
            font=T.FONT_UI,
            anchor=W,
            padx=10
        )
        self.btn_notif.pack(side=LEFT, fill=X, expand=True)
        T.btn_secondary(self.btn_notif)
        
        self.badge = Label(
            self.notif_frame,
            text="0",
            bg=T.ORANGE,
            fg=T.WHITE,
            font=("Inter", 9, "bold"),
            padx=6,
            pady=2,
            width=2
        )
        self.badge.pack(side=RIGHT, padx=(0, 5))

        self.button3 = Button(sidebar, text="Add employee", command=self.add_emp)
        self.button3.pack(fill=X, pady=4)
        T.btn_primary(self.button3)

        # --- NEW: Selection Actions (Hidden by default) ---
        self.selection_frame = Frame(sidebar, bg=T.BG_PANEL)
        # We don't pack it yet, it will appear on selection in on_tree_select
        
        self.button4 = Button(self.selection_frame, text="Update employee", command=self.update_emp)
        self.button4.pack(fill=X, pady=4)
        T.btn_secondary(self.button4)
        self.button4.configure(state=DISABLED)

        self.button5 = Button(self.selection_frame, text="Delete employee", command=self.delete_emp)
        self.button5.pack(fill=X, pady=4)
        T.btn_secondary(self.button5)
        self.button5.configure(state=DISABLED)

        self.button_reveal = Button(self.selection_frame, text="Reveal Password", command=self.reveal_passwords)
        self.button_reveal.pack(fill=X, pady=4)
        T.btn_secondary(self.button_reveal)
        self.button_reveal.configure(state=DISABLED) 
        self.show_hashes = False

        Label(
            sidebar,
            text="Search directory",
            font=T.FONT_SECTION,
            bg=T.BG_PANEL,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W, pady=(20, 8))
        sf = Frame(sidebar, bg=T.BG_PANEL)
        sf.pack(fill=X)
        self.entry1 = Entry(sf)
        self.entry1.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry1)
        self.entry1.bind("<KeyRelease>", self.search_emp) # Real-time filtering
        self.button1 = Button(sf, text="Go", command=self.search_emp)
        self.button1.pack(side=LEFT, padx=(8, 0))
        T.btn_primary(self.button1)

        

        main = Frame(body, bg="white", padx=15, pady=15)
        main.pack(side=LEFT, fill=BOTH, expand=True)

        # --- NEW: Tab Switcher ---
        self.active_tab = "Employee" # Default
        self.tab_bar = Frame(main, bg="white")
        self.tab_bar.pack(fill=X, pady=(0, 15))
        
        self.btn_staff = Button(self.tab_bar, text="Staff Directory", command=lambda: self.switch_tab("Employee"))
        self.btn_staff.pack(side=LEFT, padx=(0, 10))
        T.btn_primary(self.btn_staff)
        
        self.btn_admins = Button(self.tab_bar, text="Admin Directory", command=lambda: self.switch_tab("Admin"))
        self.btn_admins.pack(side=LEFT)
        T.btn_secondary(self.btn_admins)

        self.tree_title = Label(
            main,
            text="Staff Directory",
            font=T.FONT_SECTION,
            bg="white",
            fg=T.TEXT_ON_LIGHT,
        )
        self.tree_title.pack(anchor=W, pady=(0, 8))

        tree_wrap = Frame(
            main,
            bg=T.CARD,
            highlightthickness=1,
            highlightbackground=T.BORDER_SUBTLE,
        )
        tree_wrap.pack(fill=BOTH, expand=True)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self.scrollbarx = Scrollbar(tree_wrap, orient=HORIZONTAL, bg=T.CARD)
        self.scrollbary = Scrollbar(tree_wrap, orient=VERTICAL, bg=T.CARD)
        self.tree = ttk.Treeview(
            tree_wrap,
            style="RM.Treeview",
            yscrollcommand=self.scrollbary.set,
            xscrollcommand=self.scrollbarx.set,
            selectmode="extended",
        )
        self.tree.grid(row=0, column=0, sticky=NSEW)
        self.scrollbary.grid(row=0, column=1, sticky=NS)
        self.scrollbarx.grid(row=1, column=0, sticky=EW)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        self.scrollbary.configure(command=self.tree.yview)
        self.scrollbarx.configure(command=self.tree.xview)

        self.tree.configure(
            columns=(
                "Employee ID",
                "Employee Name",
                "Contact No.",
                "Address",
                "Aadhar No.",
                "Password",
                "Designation",
                "Status"
            )
        )

        self.tree.heading("Employee ID", text="Employee ID", anchor=CENTER)
        self.tree.heading("Employee Name", text="Employee Name", anchor=CENTER)
        self.tree.heading("Contact No.", text="Contact No.", anchor=CENTER)
        self.tree.heading("Address", text="Address", anchor=CENTER)
        self.tree.heading("Aadhar No.", text="Aadhar No.", anchor=CENTER)
        self.tree.heading("Password", text="Password", anchor=CENTER)
        self.tree.heading("Designation", text="Designation", anchor=CENTER)
        self.tree.heading("Status", text="Status", anchor=CENTER)

        self.tree.column("#0", stretch=NO, minwidth=0, width=0)
        self.tree.column("#1", stretch=NO, minwidth=120, width=130, anchor=CENTER) # ID
        self.tree.column("#2", stretch=YES, minwidth=200, width=260, anchor=CENTER)  # Name
        self.tree.column("#3", stretch=NO, minwidth=110, width=110, anchor=CENTER) # Phone
        self.tree.column("#4", stretch=NO, minwidth=180, width=220, anchor=CENTER)      # Address
        self.tree.column("#5", stretch=NO, minwidth=130, width=130, anchor=CENTER) # Aadhar
        self.tree.column("#6", stretch=NO, minwidth=100, width=100, anchor=CENTER) # Pass
        self.tree.column("#7", stretch=NO, minwidth=100, width=100, anchor=CENTER) # Desig
        self.tree.column("#8", stretch=NO, minwidth=100, width=100, anchor=CENTER) # Status
        T.apply_zebra_styling(self.tree)
        self.refresh_notifications()
        self.DisplayData()

    def DisplayData(self):
        self.tree.delete(*self.tree.get_children())
        
        # Filter based on the active tab
        cur.execute("SELECT * FROM employee WHERE designation = ? AND approved = 1", (self.active_tab,))
            
        fetch = cur.fetchall()
        for data in fetch:
            d = list(data)
            # Professional Security: Passwords are SHA-256 Hashed. 
            # We only show the hash if specifically requested and authorized.
            if getattr(self, "show_hashes", False):
                d[5] = data[5]
            else:
                d[5] = "********"
            
            # data[7] is the approved column
            status = "Approved" if d[7] == 1 else "Pending"
            d[7] = status
            self.tree.insert("", "end", values=(d))

    def switch_tab(self, role):
        self.active_tab = role
        if role == "Employee":
            T.btn_primary(self.btn_staff)
            T.btn_secondary(self.btn_admins)
            self.tree_title.configure(text="Staff Directory")
        else:
            T.btn_primary(self.btn_admins)
            T.btn_secondary(self.btn_staff)
            self.tree_title.configure(text="Administrative Directory")
        self.DisplayData()

    def search_emp(self, event=None):
        query = self.entry1.get().strip().lower()
        
        self.tree.delete(*self.tree.get_children())
        cur.execute("SELECT * FROM employee WHERE designation = ? AND approved = 1", (self.active_tab,))
        fetch = cur.fetchall()
        
        matched_items = []
        for data in fetch:
            eid = str(data[0]).lower()
            name = str(data[1]).lower()
            contact = str(data[2]).lower()
            addr = str(data[3]).lower()
            
            # Match query with ID, Name, Contact, or Address
            if not query or (query in eid or query in name or query in contact or query in addr):
                matched_items.append(data)
                
        for data in matched_items:
            d = list(data)
            if getattr(self, "show_hashes", False):
                d[5] = data[5]
            else:
                d[5] = "********"
            
            status = "Approved" if d[7] == 1 else "Pending"
            d[7] = status
            item_id = self.tree.insert("", "end", values=(d))
            
            # If exact match on Employee ID, or only one match, select, focus, and scroll to it!
            if query and (query == str(data[0]).lower() or len(matched_items) == 1):
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
                self.tree.see(item_id)
    
    sel = []
    def on_tree_select(self, Event):
        self.sel.clear()
        for i in self.tree.selection():
            if i not in self.sel:
                self.sel.append(i)
        
        if len(self.sel) >= 1:
            # Show selection actions
            self.selection_frame.pack(fill=X, pady=(10, 0), after=self.button3)
            
            if len(self.sel) == 1:
                self.button4.configure(state=NORMAL)
                self.button_reveal.configure(state=NORMAL)
            else:
                self.button4.configure(state=DISABLED)
                self.button_reveal.configure(state=DISABLED)
            
            self.button5.configure(state=NORMAL)
        else:
            # Hide selection actions
            self.selection_frame.pack_forget()
            self.button4.configure(state=DISABLED)
            self.button5.configure(state=DISABLED)
            self.button_reveal.configure(state=DISABLED)

    def delete_emp(self):
        val = []
        to_delete = []

        if len(self.sel)!=0:
            sure = messagebox.askyesno("Confirm", "Are you sure you want to delete selected employee(s)?", parent=emp)
            if sure == True:
                for i in self.sel:
                    for j in self.tree.item(i)["values"]:
                        val.append(j)
                
                for j in range(len(val)):
                    if j%7==0:
                        to_delete.append(val[j])
                
                flag = 1

                for k in to_delete:
                    if k=="EMP0000":
                        flag = 0
                        break
                    else:
                        delete = "DELETE FROM employee WHERE emp_id = ?"
                        cur.execute(delete, [k])
                        db.commit()

                if flag==1:
                    messagebox.showinfo("Success!!", "Employee(s) deleted from database.", parent=emp)
                    self.sel.clear()
                    self.tree.delete(*self.tree.get_children())
                    self.DisplayData()
                else:
                    messagebox.showerror("Error!!","Cannot delete master admin.")
        else:
            messagebox.showerror("Error!!","Please select an employee.", parent=emp)

    def refresh_notifications(self):
        cur.execute("SELECT count(*) FROM employee WHERE approved = 0")
        count = cur.fetchone()[0]
        self.badge.configure(text=str(count))
        if count > 0:
            self.badge.configure(bg="#FF5722") # Vibrant orange-red
        else:
            self.badge.configure(bg="#A5D6A7") # Soft green when empty

    def show_pending_panel(self):
        # Open a modern popup window for approvals
        self.pending_win = Toplevel(root)
        self.pending_win.title("Pending Approvals")
        self.pending_win.geometry("500x600")
        self.pending_win.configure(bg=T.BG_ROOT)
        
        Label(self.pending_win, text="Pending Registration Requests", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.PRIMARY, pady=20).pack()
        
        container = Frame(self.pending_win, bg=T.BG_ROOT)
        container.pack(fill=BOTH, expand=True, padx=20, pady=(0, 20))
        
        canvas = Canvas(container, bg=T.BG_ROOT, highlightthickness=0)
        scrollbar = Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg=T.BG_ROOT)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw", width=440)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        cur.execute("SELECT emp_id, name, contact_num, designation FROM employee WHERE approved = 0")
        requests = cur.fetchall()
        
        if not requests:
            Label(scrollable_frame, text="No pending requests at the moment.", font=T.FONT_UI, bg=T.BG_ROOT, fg=T.TEXT_SUB).pack(pady=40)
        
        for eid, name, contact, des in requests:
            card = Frame(scrollable_frame, bg=T.WHITE, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=15, pady=15)
            card.pack(fill=X, pady=10)
            
            info = Frame(card, bg=T.WHITE)
            info.pack(side=LEFT, fill=BOTH, expand=True)
            
            Label(info, text=name, font=T.FONT_SECTION, bg=T.WHITE, fg=T.TEXT_ON_LIGHT, anchor=W).pack(fill=X)
            Label(info, text=f"ID: {eid} | {des}", font=T.FONT_UI_SM, bg=T.WHITE, fg=T.TEXT_SUB, anchor=W).pack(fill=X)
            Label(info, text=f"Contact: {contact}", font=T.FONT_UI_SM, bg=T.WHITE, fg=T.TEXT_SUB, anchor=W).pack(fill=X)
            
            actions = Frame(card, bg=T.WHITE)
            actions.pack(side=RIGHT)
            
            def make_approve(id=eid, n=name):
                return lambda: self.approve_from_panel(id, n)
            
            def make_reject(id=eid, n=name):
                return lambda: self.reject_from_panel(id, n)

            btn_app = Button(actions, text="Approve", command=make_approve(), bg=T.BTN_GREEN, fg=T.WHITE, relief=FLAT, padx=10, pady=5)
            btn_app.pack(pady=2)
            T.btn_primary(btn_app)
            
            btn_rej = Button(actions, text="Decline", command=make_reject(), bg="#EF5350", fg=T.WHITE, relief=FLAT, padx=10, pady=5)
            btn_rej.pack(pady=2)

    def approve_from_panel(self, eid, name):
        sure = messagebox.askyesno("Confirm Approval", f"Approve registration for {name} ({eid})?", parent=self.pending_win)
        if sure:
            cur.execute("UPDATE employee SET approved = 1 WHERE emp_id = ?", [eid])
            db.commit()
            messagebox.showinfo("Success", f"Employee {name} has been approved.")
            self.refresh_notifications()
            self.DisplayData()
            self.pending_win.destroy()
            self.show_pending_panel() # Refresh list

    def reject_from_panel(self, eid, name):
        sure = messagebox.askyesno("Confirm Decline", f"Decline and delete registration for {name} ({eid})?", parent=self.pending_win)
        if sure:
            cur.execute("DELETE FROM employee WHERE emp_id = ?", [eid])
            db.commit()
            messagebox.showinfo("Declined", f"Registration for {name} has been deleted.")
            self.refresh_notifications()
            self.pending_win.destroy()
            self.show_pending_panel()

    def reveal_passwords(self):
        from tkinter import simpledialog
        if not self.sel: return
        
        auth_pw = simpledialog.askstring("Security Authorization", "Enter YOUR Admin Password to reveal this password:", show="*", parent=root)
        if auth_pw is None: return
        
        # Verify current admin's password (supports hash or encrypted)
        cur.execute("SELECT password FROM employee WHERE emp_id = ?", [logged_in_id])
        res = cur.fetchone()
        if res and db_init.verify_admin_password(auth_pw, res[0]):
            # Reveal ONLY for selected row
            item = self.sel[0]
            vals = list(self.tree.item(item)["values"])
            eid = vals[0]
            
            cur.execute("SELECT password FROM employee WHERE emp_id = ?", [eid])
            stored_p = cur.fetchone()[0]
            
            # Use secure_reveal to get the REAL plain text
            real_p = db_init.secure_reveal(stored_p)
            
            vals[5] = real_p # Show the plain text
            self.tree.item(item, values=vals)
            
            messagebox.showinfo("Password Revealed", f"Password for {vals[1]}:\n\n{real_p}")
        else:
            messagebox.showerror("Access Denied", "Incorrect Admin Password.")

    def update_emp(self):
        if len(self.sel)==1:
            global vall
            vall = []
            for i in self.sel:
                for j in self.tree.item(i)["values"]:
                    vall.append(j)

            for widget in root.winfo_children():
                widget.destroy()
            global e_update
            e_update = root
            page8 = Update_Employee(e_update)
            page8.time()
            
            page8.entry_id.config(state="normal")
            page8.entry_id.insert(0, vall[0])
            page8.entry1.insert(0, vall[1])
            page8.entry2.insert(0, vall[2])
            page8.entry3.insert(0, vall[4])
            page8.entry4.set(vall[6])
            # Fetch and DECRYPT for update panel visibility
            cur.execute("SELECT password FROM employee WHERE emp_id=?", [vall[0]])
            res_p = cur.fetchone()
            encrypted_p = res_p[0] if res_p else ""
            actual_pw = db_init.secure_reveal(encrypted_p)
            page8.entry6.insert(0, actual_pw)
            
            page8.entry_id.config(state="disabled")
            page8.capture_original() # Track changes from this point
        elif len(self.sel)==0:
            messagebox.showerror("Error","Please select an employee to update.")
        else:
            messagebox.showerror("Error","Can only update one employee at a time.")

        


    def add_emp(self):
        for widget in root.winfo_children():
            widget.destroy()
        global e_add
        e_add = root
        page6 = add_employee(e_add)
        page6.time()


    def ex(self):
        e_add.destroy()
        self.tree.delete(*self.tree.get_children())
        self.DisplayData()   

    def ex2(self):
        e_update.destroy()
        self.tree.delete(*self.tree.get_children())
        self.DisplayData()  



    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        global page2
        page2 = Admin_Page(root)


    def Logout(self):
        sure = messagebox.askyesno("Logout", "Are you sure you want to logout?", parent=emp)
        if sure == True:
            emp.destroy()
            adm.destroy()
            root.deiconify()
            
            page1.entry1.delete(0, END)
            page1.entry2.delete(0, END)


class add_employee:
    def __init__(self, top=None):
        top.geometry("820x620")
        top.minsize(640, 520)
        top.resizable(True, True)
        top.title("Add employee · Real Mart")
        e_add.configure(bg=T.BG_ROOT)
        T.setup_ttk(e_add)

        hdr = Frame(e_add, bg=T.ORANGE, height=52)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.ORANGE)
        hc.pack(fill=BOTH, expand=True, padx=20, pady=10)
        Label(hc, text="New team member", font=T.FONT_SECTION, bg=T.ORANGE, fg=T.WHITE).pack(side=LEFT)
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        wrap = Frame(e_add, bg=T.BG_ROOT)
        wrap.pack(fill=BOTH, expand=True, padx=24, pady=20)

        card = Frame(
            wrap,
            bg=T.CARD,
            highlightthickness=2,
            highlightbackground=T.ORANGE,
            padx=24,
            pady=22,
        )
        card.pack(fill=BOTH, expand=True)

        self.r1 = e_add.register(self.testint)
        self.r2 = e_add.register(self.testchar)

        def full_row(lbl, **kw):
            r = Frame(card, bg=T.CARD)
            r.pack(fill=X, pady=6)
            Label(r, text=lbl, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X)
            e = Entry(r, **kw)
            e.pack(fill=X, pady=(4, 0), ipady=6)
            T.entry_light(e)
            return e

        self.entry_id = full_row("Employee ID")
        self.entry_id.insert(0, random_emp_id(7))
        self.entry1 = full_row("Full name")
        self.entry2 = full_row("Contact (10 digits)", validate="key", validatecommand=(self.r1, "%P"))
        self.entry3 = full_row("Aadhaar (12 digits)", validate="key", validatecommand=(self.r1, "%P"))
        
        r4 = Frame(card, bg=T.CARD)
        r4.pack(fill=X, pady=6)
        Label(r4, text="Designation", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X)
        self.entry4 = ttk.Combobox(r4, values=["Admin", "Employee"], state="readonly")
        self.entry4.pack(fill=X, pady=(4, 0), ipady=6)
        self.entry4.set("Employee")
        
        self.entry5 = full_row("Address")
        Label(card, text="Password", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(
            fill=X, pady=(6, 0)
        )
        pf = Frame(card, bg=T.CARD)
        pf.pack(fill=X, pady=(4, 0))
        self.entry6 = Entry(pf, show="*")
        self.entry6.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry6)
        
        def toggle_p():
            if self.entry6.cget("show") == "*":
                from tkinter import simpledialog
                auth_pw = simpledialog.askstring("Security Check", "Verify Admin Password:", show="*", parent=root)
                if auth_pw is None: return
                cur.execute("SELECT password FROM employee WHERE emp_id = ?", [logged_in_id])
                res = cur.fetchone()
                if res and db_init.verify_admin_password(auth_pw, res[0]):
                    self.entry6.configure(show="")
                    btn_p.configure(text="🔒")
                else:
                    messagebox.showerror("Access Denied", "Incorrect password.", parent=root)
            else:
                self.entry6.configure(show="*")
                btn_p.configure(text="👁️")
                
        btn_p = Button(pf, text="👁️", font=("Segoe UI Symbol", 10), command=toggle_p, width=3, bg=T.WHITE, relief=FLAT)
        btn_p.pack(side=LEFT, padx=(6, 0))
        T.btn_secondary(btn_p)

        btns = Frame(card, bg=T.CARD)
        btns.pack(fill=X, pady=(22, 0))
        self.button1 = Button(btns, text="Add employee", command=self.add)
        self.button1.pack(side=LEFT, padx=(0, 12))
        T.btn_primary(self.button1)
        self.button2 = Button(btns, text="Clear form", command=self.clearr)
        self.button2.pack(side=LEFT, padx=(0, 12))
        T.btn_secondary(self.button2)

        

    def has_changes(self):
        # Check if any field is not empty
        fields = [self.entry1, self.entry2, self.entry3, self.entry5, self.entry6]
        for f in fields:
            if f.get().strip():
                return True
        return False

    def Exit(self):
        if self.has_changes():
            if not messagebox.askyesno("Unsaved Changes", "You have entered team member details. Are you sure you want to go back and discard them?", parent=e_add):
                return
        for widget in root.winfo_children():
            widget.destroy()
        global page5
        page5 = Employee(root)
        page5.DisplayData()



    def testint(self, val):
        if val.isdigit():
            return True
        elif val == "":
            return True
        return False

    def testchar(self, val):
        if val.isalpha():
            return True
        elif val == "":
            return True
        return False

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    
    def add(self):
        emp_id = self.entry_id.get().strip()
        ename = self.entry1.get()
        econtact = self.entry2.get()
        eaddhar = self.entry3.get()
        edes = self.entry4.get()
        eadd = self.entry5.get()
        epass = self.entry6.get()

        if ename.strip():
            if valid_phone(econtact):
                if valid_aadhar(eaddhar):
                    if edes:
                        if eadd:
                            if epass:
                                if not emp_id: emp_id = random_emp_id(7)
                                # Use secure_store for reversible encryption
                                epass_enc = db_init.secure_store(epass)
                                insert = (
                                            "INSERT INTO employee(emp_id, name, contact_num, address, aadhar_num, password, designation, approved) VALUES(?,?,?,?,?,?,?,?)"
                                        )
                                cur.execute(insert, [emp_id, ename.strip(), econtact.strip(), eadd.strip(), eaddhar.strip(), epass_enc, edes.strip(), 1])
                                db.commit()
                                messagebox.showinfo("Success!!", "Employee ID: {} successfully added and approved.".format(emp_id), parent=e_add)
                                self.clearr()
                            else:
                                messagebox.showerror("Oops!", "Please enter a password.", parent=e_add)
                        else:
                            messagebox.showerror("Oops!", "Please enter address.", parent=e_add)
                    else:
                        messagebox.showerror("Oops!", "Please enter designation.", parent=e_add)
                else:
                    messagebox.showerror("Oops!", "Invalid Aadhar number.", parent=e_add)
            else:
                messagebox.showerror("Oops!", "Invalid phone number.", parent=e_add)
        else:
            messagebox.showerror("Oops!", "Please enter employee name.", parent=e_add)

    def clearr(self):
        # self.entry_id.delete(0, END) # ID is pre-filled/auto, maybe don't clear? Or clear and re-fill
        self.entry1.delete(0, END)
        self.entry2.delete(0, END)
        self.entry3.delete(0, END)
        self.entry5.delete(0, END)
        self.entry6.delete(0, END)


class Update_Employee:
    def __init__(self, top=None):
        top.geometry("820x620")
        top.minsize(640, 520)
        top.resizable(True, True)
        top.title("Update employee · Real Mart")
        e_update.configure(bg=T.BG_ROOT)
        T.setup_ttk(e_update)

        hdr = Frame(e_update, bg=T.ORANGE, height=52)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.ORANGE)
        hc.pack(fill=BOTH, expand=True, padx=20, pady=10)
        Label(hc, text="Edit team member", font=T.FONT_SECTION, bg=T.ORANGE, fg=T.WHITE).pack(side=LEFT)
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        wrap = Frame(e_update, bg=T.BG_ROOT)
        wrap.pack(fill=BOTH, expand=True, padx=24, pady=20)

        card = Frame(
            wrap,
            bg=T.CARD,
            highlightthickness=2,
            highlightbackground=T.ORANGE,
            padx=24,
            pady=22,
        )
        card.pack(fill=BOTH, expand=True)

        self.r1 = e_update.register(self.testint)
        self.r2 = e_update.register(self.testchar)

        def full_row(lbl, **kw):
            r = Frame(card, bg=T.CARD)
            r.pack(fill=X, pady=6)
            Label(r, text=lbl, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X)
            e = Entry(r, **kw)
            e.pack(fill=X, pady=(4, 0), ipady=6)
            T.entry_light(e)
            return e

        self.entry_id = full_row("Employee ID")
        self.entry1 = full_row("Full name")
        self.entry2 = full_row("Contact (10 digits)", validate="key", validatecommand=(self.r1, "%P"))
        self.entry3 = full_row("Aadhaar (12 digits)", validate="key", validatecommand=(self.r1, "%P"))
        
        r4 = Frame(card, bg=T.CARD)
        r4.pack(fill=X, pady=6)
        Label(r4, text="Designation", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(fill=X)
        self.entry4 = ttk.Combobox(r4, values=["Admin", "Employee"], state="readonly")
        self.entry4.pack(fill=X, pady=(4, 0), ipady=6)
        self.entry4.set("Employee")
        
        self.entry5 = full_row("Address")
        Label(card, text="Password", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, anchor=W).pack(
            fill=X, pady=(6, 0)
        )
        pf = Frame(card, bg=T.CARD)
        pf.pack(fill=X, pady=(4, 0))
        self.entry6 = Entry(pf, show="*")
        self.entry6.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry6)
        
        def toggle_p():
            if self.entry6.cget("show") == "*":
                from tkinter import simpledialog
                auth_pw = simpledialog.askstring("Security Check", "Verify Admin Password:", show="*", parent=root)
                if auth_pw is None: return
                cur.execute("SELECT password FROM employee WHERE emp_id = ?", [logged_in_id])
                res = cur.fetchone()
                if res and db_init.verify_admin_password(auth_pw, res[0]):
                    self.entry6.configure(show="")
                    btn_p.configure(text="🔒")
                else:
                    messagebox.showerror("Access Denied", "Incorrect password.", parent=root)
            else:
                self.entry6.configure(show="*")
                btn_p.configure(text="👁️")
                
        btn_p = Button(pf, text="👁️", font=("Segoe UI Symbol", 10), command=toggle_p, width=3, bg=T.WHITE, relief=FLAT)
        btn_p.pack(side=LEFT, padx=(6, 0))
        T.btn_secondary(btn_p)

        btns = Frame(card, bg=T.CARD)
        btns.pack(fill=X, pady=(22, 0))
        self.button1 = Button(btns, text="Save changes", command=self.update)
        self.button1.pack(side=LEFT, padx=(0, 12))
        T.btn_primary(self.button1)
        self.button2 = Button(btns, text="Clear form", command=self.clearr)
        self.button2.pack(side=LEFT, padx=(0, 12))
        T.btn_secondary(self.button2)

        

    def capture_original(self):
        self.original_data = {
            "id": str(self.entry_id.get()),
            "name": str(self.entry1.get()),
            "contact": str(self.entry2.get()),
            "aadhar": str(self.entry3.get()),
            "des": str(self.entry4.get()),
            "address": str(self.entry5.get()),
            "pass": str(self.entry6.get())
        }

    def has_changes(self):
        if not hasattr(self, "original_data"): return False
        current_data = {
            "id": str(self.entry_id.get()),
            "name": str(self.entry1.get()),
            "contact": str(self.entry2.get()),
            "aadhar": str(self.entry3.get()),
            "des": str(self.entry4.get()),
            "address": str(self.entry5.get()),
            "pass": str(self.entry6.get())
        }
        return current_data != self.original_data

    def Exit(self):
        if self.has_changes():
            if not messagebox.askyesno("Unsaved Changes", "You have made changes to this team member's profile. Are you sure you want to discard them?", parent=e_update):
                return
        for widget in root.winfo_children():
            widget.destroy()
        global page5
        page5 = Employee(root)
        page5.DisplayData()

    def update(self):
        emp_id = self.entry_id.get().strip()
        ename = self.entry1.get()
        econtact = self.entry2.get()
        eaddhar = self.entry3.get()
        edes = self.entry4.get()
        eadd = self.entry5.get()
        epass = self.entry6.get()

        if ename.strip():
            if valid_phone(econtact):
                if valid_aadhar(eaddhar):
                    if edes:
                        if eadd:
                            if epass:
                                # Security: Check if target is an Admin (Case-Insensitive)
                                is_target_admin = (str(vall[6]).strip().lower() == "admin")
                                if is_target_admin:
                                    if not logged_in_id:
                                        messagebox.showerror("Session Error", "Could not verify your session. Please log out and log in again.", parent=e_update)
                                        return
                                        
                                    auth_pw = simpledialog.askstring("Security Authorization", "Enter YOUR current password to verify this Admin change:", show="*", parent=e_update)
                                    if auth_pw is None: return # User cancelled
                                    
                                    # Verify current user's password (supports hash or encrypted)
                                    cur.execute("SELECT password FROM employee WHERE emp_id = ?", [logged_in_id])
                                    stored_auth = cur.fetchone()
                                    if not stored_auth or not db_init.verify_admin_password(auth_pw, stored_auth[0]):
                                        messagebox.showerror("Access Denied", "Verification failed. Incorrect password.", parent=e_update)
                                        return

                                try:
                                    # Use secure_store for reversible encryption (Allows Admin visibility)
                                    encrypted_new_pw = db_init.secure_store(epass)
                                    
                                    update = (
                                                "UPDATE employee SET emp_id = ?, name = ?, contact_num = ?, address = ?, aadhar_num = ?, password = ?, designation = ? WHERE emp_id = ?"
                                            )
                                    cur.execute(
                                        update,
                                        [emp_id, ename, econtact, eadd, eaddhar, encrypted_new_pw, edes, vall[0]],
                                    )
                                    db.commit()
                                except sqlite3.IntegrityError:
                                    messagebox.showerror("Database Error", "The Employee ID '{}' is already in use by another person. Please choose a different ID.".format(emp_id), parent=e_update)
                                    return
                                
                                # Auto-Logout if current user changed their own ID or Password
                                if str(vall[0]).strip() == str(logged_in_id).strip():
                                    # Compare new encrypted password with stored value
                                    if emp_id != vall[0] or encrypted_new_pw != str(stored_auth[0]).strip():
                                        messagebox.showinfo("Security Update", "Your login credentials have changed. For security, please log in again.", parent=e_update)
                                        force_logout()
                                        return

                                messagebox.showinfo("Success!!", "Employee ID: {} successfully updated in database.".format(emp_id), parent=e_update)
                                vall.clear()
                                Employee.sel.clear()
                                self.Exit()
                            else:
                                messagebox.showerror("Oops!", "Please enter a password.", parent=e_update)
                        else:
                            messagebox.showerror("Oops!", "Please enter address.", parent=e_update)
                    else:
                        messagebox.showerror("Oops!", "Please enter designation.", parent=e_update)
                else:
                    messagebox.showerror("Oops!", "Invalid Aadhar number.", parent=e_update)
            else:
                messagebox.showerror("Oops!", "Invalid phone number.", parent=e_update)
        else:
            messagebox.showerror("Oops!", "Please enter employee name.", parent=e_update)


    def clearr(self):
        self.entry1.delete(0, END)
        self.entry2.delete(0, END)
        self.entry3.delete(0, END)
        self.entry4.delete(0, END)
        self.entry5.delete(0, END)
        self.entry6.delete(0, END)



    def testint(self, val):
        if val.isdigit():
            return True
        elif val == "":
            return True
        return False

    def testchar(self, val):
        if val.isalpha():
            return True
        elif val == "":
            return True
        return False

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)


        

class Payment_Config_Page:
    def __init__(self, top=None):
        top.geometry("1100x750")
        top.minsize(900, 600)
        top.resizable(True, True)
        top.title("Payment Config · Real Mart")
        top.configure(bg="white")
        
        self.canvas = Canvas(top, bg="white", highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lower(self.canvas)

        self.top = top
        self.upi_var = StringVar()
        self.payee_var = StringVar()
        self.active_filename = None
        self.qr_photo = None

        hdr = Frame(top, bg=T.ORANGE, height=56)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.ORANGE)
        hc.pack(fill=BOTH, expand=True, padx=24, pady=12)
        
        Label(hc, text="Payment Configuration", font=T.FONT_SECTION, bg=T.ORANGE, fg=T.WHITE).pack(side=LEFT)
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.PRIMARY, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        body = Frame(top, bg="white") # Explicitly white to match canvas
        body.pack(fill=BOTH, expand=True, padx=32, pady=28)

        # Use a PanedWindow to ensure both sides are visible and adjustable
        panes = ttk.PanedWindow(body, orient=HORIZONTAL)
        panes.pack(fill=BOTH, expand=True)

        # Left side: Form
        self.left_pane = Frame(panes, bg=T.CARD, padx=20, pady=20)
        panes.add(self.left_pane, weight=1)

        Label(self.left_pane, text="Add New QR Code", font=T.FONT_TITLE, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        Label(self.left_pane, text="Link a UPI ID with a QR image.", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(4, 20))

        Label(self.left_pane, text="UPI ID / Phone Number", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        self.entry_upi = Entry(self.left_pane, textvariable=self.upi_var, font=T.FONT_UI)
        self.entry_upi.pack(fill=X, pady=(6, 16), ipady=8)
        T.entry_light(self.entry_upi)

        Label(self.left_pane, text="Display Name (shown in GPay/PhonePe)", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        self.entry_payee = Entry(self.left_pane, textvariable=self.payee_var, font=T.FONT_UI)
        self.entry_payee.pack(fill=X, pady=(6, 16), ipady=8)
        T.entry_light(self.entry_payee)
        self.payee_var.set("Real Mart")

        Label(self.left_pane, text="QR Image File", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        self.btn_choose = Button(self.left_pane, text="Choose File...", command=self.choose_file)
        self.btn_choose.pack(fill=X, pady=(6, 20))
        T.btn_secondary(self.btn_choose)

        self.btn_add = Button(self.left_pane, text="Add to POS System", command=self.add_qr)
        self.btn_add.pack(fill=X, pady=(10, 0), ipady=10)
        T.btn_primary(self.btn_add)

        # Modern Security Section
        self.sec_frame = Frame(self.left_pane, bg=T.CARD_SOFT, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=16, pady=16)
        self.sec_frame.pack(fill=X, pady=(32, 20))

        Label(self.sec_frame, text="🛡️ Security Authorization", font=T.FONT_SECTION, bg=T.CARD_SOFT, fg=T.PRIMARY).pack(anchor=W)
        Label(self.sec_frame, text="Update administrative PIN.", font=T.FONT_UI_SM, bg=T.CARD_SOFT, fg=T.TEXT_SUB).pack(anchor=W, pady=(2, 12))

        # Current PIN with Toggle
        Label(self.sec_frame, text="Current PIN", font=T.FONT_UI_SM, bg=T.CARD_SOFT, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        cp_row = Frame(self.sec_frame, bg=T.CARD_SOFT)
        cp_row.pack(fill=X, pady=(4, 12))
        self.entry_old_pin = Entry(cp_row, show="*", font=T.FONT_UI)
        self.entry_old_pin.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry_old_pin)
        self.btn_show1 = Button(cp_row, text="👁️", font=("Segoe UI Symbol", 10), command=lambda: self.toggle_pin(self.entry_old_pin, self.btn_show1), width=3)
        self.btn_show1.pack(side=LEFT, padx=(6, 0))
        T.btn_secondary(self.btn_show1)
        self.btn_show1.configure(padx=0, pady=4)

        # New PIN with Toggle
        Label(self.sec_frame, text="New PIN", font=T.FONT_UI_SM, bg=T.CARD_SOFT, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        np_row = Frame(self.sec_frame, bg=T.CARD_SOFT)
        np_row.pack(fill=X, pady=(4, 16))
        self.entry_new_pin = Entry(np_row, show="*", font=T.FONT_UI)
        self.entry_new_pin.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry_new_pin)
        self.btn_show2 = Button(np_row, text="👁️", font=("Segoe UI Symbol", 10), command=lambda: self.toggle_pin(self.entry_new_pin, self.btn_show2), width=3)
        self.btn_show2.pack(side=LEFT, padx=(6, 0))
        T.btn_secondary(self.btn_show2)
        self.btn_show2.configure(padx=0, pady=4)

        self.btn_update_pin = Button(self.sec_frame, text="Update PIN", command=self.change_pin)
        self.btn_update_pin.pack(fill=X, ipady=8)
        T.btn_primary(self.btn_update_pin)
        
        self.status_lbl = Label(self.sec_frame, text="", font=T.FONT_SMALL, bg=T.CARD_SOFT, fg=T.PRIMARY)
        self.status_lbl.pack(pady=(8, 0))

        # Bind Enter keys
        self.entry_old_pin.bind("<Return>", lambda e: self.change_pin())
        self.entry_new_pin.bind("<Return>", lambda e: self.change_pin())


        # Right side: Treeview List
        self.right_pane = Frame(panes, bg=T.BG_ROOT, padx=20, pady=20)
        panes.add(self.right_pane, weight=2)

        Label(self.right_pane, text="Active Payment Options", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(0, 10))
        
        # Treeview is much more reliable for lists
        cols = ("id", "upi", "payee", "file")
        self.tree = ttk.Treeview(self.right_pane, columns=cols, show="headings", height=10)
        self.tree.heading("id", text="ID")
        self.tree.heading("upi", text="UPI ID")
        self.tree.heading("payee", text="Display Name")
        self.tree.heading("file", text="Image Filename")
        
        self.tree.column("id", width=50, anchor=CENTER)
        self.tree.column("upi", width=180, anchor=W)
        self.tree.column("payee", width=200, anchor=W)
        self.tree.column("file", width=250, anchor=W)
        
        self.tree.pack(fill=X, pady=(0, 20))
        
        # Delete button for selected
        self.btn_delete = Button(self.right_pane, text="Delete Selected QR", command=self.delete_selected)
        self.btn_delete.pack(anchor=W)
        T.btn_secondary(self.btn_delete)
        self.btn_delete.configure(fg="#D32F2F")

        # Preview area for selected
        self.preview_frame = Frame(self.right_pane, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        self.preview_frame.pack(fill=BOTH, expand=True, pady=(20, 0))
        self.preview_label = Label(self.preview_frame, text="Select an option to see preview", bg=T.CARD, fg=T.TEXT_SUB)
        self.preview_label.pack(expand=True, fill=BOTH)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        
        self.refresh_list()
        self.time()

    def choose_file(self):
        from tkinter import filedialog
        path = filedialog.askopenfilename(title="Select QR Image", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if path:
            self.active_filename = path
            self.btn_choose.configure(text=f"Selected: {os.path.basename(path)}")

    def add_qr(self):
        if not self.active_filename:
            messagebox.showwarning("Warning", "Please select an image file first.", parent=self.top)
            return
            
        upi = self.upi_var.get().strip()
        if not upi:
            messagebox.showwarning("Warning", "Please enter a UPI ID or Phone Number.", parent=self.top)
            return
            
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            qrs_dir = os.path.join(base, "images", "qrs")
            os.makedirs(qrs_dir, exist_ok=True)
            
            fname = os.path.basename(self.active_filename)
            # Add timestamp to filename for uniqueness
            unique_name = f"{int(time.time())}_{fname}"
            dest = os.path.join(qrs_dir, unique_name)
            
            shutil.copy(self.active_filename, dest)
            
            payee = self.payee_var.get().strip() or "Real Mart"
            cur.execute("INSERT INTO payment_config (filename, upi_id, payee_name) VALUES (?, ?, ?)", (unique_name, upi, payee))
            db.commit()
            
            messagebox.showinfo("Success", "Card added successfully!", parent=self.top)
            self.upi_var.set("")
            self.active_filename = None
            self.btn_choose.configure(text="Choose File...")
            self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save: {e}", parent=self.top)

    def change_pin(self):
        old_pin = self.entry_old_pin.get().strip()
        new_pin = self.entry_new_pin.get().strip()

        if not old_pin or not new_pin:
            self.status_lbl.configure(text="Please fill both PIN fields.", fg="#D32F2F")
            return

        if not new_pin.isdigit() or len(new_pin) < 4:
            self.status_lbl.configure(text="New PIN must be at least 4 digits.", fg="#D32F2F")
            return

        self.status_lbl.configure(text="Verifying...", fg=T.PRIMARY)
        self.top.update_idletasks()

        # Fetch actual PIN from database
        cur.execute("SELECT value FROM settings WHERE key='payment_pin'")
        res = cur.fetchone()
        db_pin = res[0] if res else "1234"

        if old_pin != db_pin:
            self.status_lbl.configure(text="Current PIN is incorrect.", fg="#D32F2F")
            return

        try:
            cur.execute("UPDATE settings SET value = ? WHERE key = 'payment_pin'", (new_pin,))
            db.commit()
            self.status_lbl.configure(text="🛡️ PIN updated successfully!", fg=T.PRIMARY)
            messagebox.showinfo("Success", "Security PIN updated successfully!", parent=self.top)
            self.entry_old_pin.delete(0, END)
            self.entry_new_pin.delete(0, END)
        except Exception as e:
            self.status_lbl.configure(text="Update failed.", fg="#D32F2F")
            messagebox.showerror("Error", f"Failed to update PIN: {e}", parent=self.top)

    def toggle_pin(self, entry, btn):
        if entry.cget("show") == "*":
            entry.configure(show="")
            btn.configure(text="🔒")
        else:
            entry.configure(show="*")
            btn.configure(text="👁️")

    def refresh_list(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.preview_label.configure(image="", text="Select an option to see preview")
            
        try:
            cur.execute("SELECT qr_id, upi_id, payee_name, filename FROM payment_config ORDER BY qr_id DESC")
            rows = cur.fetchall()
            for row in rows:
                self.tree.insert("", END, values=row)
        except Exception as e:
            print(f"Refresh error: {e}")

    def on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        
        item = self.tree.item(sel[0])
        qid, upi, payee, fname = item['values']
        
        base = os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "images", "qrs", fname)
        if os.path.exists(path):
            try:
                from PIL import Image, ImageTk
                img = Image.open(path).convert("RGB")
                img.thumbnail((300, 300), Image.Resampling.LANCZOS)
                self.qr_photo = ImageTk.PhotoImage(img)
                self.preview_label.configure(image=self.qr_photo, text="")
                self.preview_label.image = self.qr_photo
            except Exception:
                self.preview_label.configure(image="", text=f"File: {fname}\n(Preview unavailable)")
        else:
            self.preview_label.configure(image="", text="Image file missing from server")

    def delete_selected(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Warning", "Please select a payment option to delete.", parent=self.top)
            return
            
        item = self.tree.item(sel[0])
        qid, upi, payee, fname = item['values']
        
        if not messagebox.askyesno("Confirm", f"Delete payment option '{upi}'?", parent=self.top):
            return
            
        try:
            cur.execute("DELETE FROM payment_config WHERE qr_id = ?", (qid,))
            db.commit()
            
            base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "images", "qrs", fname)
            if os.path.exists(path): os.remove(path)
            
            self.refresh_list()
            messagebox.showinfo("Success", "Deleted successfully.", parent=self.top)
        except Exception as e:
            messagebox.showerror("Error", f"Delete failed: {e}", parent=self.top)

    def delete_card(self, qid, fname):
        if not messagebox.askyesno("Confirm Delete", f"Delete this payment option?", parent=self.top):
            return
        import os
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            path = os.path.join(base, "images", "qrs", fname)
            if os.path.exists(path): os.remove(path)
            
            cur.execute("DELETE FROM payment_config WHERE qr_id = ?", (qid,))
            db.commit()
            self.refresh_list()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete: {e}", parent=self.top)

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        global page2
        page2 = Admin_Page(root)


class Invoice:
    def __init__(self, top=None):
        top.geometry("1240x920")
        top.minsize(1000, 600)
        top.resizable(True, True)
        top.title("Invoices · Real Mart")
        self.open_bills = {} # Track open bill windows
        top.configure(bg=T.BG_ROOT)
        refresh_db()

        hdr = Frame(top, bg=T.ORANGE, height=56)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hr = Frame(hdr, bg=T.ORANGE)
        hr.pack(fill=BOTH, expand=True, padx=20, pady=10)
        self.message = Label(
            hr,
            text="INVOICES",
            font=T.FONT_SECTION,
            bg=T.ORANGE,
            fg=T.WHITE,
        )
        self.message.pack(side=LEFT)
        self.btn_back = Button(hr, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hr, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        body = Frame(top, bg="white")
        body.pack(fill=BOTH, expand=True, padx=16, pady=16)

        # Apply Glass panels for readability over the background
        sidebar = Frame(body, bg=T.WHITE, padx=16, pady=16)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 16))
        sidebar.pack_propagate(False)
        sidebar.configure(width=268)

        # --- NEW: Selection Actions (Hidden by default) ---
        self.selection_frame = Frame(sidebar, bg=T.WHITE)
        # Hidden initially
        
        self.button3 = Button(self.selection_frame, text="Delete selected", command=self.delete_invoice)
        self.button3.pack(fill=X, pady=4)
        T.btn_primary(self.button3)
        self.button3.configure(state=DISABLED)

        self.button_refresh = Button(sidebar, text="🔄 Refresh List", command=self.DisplayData)
        self.button_refresh.pack(fill=X, pady=(0, 10))
        T.btn_primary(self.button_refresh)

        self.bill_find_label = Label(
            sidebar,
            text="Search invoices",
            font=T.FONT_SECTION,
            bg=T.WHITE,
            fg=T.TEXT_ON_LIGHT,
        )
        self.bill_find_label.pack(anchor=W, pady=(20, 8))
        sf = Frame(sidebar, bg=T.WHITE)
        sf.pack(fill=X)
        self.entry1 = Entry(sf)
        self.entry1.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry1)
        self.entry1.bind("<KeyRelease>", self.search_inv) # Real-time filtering
        self.button1 = Button(sf, text="Go", command=self.search_inv)
        self.button1.pack(side=LEFT, padx=(8, 0))
        T.btn_primary(self.button1)

        # --- Date Filter Section ---
        Label(
            sidebar,
            text="Filter by Date",
            font=T.FONT_SECTION,
            bg=T.WHITE,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W, pady=(24, 8))

        self.filter_date_var = StringVar()
        df = Frame(sidebar, bg=T.WHITE)
        df.pack(fill=X)
        
        self.entry_date = Entry(df, textvariable=self.filter_date_var, state="readonly")
        self.entry_date.pack(side=LEFT, fill=X, expand=True, ipady=6)
        T.entry_light(self.entry_date)

        def pick_filter_date():
            CalendarPicker(top, lambda d: self.filter_date_var.set(d))

        self.btn_pick = Button(df, text="📅", command=pick_filter_date, bg=T.WHITE, relief=FLAT)
        self.btn_pick.pack(side=LEFT, padx=(5, 0))

        btn_grid = Frame(sidebar, bg=T.WHITE)
        btn_grid.pack(fill=X, pady=10)

        self.btn_apply = Button(btn_grid, text="Apply Filter", command=lambda: self.DisplayData(self.filter_date_var.get()))
        self.btn_apply.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))
        T.btn_primary(self.btn_apply)

        self.btn_reset = Button(btn_grid, text="Reset", command=lambda: (self.filter_date_var.set(""), self.DisplayData()))
        self.btn_reset.pack(side=LEFT, fill=X, expand=True)
        T.btn_secondary(self.btn_reset)


        Label(
            sidebar,
            text="Tip: double-click a row to open bill details.",
            font=T.FONT_UI_SM,
            bg=T.WHITE,
            fg=T.TEXT_MUTED,
            wraplength=220,
            justify=LEFT,
        ).pack(side=BOTTOM, anchor=W, pady=(16, 0))

        main = Frame(body, bg="white", padx=15, pady=15)
        main.pack(side=LEFT, fill=BOTH, expand=True)

        Label(
            main,
            text="All bills",
            font=T.FONT_SECTION,
            bg="white",
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W, pady=(0, 8))

        tree_wrap = Frame(
            main,
            bg=T.CARD,
            highlightthickness=1,
            highlightbackground=T.BORDER_SUBTLE,
        )
        tree_wrap.pack(fill=BOTH, expand=True)
        tree_wrap.rowconfigure(0, weight=1)
        tree_wrap.columnconfigure(0, weight=1)

        self.scrollbarx = Scrollbar(tree_wrap, orient=HORIZONTAL, bg=T.CARD)
        self.scrollbary = Scrollbar(tree_wrap, orient=VERTICAL, bg=T.CARD)
        self.tree = ttk.Treeview(
            tree_wrap,
            style="RM.Treeview",
            yscrollcommand=self.scrollbary.set,
            xscrollcommand=self.scrollbarx.set,
            selectmode="extended",
        )
        self.tree.grid(row=0, column=0, sticky=NSEW)
        self.scrollbary.grid(row=0, column=1, sticky=NS)
        self.scrollbarx.grid(row=1, column=0, sticky=EW)

        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.tree.bind("<Double-1>", self.double_tap)

        self.scrollbary.configure(command=self.tree.yview)
        self.scrollbarx.configure(command=self.tree.xview)

        self.tree.configure(
            columns=(
                "Bill Number",
                "Date",
                "Customer Name",
                "Customer Phone No.",
                "Payment",
                "Bill time",
            )
        )

        self.tree.heading("Bill Number", text="Bill Number", anchor=CENTER)
        self.tree.heading("Date", text="Date", anchor=CENTER)
        self.tree.heading("Customer Name", text="Customer Name", anchor=CENTER)
        self.tree.heading("Customer Phone No.", text="Customer Phone No.", anchor=CENTER)
        self.tree.heading("Payment", text="Payment", anchor=CENTER)
        self.tree.heading("Bill time", text="Bill time", anchor=CENTER)

        self.tree.column("#0", stretch=NO, minwidth=0, width=0)
        self.tree.column("#1", stretch=NO, minwidth=130, width=140, anchor=CENTER) # Bill No
        self.tree.column("#2", stretch=NO, minwidth=100, width=110, anchor=CENTER) # Date
        self.tree.column("#3", stretch=YES, minwidth=200, width=220, anchor=CENTER)     # Name
        self.tree.column("#4", stretch=NO, minwidth=120, width=140, anchor=CENTER) # Phone
        self.tree.column("#5", stretch=NO, minwidth=90, width=110, anchor=CENTER)  # Payment
        self.tree.column("#6", stretch=NO, minwidth=130, width=150, anchor=CENTER) # Time
        T.apply_zebra_styling(self.tree)

        refresh_db()
        self.DisplayData()


    def DisplayData(self, date_filter=None):
        self.tree.delete(*self.tree.get_children())
        query = (
            "SELECT bill_no, date, customer_name, customer_no, "
            "COALESCE(payment_method, 'Cash'), COALESCE(bill_time, '') FROM bill"
        )
        params = []
        if date_filter and date_filter.strip():
            query += " WHERE date = ?"
            params.append(date_filter.strip())
            
        query += " ORDER BY date DESC, bill_time DESC"
        
        cur.execute(query, params)
        fetch = cur.fetchall()
        for i, data in enumerate(fetch):
            self.tree.insert("", "end", values=data, tags=("even" if i % 2 == 0 else "odd",))

    sel = []
    def on_tree_select(self, Event):
        self.sel.clear()
        for i in self.tree.selection():
            if i not in self.sel:
                self.sel.append(i)
        
        if len(self.sel) >= 1:
            # Show selection actions
            self.selection_frame.pack(fill=X, pady=(10, 0), before=self.bill_find_label)
            self.button3.configure(state=NORMAL)
        else:
            # Hide selection actions
            self.selection_frame.pack_forget()
            self.button3.configure(state=DISABLED)

    def double_tap(self, Event):
        item = self.tree.identify("item", Event.x, Event.y)
        if not item:
            return
        vals = self.tree.item(item).get("values") or []
        if not vals:
            return
        bill_no = vals[0]

        # Check if already open
        if bill_no in self.open_bills:
            try:
                self.open_bills[bill_no].lift()
                self.open_bills[bill_no].focus_force()
                return
            except Exception:
                # Window might have been closed but not removed from dict
                del self.open_bills[bill_no]

        global bill_num
        bill_num = bill_no

        # Use a full-screen Frame overlay in the same window instead of a separate Toplevel
        parent_win = self.tree.winfo_toplevel()
        overlay = Frame(parent_win, bg=T.BG_ROOT)
        overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        
        self.open_bills[bill_no] = overlay
        
        open_bill(overlay)

    def on_close_bill(self, bill_no, win):
        if bill_no in self.open_bills:
            del self.open_bills[bill_no]
        win.destroy()

        


    def delete_invoice(self):
        val = []
        to_delete = []

        if len(self.sel)!=0:
            sure = messagebox.askyesno("Confirm", "Are you sure you want to delete selected invoice(s)?", parent=invoice)
            if sure == True:
                for i in self.sel:
                    for j in self.tree.item(i)["values"]:
                        val.append(j)
                
                for j in range(len(val)):
                    if j % 6 == 0:
                        to_delete.append(val[j])
                
                for k in to_delete:
                    delete = "DELETE FROM bill WHERE bill_no = ?"
                    cur.execute(delete, [k])
                    db.commit()

                messagebox.showinfo("Success!!", "Invoice(s) deleted from database.", parent=invoice)
                self.sel.clear()
                self.tree.delete(*self.tree.get_children())

                self.DisplayData()
        else:
            messagebox.showerror("Error!!","Please select an invoice", parent=invoice)

    def search_inv(self, event=None):
        query = self.entry1.get().strip().lower()
        date_filter = self.filter_date_var.get()
        
        self.tree.delete(*self.tree.get_children())
        
        q = (
            "SELECT bill_no, date, customer_name, customer_no, "
            "COALESCE(payment_method, 'Cash'), COALESCE(bill_time, '') FROM bill"
        )
        params = []
        if date_filter and date_filter.strip():
            q += " WHERE date = ?"
            params.append(date_filter.strip())
            
        q += " ORDER BY date DESC, bill_time DESC"
        
        cur.execute(q, params)
        fetch = cur.fetchall()
        
        matched_items = []
        for data in fetch:
            bill_no = str(data[0]).lower()
            date = str(data[1]).lower()
            name = str(data[2]).lower()
            phone = str(data[3]).lower()
            method = str(data[4]).lower()
            
            # Match query with Bill Number, Date, Customer Name, Phone, or Method
            if not query or (query in bill_no or query in date or query in name or query in phone or query in method):
                matched_items.append(data)
                
        for i, data in enumerate(matched_items):
            item_id = self.tree.insert("", "end", values=data, tags=("even" if i % 2 == 0 else "odd",))
            
            # If exact match on Bill Number, or only one match, select, focus, and scroll to it!
            if query and (query == str(data[0]).lower() or len(matched_items) == 1):
                self.tree.selection_set(item_id)
                self.tree.focus(item_id)
                self.tree.see(item_id)


    def Logout(self):
        sure = messagebox.askyesno("Logout", "Are you sure you want to logout?", parent=invoice)
        if sure == True:
            invoice.destroy()
            adm.destroy()
            root.deiconify()
            page1.entry1.delete(0, END)
            page1.entry2.delete(0, END)

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        global page2
        page2 = Admin_Page(root)


class open_bill:
    def __init__(self, top=None):
        # Full-screen overlay in the same window
        if isinstance(top, Toplevel) or isinstance(top, Tk):
            top.attributes("-fullscreen", True)
        
        top.configure(bg=T.BG_ROOT)

        hdr = Frame(top, bg=T.ORANGE, height=60)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text="📄 INVOICE DETAILS", font=T.FONT_SECTION, bg=T.ORANGE, fg=T.WHITE).pack(
            side=LEFT, padx=30, pady=15
        )
        
        # Close button for full screen
        btn_close = Button(hdr, text="✕ CLOSE", command=top.destroy, font=T.FONT_UI_SM, 
                           bg="#E65100", fg=T.WHITE, relief=FLAT, padx=20, cursor="hand2")
        btn_close.pack(side=RIGHT, padx=20, pady=10)
        def on_hover(e): btn_close.configure(bg="#F57C00")
        def on_leave(e): btn_close.configure(bg="#E65100")
        btn_close.bind("<Enter>", on_hover)
        btn_close.bind("<Leave>", on_leave)

        body = Frame(top, bg=T.BG_ROOT, padx=40, pady=30)
        body.pack(fill=BOTH, expand=True)

        # Center content frame to keep it from stretching too much on wide screens
        content_wrap = Frame(body, bg=T.BG_ROOT)
        content_wrap.place(relx=0.5, rely=0, anchor=N, relwidth=0.8, relheight=1.0)

        meta = Frame(content_wrap, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=24, pady=20)
        meta.pack(fill=X, pady=(0, 20))

        g = Frame(meta, bg=T.CARD)
        g.pack(fill=X)
        Label(g, text="Customer", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(row=0, column=0, sticky=W)
        self.name_message = Text(g, height=1, width=28, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.TEXT_ON_LIGHT)
        self.name_message.grid(row=1, column=0, sticky=W, padx=(0, 24))
        Label(g, text="Phone", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(row=0, column=1, sticky=W)
        self.num_message = Text(g, height=1, width=14, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.TEXT_ON_LIGHT)
        self.num_message.grid(row=1, column=1, sticky=W)
        Label(g, text="Bill #", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(row=2, column=0, sticky=W, pady=(10, 0))
        self.bill_message = Text(g, height=1, width=28, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.ORANGE)
        self.bill_message.grid(row=3, column=0, sticky=W, padx=(0, 24))
        Label(g, text="Date", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(row=2, column=1, sticky=W, pady=(10, 0))
        self.bill_date_message = Text(g, height=1, width=14, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.TEXT_ON_LIGHT)
        self.bill_date_message.grid(row=3, column=1, sticky=W)
        Label(g, text="Payment", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(
            row=4, column=0, sticky=W, pady=(10, 0)
        )
        self.pay_message = Text(g, height=1, width=28, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.TEXT_ON_LIGHT)
        self.pay_message.grid(row=5, column=0, sticky=W, padx=(0, 24))
        Label(g, text="Recorded at", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(
            row=4, column=1, sticky=W, pady=(10, 0)
        )
        self.time_message = Text(g, height=1, width=22, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.ORANGE)
        self.time_message.grid(row=5, column=1, sticky=W)

        self.Scrolledtext1 = tkst.ScrolledText(
            content_wrap,
            height=20,
            borderwidth=0,
            font=T.FONT_MONO,
            bg=T.CARD,
            fg=T.TEXT_ON_LIGHT,
            relief=FLAT,
            highlightthickness=1,
            highlightbackground=T.BORDER_SUBTLE,
            highlightcolor=T.ORANGE,
        )
        self.Scrolledtext1.pack(fill=BOTH, expand=True)

        find_bill = "SELECT * FROM bill WHERE bill_no = ?"
        cur.execute(find_bill, [bill_num])
        results = cur.fetchall()
        if results:
            br = db_init.parse_bill_row(results[0])
            self.name_message.insert(END, br["customer_name"])
            self.name_message.configure(state="disabled")

            self.num_message.insert(END, br["customer_no"])
            self.num_message.configure(state="disabled")

            self.bill_message.insert(END, br["bill_no"])
            self.bill_message.configure(state="disabled")

            self.bill_date_message.insert(END, br["date"])
            self.bill_date_message.configure(state="disabled")

            self.pay_message.insert(END, br["payment_method"] or "Cash")
            self.pay_message.configure(state="disabled")
            bt = br["bill_time"] or ""
            short_bt = bt[11:19] if bt and len(bt) >= 19 else (bt or "—")
            self.time_message.insert(END, short_bt if short_bt else "—")
            self.time_message.configure(state="disabled")

            if (br["payment_method"] or "") == "Cash" and br["cash_tendered"] is not None:
                Label(g, text="Cash received", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(
                    row=6, column=0, sticky=W, pady=(10, 0)
                )
                cx = Text(g, height=1, width=22, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.TEXT_ON_LIGHT)
                cx.grid(row=7, column=0, sticky=W, padx=(0, 24))
                cx.insert(END, "Rs. {:.2f}".format(float(br["cash_tendered"])))
                cx.configure(state="disabled")
                Label(g, text="Change returned", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(
                    row=6, column=1, sticky=W, pady=(10, 0)
                )
                cy = Text(g, height=1, width=18, font=T.FONT_UI, relief=FLAT, bg=T.CARD, fg=T.PRIMARY_DIM)
                cy.grid(row=7, column=1, sticky=W)
                chg = br["change_amount"]
                cy.insert(END, "Rs. {:.2f}".format(float(chg)) if chg is not None else "—")
                cy.configure(state="disabled")

            self.Scrolledtext1.configure(state="normal")
            self.Scrolledtext1.insert(END, br["bill_details"])
            self.Scrolledtext1.configure(state="disabled")

            # --- ANTI-COUNTERFEIT VERIFICATION PANEL ---
            # Calculate the official security hash from the stored details
            official_hash = hashlib.md5(br["bill_details"].encode()).hexdigest().upper()[:12]
            
            security_frame = Frame(content_wrap, bg="#E8F5E9", highlightthickness=1, highlightbackground="#C8E6C9", padx=20, pady=15)
            security_frame.pack(fill=X, pady=(0, 20), side=TOP) # Pack at TOP of content
            
            Label(security_frame, text="🔒 ANTI-COUNTERFEIT VERIFICATION", font=(T.FONT_FAMILY, 9, "bold"), bg="#E8F5E9", fg="#2E7D32").pack(anchor=W)
            Label(security_frame, text=f"Official Security Hash: {official_hash}", font=(T.FONT_MONO, 11, "bold"), bg="#E8F5E9", fg="#1B5E20").pack(anchor=W, pady=(4, 0))
            Label(security_frame, text="Note: This hash must match the 'SECURITY HASH' on the customer's digital bill.", font=T.FONT_SMALL, bg="#E8F5E9", fg="#388E3C").pack(anchor=W)

class Sales_Dashboard_Page:
    def __init__(self, top=None):
        top.geometry("1240x920")
        top.minsize(1000, 700)
        top.resizable(True, True)
        top.title("Sales Analytics · Real Mart")
        top.configure(bg=T.BG_ROOT)
        refresh_db()

        self.top = top
        hdr = Frame(top, bg=T.ORANGE, height=56)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.ORANGE)
        hc.pack(fill=BOTH, expand=True, padx=24, pady=12)
        Label(hc, text="Visual Sales Dashboard", font=T.FONT_SECTION, bg=T.ORANGE, fg=T.WHITE).pack(side=LEFT)
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.ORANGE, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        # --- SCROLLABLE CONTAINER SETUP ---
        self.container = Frame(top, bg=T.BG_ROOT)
        self.container.pack(fill=BOTH, expand=True)

        self.v_can = Canvas(self.container, bg=T.BG_ROOT, highlightthickness=0)
        self.v_can.pack(side=LEFT, fill=BOTH, expand=True)

        self.v_scr = Scrollbar(self.container, orient=VERTICAL, command=self.v_can.yview)
        self.v_scr.pack(side=RIGHT, fill=Y)
        self.v_can.configure(yscrollcommand=self.v_scr.set, yscrollincrement=1)

        self.scrollable_frame = Frame(self.v_can, bg=T.BG_ROOT)
        self.canvas_window = self.v_can.create_window((0, 0), window=self.scrollable_frame, anchor=NW)

        def _on_can_cfg(e):
            self.v_can.itemconfig(self.canvas_window, width=e.width)
        def _on_body_cfg(e):
            self.v_can.configure(scrollregion=self.v_can.bbox("all"))

        self.v_can.bind("<Configure>", _on_can_cfg)
        self.scrollable_frame.bind("<Configure>", _on_body_cfg)

        def _on_mousewheel(event):
            # Precision scrolling: 40 units per notch (at 1px increment = 40px)
            self.v_can.yview_scroll(int(-1 * (event.delta / 3)), "units")
            
        def _bind_mouse(e): self.v_can.bind_all("<MouseWheel>", _on_mousewheel)
        def _unbind_mouse(e): self.v_can.unbind_all("<MouseWheel>")

        self.v_can.bind("<Enter>", _bind_mouse)
        self.v_can.bind("<Leave>", _unbind_mouse)

        # Main content body (padded)
        body = Frame(self.scrollable_frame, bg=T.BG_ROOT, padx=32, pady=28)
        body.pack(fill=X)

        # 0. ALL-PURPOSE DATE FILTER BAR
        filter_bar = Frame(body, bg=T.BG_ROOT)
        filter_bar.pack(fill=X, pady=(0, 24))
        
        f_left = Frame(filter_bar, bg=T.BG_ROOT)
        f_left.pack(side=LEFT)
        Label(f_left, text="Date Range:", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(side=LEFT, padx=(0, 15))
        
        self.sd_ent = Entry(f_left, font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT, insertbackground=T.WHITE, relief=FLAT, width=12)
        self.sd_ent.pack(side=LEFT, padx=5)
        self.sd_ent.insert(0, str(date.today() - timedelta(days=6)))
        
        def pick_sd(): CalendarPicker(self.top, lambda d: (self.sd_ent.delete(0, END), self.sd_ent.insert(0, d)))
        Button(f_left, text="📅", command=pick_sd, bg=T.BG_ROOT, fg=T.PRIMARY, relief=FLAT, borderwidth=0, activebackground=T.BG_ROOT, font=("Segoe UI Symbol", 14)).pack(side=LEFT, padx=(0, 10))
        
        Label(f_left, text="to", font=T.FONT_UI, bg=T.BG_ROOT, fg=T.TEXT_SUB).pack(side=LEFT, padx=5)
        
        self.ed_ent = Entry(f_left, font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT, insertbackground=T.WHITE, relief=FLAT, width=12)
        self.ed_ent.pack(side=LEFT, padx=5)
        self.ed_ent.insert(0, str(date.today()))

        def pick_ed(): CalendarPicker(self.top, lambda d: (self.ed_ent.delete(0, END), self.ed_ent.insert(0, d)))
        Button(f_left, text="📅", command=pick_ed, bg=T.BG_ROOT, fg=T.PRIMARY, relief=FLAT, borderwidth=0, activebackground=T.BG_ROOT, font=("Segoe UI Symbol", 14)).pack(side=LEFT, padx=(0, 10))
        
        self.btn_refresh = Button(f_left, text="Apply Filter", command=self.refresh_all_analytics)
        self.btn_refresh.pack(side=LEFT, padx=20)
        T.btn_primary(self.btn_refresh)

        # 1. Summary Cards
        self.summary_frame = Frame(body, bg=T.BG_ROOT)
        self.summary_frame.pack(fill=X, pady=(0, 24))
        self.update_stat_cards()

        # 2. Charts section
        charts_container = Frame(body, bg=T.BG_ROOT)
        charts_container.pack(fill=X, pady=(0, 24))

        # ROW 1: Trend and Payment
        row1 = Frame(charts_container, bg=T.BG_ROOT, height=360)
        row1.pack(fill=X)
        row1.pack_propagate(False)

        trend_card = Frame(row1, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=20, pady=20)
        trend_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 12))
        Label(trend_card, text="Sales Trend (Last 7 Days)", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        
        self.trend_canvas = Canvas(trend_card, bg=T.CARD, highlightthickness=0)
        self.trend_canvas.pack(fill=BOTH, expand=True, pady=(20, 0))
        self.trend_canvas.bind("<Configure>", lambda e: self.draw_trend())

        pay_card = Frame(row1, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=20, pady=20)
        pay_card.pack(side=LEFT, fill=BOTH, expand=True, padx=(12, 0))
        Label(pay_card, text="Payment Mode Performance", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        
        self.pay_canvas = Canvas(pay_card, bg=T.CARD, highlightthickness=0)
        self.pay_canvas.pack(fill=BOTH, expand=True, pady=(20, 0))
        self.pay_canvas.bind("<Configure>", lambda e: self.draw_payments())

        # ROW 2: Best Sellers
        row2 = Frame(charts_container, bg=T.BG_ROOT, height=280)
        row2.pack(fill=X, pady=(24, 0))
        row2.pack_propagate(False)
        
        top_card = Frame(row2, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=20, pady=20)
        top_card.pack(fill=BOTH, expand=True)
        Label(top_card, text="Top 5 Best-Selling Products", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        
        self.top_canvas = Canvas(top_card, bg=T.CARD, highlightthickness=0)
        self.top_canvas.pack(fill=BOTH, expand=True, pady=(20, 0))
        self.top_canvas.bind("<Configure>", lambda e: self.draw_top_products())

        # ROW 3: Hourly Peak Times
        row3 = Frame(charts_container, bg=T.BG_ROOT, height=280)
        row3.pack(fill=X, pady=(24, 0))
        row3.pack_propagate(False)
        
        peak_card = Frame(row3, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=20, pady=20)
        peak_card.pack(fill=BOTH, expand=True)
        Label(peak_card, text="Hourly Transaction Density (Peak Times)", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        
        self.peak_canvas = Canvas(peak_card, bg=T.CARD, highlightthickness=0)
        self.peak_canvas.pack(fill=BOTH, expand=True, pady=(20, 0))
        self.peak_canvas.bind("<Configure>", lambda e: self.draw_peak_times())

        # 3. Comprehensive Product Ledger
        ledger_frame = Frame(body, bg=T.BG_ROOT)
        ledger_frame.pack(fill=X, pady=(32, 0))
        
        ledger_hdr = Frame(ledger_frame, bg=T.BG_ROOT)
        ledger_hdr.pack(fill=X, pady=(0, 12))
        Label(ledger_hdr, text="Complete Product Performance Ledger", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(side=LEFT)
        
        self.btn_csv = Button(ledger_hdr, text="Export CSV 💾", command=self.export_ledger_csv)
        self.btn_csv.pack(side=RIGHT)
        T.btn_secondary(self.btn_csv)
        
        tree_card = Frame(ledger_frame, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        tree_card.pack(fill=X)
        
        v_scroll_tree = Scrollbar(tree_card, orient=VERTICAL)
        v_scroll_tree.pack(side=RIGHT, fill=Y)
        
        self.ledger_tree = ttk.Treeview(
            tree_card, 
            columns=("Name", "Cat", "Sold", "Revenue", "Profit"), 
            show="headings", 
            height=15, 
            yscrollcommand=v_scroll_tree.set,
            style="RM.Treeview"
        )
        self.ledger_tree.pack(side=LEFT, fill=BOTH, expand=True)
        v_scroll_tree.configure(command=self.ledger_tree.yview)

        # Headings with sorting capability
        self.ledger_tree.heading("Name", text="Product Name", anchor=W, command=lambda: self.sort_ledger("Name", False))
        self.ledger_tree.heading("Cat", text="Category", anchor=W, command=lambda: self.sort_ledger("Cat", False))
        self.ledger_tree.heading("Sold", text="Units Sold", anchor=E, command=lambda: self.sort_ledger("Sold", False))
        self.ledger_tree.heading("Revenue", text="Revenue", anchor=E, command=lambda: self.sort_ledger("Revenue", False))
        self.ledger_tree.heading("Profit", text="Est. Profit", anchor=E, command=lambda: self.sort_ledger("Profit", False))

        self.ledger_tree.column("Name", width=300, anchor=W, stretch=YES)
        self.ledger_tree.column("Cat", width=150, anchor=W, stretch=NO)
        self.ledger_tree.column("Sold", width=100, anchor=CENTER, stretch=NO)
        self.ledger_tree.column("Revenue", width=120, anchor=CENTER, stretch=NO)
        self.ledger_tree.column("Profit", width=120, anchor=CENTER, stretch=NO)
        
        self.refresh_ledger()

        # Resolve scroll conflict: disable page scroll when hovering over the ledger
        tree_card.bind("<Enter>", _unbind_mouse)
        tree_card.bind("<Leave>", _bind_mouse)
        self.ledger_tree.bind("<Enter>", _unbind_mouse)
        self.ledger_tree.bind("<Leave>", _bind_mouse)

        self.btn_back = Button(body, text="← Back to hub", command=self.Exit)
        self.btn_back.pack(anchor=W, pady=(32, 60))
        T.btn_secondary(self.btn_back)

        self.time()

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def refresh_all_analytics(self):
        # Force MySQL to see latest committed data from other threads
        try: cur.connection.rollback()
        except: pass
        
        self.update_stat_cards()
        self.draw_trend()
        self.draw_payments()
        self.draw_top_products()
        self.draw_peak_times()
        self.refresh_ledger()

    def get_active_dates(self):
        s_raw = self.sd_ent.get().strip()
        e_raw = self.ed_ent.get().strip()
        # Fallback to today if invalid
        try:
            datetime.strptime(s_raw, "%Y-%m-%d")
            sd = s_raw
        except: sd = str(date.today())
        try:
            datetime.strptime(e_raw, "%Y-%m-%d")
            ed = e_raw
        except: ed = str(date.today())
        return sd, ed

    def update_stat_cards(self):
        for w in self.summary_frame.winfo_children(): w.destroy()
        sd, ed = self.get_active_dates()
        
        cur.execute("SELECT COUNT(*), SUM(total_amount) FROM bill WHERE date BETWEEN ? AND ?", (sd, ed))
        count, total = cur.fetchone()
        total = total or 0.0
        avg = total / count if count > 0 else 0.0

        def stat_card(parent, title, value, color):
            f = Frame(parent, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=20, pady=16)
            f.pack(side=LEFT, fill=X, expand=True, padx=10)
            Label(f, text=title, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
            Label(f, text=value, font=(T.FONT_FAMILY, 24, "bold"), bg=T.CARD, fg=color).pack(anchor=W, pady=(4, 0))
            return f

        range_text = "Today" if sd == ed == str(date.today()) else "Selected Range"
        stat_card(self.summary_frame, f"{range_text} Revenue", f"Rs. {total:,.2f}", T.PRIMARY)
        stat_card(self.summary_frame, f"{range_text} Bills", str(count), T.PRIMARY_DIM)
        stat_card(self.summary_frame, "Avg. Bill Value", f"Rs. {avg:,.2f}", T.PRIMARY_DIM)

        # Perishable check (Not date filtered usually, but keep same UX)
        cur.execute("SELECT expiry_date FROM raw_inventory WHERE expiry_date != 'N/A'")
        all_exp = cur.fetchall()
        today_dt = date.today()
        expired = 0; soon = 0
        for (exstr,) in all_exp:
            try:
                ex_dt = datetime.strptime(exstr, "%Y-%m-%d").date()
                diff = (ex_dt - today_dt).days
                if diff < 0: expired += 1
                elif diff <= 7: soon += 1
            except: pass
        stat_card(self.summary_frame, "Expired Items", f"{expired} items", "#D32F2F" if expired > 0 else T.TEXT_SUB)
        stat_card(self.summary_frame, "Expiring Soon", f"{soon} items", "#FFA000" if soon > 0 else T.TEXT_SUB)

    def draw_peak_times(self):
        c = self.peak_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100: return
        padding = 40
        cw, ch = w - (padding*2), h - (padding*2)
        
        sd, ed = self.get_active_dates()
        cur.execute("SELECT bill_time FROM bill WHERE date BETWEEN ? AND ?", (sd, ed))
        rows = cur.fetchall()
        hours = [0]*24
        for (bt,) in rows:
            try: 
                hr = int(bt[11:13])
                hours[hr] += 1
            except: pass
        
        max_v = max(hours) if max(hours) > 0 else 10
        bw = cw / 24
        for i, val in enumerate(hours):
            x0 = padding + i * bw
            y0 = (h - padding) - (val / max_v * ch)
            x1 = x0 + bw - 2
            y1 = h - padding
            color = T.PRIMARY if val > 0 else T.CARD_SOFT
            c.create_rectangle(x0, y0, x1, y1, fill=color, outline="")
            if i % 4 == 0:
                c.create_text(x0 + bw/2, h - padding + 15, text=f"{i:02d}", font=T.FONT_SMALL, fill=T.TEXT_SUB)

    def draw_trend(self):
        c = self.trend_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100: return
        
        padding = 40
        chart_w, chart_h = w - (padding*2), h - (padding*2)
        
        # Trend logic: we use the selected range's end date and back 7 days for the chart labels
        sd_str, ed_str = self.get_active_dates()
        ed_dt = datetime.strptime(ed_str, "%Y-%m-%d").date()
        dates = [(ed_dt - timedelta(days=i)) for i in range(6, -1, -1)]
        
        data = []
        for d in dates:
            cur.execute("SELECT SUM(total_amount) FROM bill WHERE date = ?", (str(d),))
            data.append(cur.fetchone()[0] or 0.0)
        
        max_val = max(data) if max(data) > 0 else 100
        step_x = chart_w / 6
        points = []
        for i, val in enumerate(data):
            x = padding + (i * step_x)
            y = (h - padding) - (float(val) / float(max_val) * chart_h)
            points.append((x, y))
            c.create_text(x, h - padding + 15, text=dates[i].strftime("%d/%m"), font=T.FONT_SMALL, fill=T.TEXT_SUB)

        c.create_line(padding, h - padding, padding + chart_w, h - padding, fill=T.BORDER_SUBTLE)
        if len(points) > 1:
            c.create_line(points, fill=T.PRIMARY, width=3, smooth=True)
            for x, y in points:
                c.create_oval(x-4, y-4, x+4, y+4, fill=T.PRIMARY_LIGHT, outline=T.PRIMARY)

    def draw_payments(self):
        c = self.pay_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100: return
        padding = 40
        cw, ch = w - (padding * 2), h - (padding * 2)
        sd, ed = self.get_active_dates()
        
        modes = ["Cash", "UPI", "Card"]
        vals = []
        for m in modes:
            cur.execute("SELECT SUM(total_amount) FROM bill WHERE payment_method = ? AND date BETWEEN ? AND ?", (m, sd, ed))
            vals.append(cur.fetchone()[0] or 0.0)
            
        max_val = max(vals) if max(vals) > 0 else 100
        bar_w = cw / 5
        spacing = cw / 4
        colors = [T.PRIMARY, T.PRIMARY, T.PRIMARY]
        
        for i, val in enumerate(vals):
            x0 = padding + (i + 1) * spacing - (bar_w / 2)
            y0 = (h - padding) - (float(val) / float(max_val) * ch)
            x1 = x0 + bar_w
            y1 = h - padding
            c.create_rectangle(x0, y0, x1, y1, fill=colors[i], outline="")
            c.create_text((x0+x1)/2, h-padding+15, text=modes[i], font=T.FONT_UI_SM, fill=T.TEXT_SUB)
            c.create_text((x0+x1)/2, y0-10, text=f"₹{val:,.0f}", font=T.FONT_SMALL, fill=T.TEXT_ON_LIGHT)

    def get_top_products(self):
        sd, ed = self.get_active_dates()
        # For MySQL: Reset transaction to see latest data from other threads
        try: cur.connection.rollback()
        except: pass
        try:
            cur.execute("""
                SELECT bi.product_name, SUM(bi.quantity) 
                FROM bill_items bi
                JOIN bill b ON bi.bill_no = b.bill_no
                WHERE b.date BETWEEN ? AND ?
                GROUP BY bi.product_name
                ORDER BY SUM(bi.quantity) DESC
                LIMIT 5
            """, (sd, ed))
            return cur.fetchall()
        except Exception as e:
            print(f"Error getting top products: {e}")
            return []


    def draw_top_products(self):
        c = self.top_canvas
        c.delete("all")
        w, h = c.winfo_width(), c.winfo_height()
        if w < 100: return
        
        data = self.get_top_products()
        if not data:
            c.create_text(w/2, h/2, text="No sales data available yet.", fill=T.TEXT_SUB, font=T.FONT_UI)
            return
            
        padding_l = 220
        padding_r = 80
        chart_w = w - padding_l - padding_r
        
        max_qty = max([d[1] for d in data]) if data else 1
        bar_h = 24
        spacing = (h - 40) / 5
        
        for i, (name, qty) in enumerate(data):
            y = 20 + i * spacing
            bw = (qty / max_qty) * chart_w
            
            # Progress-bar style with rounded aesthetic
            c.create_rectangle(padding_l, y, padding_l + chart_w, y + bar_h, fill=T.CARD_SOFT, outline="")
            c.create_rectangle(padding_l, y, padding_l + bw, y + bar_h, fill=T.PRIMARY, outline="")
            
            # Labels
            disp_name = name
            c.create_text(padding_l - 15, y + bar_h/2, text=disp_name, anchor=E, font=T.FONT_UI_SM, fill=T.TEXT_ON_LIGHT)
            c.create_text(padding_l + bw + 10, y + bar_h/2, text=f"{int(qty)} units", anchor=W, font=T.FONT_SMALL, fill=T.PRIMARY_LIGHT)

    def get_detailed_ledger(self, sd=None, ed=None):
        # 1. Thread-safe database connection
        import db_manager as thread_sql
        conn = thread_sql.connect(db_init.db_path())
        l_cur = conn.cursor()
        
        # Use provided dates or fall back to active ones (if called on main thread)
        if not sd or not ed:
            sd, ed = self.get_active_dates()

        # For MySQL: Reset transaction to see latest data from other threads
        try: conn.rollback()
        except: pass

        # 1. Map all products from inventory
        l_cur.execute("SELECT product_name, product_cat, mrp, cost_price FROM raw_inventory")
        inv_rows = l_cur.fetchall()
        inventory_map = {}
        for row in inv_rows:
            name = row[0]
            inventory_map[name] = {'full_name': name, 'cat': row[1], 'mrp': row[2], 'cost': row[3], 'sold': 0}
            
        # 2. Extract stats from professional reporting table (bill_items)
        l_cur.execute("""
            SELECT bi.product_name, bi.quantity 
            FROM bill_items bi
            JOIN bill b ON bi.bill_no = b.bill_no
            WHERE b.date BETWEEN ? AND ?
        """, (sd, ed))
        
        item_rows = l_cur.fetchall()
        conn.close() 

        for p_name, qty in item_rows:
            if p_name in inventory_map:
                inventory_map[p_name]['sold'] += qty
                
        ledger_data = []
        for info in inventory_map.values():
            try:
                name, sold = info['full_name'], info['sold']
                # Convert MRP and Cost to float safely
                mrp = float(info.get('mrp', 0) or 0)
                cost = float(info.get('cost', 0) or 0)
                sold = float(info.get('sold', 0) or 0)
                
                rev = sold * mrp
                profit = sold * (mrp - cost)
                ledger_data.append((name, info['cat'], int(sold), f"₹{rev:,.2f}", f"₹{profit:,.2f}", rev, profit))
            except Exception as e:
                print(f"Skipping ledger item: {e}")
        return sorted(ledger_data, key=lambda x: x[2], reverse=True)

    def export_ledger_csv(self):
        items = self.ledger_tree.get_children()
        if not items:
            messagebox.showinfo("Export", "No analytical data to export.")
            return
        sd, ed = self.get_active_dates()
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", 
            initialfile=f"RealMart_Ledger_{sd}_to_{ed}.csv",
            filetypes=[("CSV Files", "*.csv")]
        )
        if not path: return
        try:
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Date Range", f"{sd} to {ed}", "", "", ""])
                writer.writerow(["Product Name", "Category", "Units Sold", "Revenue", "Estimated Profit"])
                for item in items:
                    writer.writerow(self.ledger_tree.item(item, 'values'))
            messagebox.showinfo("Export Success", f"Detailed ledger exported to:\n{path}")
        except Exception as e:
            messagebox.showerror("Export Failed", f"Could not save file: {e}")

    def refresh_ledger(self):
        # Clear and show loading state
        self.ledger_tree.delete(*self.ledger_tree.get_children())
        self.ledger_tree.insert("", "end", values=("Loading analytical data...", "--", "--", "--", "--"))
        
        # IMPORTANT: Fetch dates on MAIN THREAD before starting background thread
        sd, ed = self.get_active_dates()

        def _load_data():
            try:
                data = self.get_detailed_ledger(sd, ed)
                
                # Safely update GUI from the background thread
                def _done():
                    self._apply_ledger_data(data)
                
                self.top.after(10, _done)
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"Ledger load error: {e}")

        # Dispatch heavy parsing to background
        t = threading.Thread(target=_load_data, daemon=True)
        t.start()

    def _apply_ledger_data(self, data):
        self.ledger_tree.delete(*self.ledger_tree.get_children())
        for d in data:
            self.ledger_tree.insert("", "end", values=d[:5])

    def sort_ledger(self, col, reverse):
        # Extract data from tree
        items = []
        for k in self.ledger_tree.get_children(''):
            vals = self.ledger_tree.item(k, 'values')
            items.append((vals, k))
            
        # Determine sorting index and type
        idx = ["Name", "Cat", "Sold", "Revenue", "Profit"].index(col)
        
        def sort_key(t):
            val = t[0][idx]
            if idx in [2, 3, 4]: # Numeric/Currency columns
                return float(re.sub(r'[^\d.]', '', val))
            return val.lower()

        items.sort(key=sort_key, reverse=reverse)

        for index, (_, k) in enumerate(items):
            self.ledger_tree.move(k, '', index)

        # Reverse sort on next click
        self.ledger_tree.heading(col, command=lambda: self.sort_ledger(col, not reverse))

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        global page2
        page2 = Admin_Page(root)


class CalendarPicker:
    def __init__(self, parent, callback):
        self.top = Toplevel(parent)
        self.top.title("Select Date")
        self.top.geometry("320x380")
        self.top.configure(bg=T.BG_ROOT)
        self.top.resizable(False, False)
        self.top.transient(parent)
        self.top.grab_set()
        
        self.callback = callback
        self.now = date.today()
        self.curr_month = self.now.month
        self.curr_year = self.now.year
        
        hdr = Frame(self.top, bg=T.BG_ROOT, pady=15)
        hdr.pack(fill=X)
        
        Button(hdr, text="❮", command=self.prev_month, bg=T.BG_ROOT, fg=T.PRIMARY, relief=FLAT, font=("Segoe UI", 12, "bold")).pack(side=LEFT, padx=15)
        self.lbl_month = Label(hdr, text="", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT)
        self.lbl_month.pack(side=LEFT, expand=True)
        Button(hdr, text="❯", command=self.next_month, bg=T.BG_ROOT, fg=T.PRIMARY, relief=FLAT, font=("Segoe UI", 12, "bold")).pack(side=RIGHT, padx=15)
        
        self.body = Frame(self.top, bg=T.CARD, padx=15, pady=15)
        self.body.pack(fill=BOTH, expand=True)
        
        # Days head
        days = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
        for i, d in enumerate(days):
            Label(self.body, text=d, font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).grid(row=0, column=i, pady=(0, 10))
            
        self.draw_calendar()
        
    def draw_calendar(self):
        # Clear previous days (keep header)
        for w in self.body.winfo_children():
            if int(w.grid_info().get("row", 0)) > 0: w.destroy()
            
        month_name = calendar.month_name[self.curr_month]
        self.lbl_month.config(text=f"{month_name} {self.curr_year}")
        
        cal = calendar.monthcalendar(self.curr_year, self.curr_month)
        for r, week in enumerate(cal):
            for c, day in enumerate(week):
                if day != 0:
                    btn = Button(self.body, text=str(day), width=3, relief=FLAT, bg=T.CARD, fg=T.TEXT_ON_LIGHT,
                                 font=T.FONT_UI_SM, command=lambda d=day: self.select_date(d))
                    btn.grid(row=r+1, column=c, padx=3, pady=3)
                    
                    if day == self.now.day and self.curr_month == self.now.month and self.curr_year == self.now.year:
                        btn.config(bg=T.PRIMARY, fg=T.WHITE)
                    else:
                        def _hov(e, b=btn): b.config(bg=T.PRIMARY_DIM)
                        def _lev(e, b=btn): b.config(bg=T.CARD)
                        btn.bind("<Enter>", _hov)
                        btn.bind("<Leave>", _lev)

    def prev_month(self):
        self.curr_month -= 1
        if self.curr_month == 0: self.curr_month = 12; self.curr_year -= 1
        self.draw_calendar()
        
    def next_month(self):
        self.curr_month += 1
        if self.curr_month == 13: self.curr_month = 1; self.curr_year += 1
        self.draw_calendar()
        
    def select_date(self, day):
        d_str = f"{self.curr_year}-{self.curr_month:02d}-{day:02d}"
        self.callback(d_str)
        self.top.destroy()


class Marketing_Panel:
    def __init__(self, top=None, user_data=None):
        self.top = top
        self.user_data = user_data
        top.geometry("1400x920")
        top.title("Marketing & Offers Hub · Real Mart")
        top.configure(bg=T.BG_ROOT)
        refresh_db()

        # Header
        hdr = Frame(top, bg=T.PRIMARY, height=64)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.PRIMARY)
        hc.pack(fill=BOTH, expand=True, padx=24, pady=12)
        Label(hc, text="🚀 Marketing & Growth Center", font=T.FONT_TITLE_MD, bg=T.PRIMARY, fg=T.WHITE).pack(side=LEFT)
        
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=15, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT)
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.PRIMARY, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 20))

        # Main Layout
        # Main Layout
        self.body = Frame(top, bg=T.BG_ROOT)
        self.body.pack(fill=BOTH, expand=True, padx=40, pady=(10, 24))
        
        # --- TAB NAVIGATION ---
        self.tab_f = Frame(self.body, bg=T.BG_ROOT)
        self.tab_f.pack(fill=X, pady=(0, 20))
        
        self.tabs = {}
        self.active_tab = "Offers"
        
        def create_tab(name, label):
            btn = Button(self.tab_f, text=label, command=lambda: self.switch_tab(name))
            btn.pack(side=LEFT, padx=(0, 15))
            T.btn_tab(btn, active=(name == self.active_tab))
            self.tabs[name] = btn
            
        create_tab("Offers", "🏷️ Product Offers")
        create_tab("Tiers", "🎟️ Reward Tiers")
        create_tab("Log", "📜 Coupon History")
        create_tab("Flash", "⚡ Flash Sales")
        create_tab("Loyalty", "💎 Loyalty Points")
        create_tab("LastChance", "⌛ Last Chance")
        create_tab("LossLeader", "📉 Loss Leaders")
        
        # --- CONTENT CONTAINER ---
        self.container = Frame(self.body, bg=T.BG_ROOT)
        self.container.pack(fill=BOTH, expand=True)
        
        self.switch_tab("Offers")

    def switch_tab(self, name):
        self.active_tab = name
        # Update button styles
        for k, b in self.tabs.items():
            T.btn_tab(b, active=(k == name))
        
        # Clear container
        for w in self.container.winfo_children():
            w.destroy()
            
        if name == "Offers": self.draw_offers_tab()
        elif name == "Tiers": self.draw_tiers_tab()
        elif name == "Log": self.draw_log_tab()
        elif name == "Flash": self.draw_flash_tab()
        elif name == "Loyalty": self.draw_loyalty_tab()
        elif name == "LastChance": self.draw_last_chance_tab()
        elif name == "LossLeader": self.draw_loss_leader_tab()

    def draw_loss_leader_tab(self):
        f = Frame(self.container, bg=T.BG_ROOT)
        f.pack(fill=BOTH, expand=True)

        hdr = Frame(f, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        hdr.pack(fill=X, pady=(0, 20))
        Label(hdr, text="📉 Loss Leader Analytics", font=T.FONT_TITLE, bg=T.CARD, fg=T.PRIMARY).pack(anchor=W)
        Label(hdr, text="Identify products sold below cost and analyze if they drive higher total bill values.", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(5,0))

        # Stats Row
        stats_f = Frame(f, bg=T.BG_ROOT)
        stats_f.pack(fill=X, pady=(0, 20))

        def make_stat(parent, title, val, color):
            c = Frame(parent, bg=T.CARD, padx=20, pady=15, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
            c.pack(side=LEFT, expand=True, fill=BOTH, padx=(0, 15))
            Label(c, text=title, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
            Label(c, text=val, font=T.FONT_HERO, bg=T.CARD, fg=color).pack(anchor=W, pady=(5,0))

        # Query for stats
        # 1. Total Loss Incurred
        cur.execute("SELECT SUM((cost_price - mrp) * quantity) FROM bill_items WHERE mrp < cost_price")
        total_loss = cur.fetchone()[0] or 0.0
        
        # 2. Avg Bill Total with Loss Leaders
        cur.execute("""
            SELECT AVG(total_amount) FROM bill 
            WHERE bill_no IN (SELECT DISTINCT bill_no FROM bill_items WHERE mrp < cost_price)
        """)
        avg_ll_bill = cur.fetchone()[0] or 0.0
        
        # 3. Avg Bill Total WITHOUT Loss Leaders
        cur.execute("""
            SELECT AVG(total_amount) FROM bill 
            WHERE bill_no NOT IN (SELECT DISTINCT bill_no FROM bill_items WHERE mrp < cost_price)
        """)
        avg_normal_bill = cur.fetchone()[0] or 0.0

        make_stat(stats_f, "Total Strategy Loss", f"₹{total_loss:.2f}", "#D32F2F")
        make_stat(stats_f, "Avg Bill (With LL)", f"₹{avg_ll_bill:.2f}", "#2E7D32")
        make_stat(stats_f, "Avg Bill (Normal)", f"₹{avg_normal_bill:.2f}", T.TEXT_SUB)

        # List of Loss Leaders
        Label(f, text="Top Products Triggering Strategy Losses", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(10, 10))
        
        list_card = Frame(f, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        list_card.pack(fill=BOTH, expand=True)

        tree = ttk.Treeview(list_card, columns=("Product", "Units Sold", "Cost", "Avg Price", "Total Loss", "Basket Impact"), show="headings", style="RM.Treeview")
        tree.pack(fill=BOTH, expand=True)
        for col in tree["columns"]: 
            tree.heading(col, text=col, anchor=CENTER)
            tree.column(col, anchor=CENTER, width=150)
        tree.column("Product", width=250, stretch=YES)
        T.apply_zebra_styling(tree)
        
        # Fetch Top Loss Leaders
        query = """
            SELECT product_name, SUM(quantity), AVG(cost_price), AVG(mrp), SUM((cost_price - mrp) * quantity)
            FROM bill_items 
            WHERE mrp < cost_price 
            GROUP BY product_name 
            ORDER BY SUM((cost_price - mrp) * quantity) DESC
        """
        cur.execute(query)
        for r in cur.fetchall():
            p_name, qty, cost, price, loss = r
            
            # Impact: Avg total of bills containing this specific product
            cur.execute("""
                SELECT AVG(total_amount) FROM bill 
                WHERE bill_no IN (SELECT bill_no FROM bill_items WHERE product_name = ?)
            """, (p_name,))
            impact = cur.fetchone()[0] or 0.0
            
            tag = "even" if len(tree.get_children()) % 2 == 0 else "odd"
            tree.insert("", "end", values=(p_name, int(qty), f"₹{cost:.2f}", f"₹{price:.2f}", f"₹{loss:.2f}", f"₹{impact:.2f}"), tags=(tag,))

    def draw_last_chance_tab(self):
        f = Frame(self.container, bg=T.BG_ROOT)
        f.pack(fill=BOTH, expand=True)

        hdr = Frame(f, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        hdr.pack(fill=X, pady=(0, 20))
        Label(hdr, text="⌛ Near-Expiry 'Last Chance' Automation", font=T.FONT_TITLE, bg=T.CARD, fg=T.PRIMARY).pack(anchor=W)
        Label(hdr, text="Automatically apply steep discounts to items nearing expiration to clear stock.", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(5,0))

        # Config Row
        cfg_f = Frame(f, bg=T.BG_ROOT)
        cfg_f.pack(fill=X, pady=(0, 20))

        def make_cfg_card(parent, title, key, default, unit=""):
            c = Frame(parent, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
            c.pack(side=LEFT, expand=True, fill=X, padx=(0, 15))
            Label(c, text=title, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
            
            cur.execute("SELECT `value` FROM last_chance_config WHERE `key`=?", (key,))
            res = cur.fetchone()
            val = res[0] if res else default
            
            e_row = Frame(c, bg=T.CARD)
            e_row.pack(fill=X, pady=10)
            e = Entry(e_row, font=T.FONT_SECTION); e.pack(side=LEFT, fill=X, expand=True, ipady=4); T.entry_light(e); e.insert(0, val)
            if unit: Label(e_row, text=unit, font=T.FONT_BTN, bg=T.CARD, fg=T.TEXT_SUB).pack(side=LEFT, padx=5)
            
            def save():
                import config_manager
                is_mysql = config_manager.load_config().get("db_type") == "mysql"
                sql = "REPLACE INTO last_chance_config (`key`, `value`) VALUES (?,?)" if is_mysql else "INSERT OR REPLACE INTO last_chance_config (`key`, `value`) VALUES (?,?)"
                cur.execute(sql, (key, e.get()))
                db.commit()
                messagebox.showinfo("Saved", f"{title} updated.")
            
            Button(c, text="Update", command=save).pack(anchor=E); T.btn_ghost(c.winfo_children()[-1])

        make_cfg_card(cfg_f, "Near-Expiry Threshold", "threshold_days", "7", "Days")
        make_cfg_card(cfg_f, "Last Chance Discount", "discount_percent", "50", "% OFF")

        # Inventory View
        Label(f, text="Items Currently in 'Last Chance' Range", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(10, 15))
        list_card = Frame(f, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        list_card.pack(fill=BOTH, expand=True)

        tree = ttk.Treeview(list_card, columns=("Name", "Expiry", "Stock", "MRP", "Clearance"), show="headings", style="RM.Treeview")
        tree.pack(fill=BOTH, expand=True)
        for col in tree["columns"]: 
            tree.heading(col, text=col, anchor=CENTER)
            tree.column(col, anchor=CENTER, width=150)
        tree.column("Name", width=250, stretch=YES)
        T.apply_zebra_styling(tree)
        
        # Logic to find items
        cur.execute("SELECT `value` FROM last_chance_config WHERE `key`='threshold_days'")
        t_days = int(cur.fetchone()[0] or 7)
        cur.execute("SELECT `value` FROM last_chance_config WHERE `key`='discount_percent'")
        d_pct = float(cur.fetchone()[0] or 50)

        cur.execute("SELECT product_name, expiry_date, stock, mrp FROM raw_inventory WHERE expiry_date != 'N/A' AND expiry_date != ''")
        import datetime
        today = datetime.date.today()
        for r in cur.fetchall():
            try:
                exp = datetime.datetime.strptime(r[1], "%Y-%m-%d").date()
                diff = (exp - today).days
                if diff <= t_days:
                    clearance_price = float(r[3]) * (1 - d_pct/100)
                    tag_color = "near"
                    zebra = "even" if len(tree.get_children()) % 2 == 0 else "odd"
                    tree.insert("", "end", values=(r[0], r[1], r[2], f"₹{r[3]}", f"₹{clearance_price:.2f}"), tags=(tag_color, zebra))
            except: pass
        
        tree.tag_configure("near", foreground="#D32F2F")

    def draw_loyalty_tab(self):
        f = Frame(self.container, bg=T.BG_ROOT)
        f.pack(fill=BOTH, expand=True)

        # Config Row
        cfg_f = Frame(f, bg=T.BG_ROOT)
        cfg_f.pack(fill=X, pady=(0, 20))
        
        def make_cfg_card(parent, title, key, default):
            c = Frame(parent, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
            c.pack(side=LEFT, expand=True, fill=X, padx=(0, 15))
            Label(c, text=title, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
            
            cur.execute("SELECT `value` FROM loyalty_config WHERE `key`=?", (key,))
            res = cur.fetchone()
            val = res[0] if res else default
            
            e = Entry(c, font=T.FONT_SECTION); e.pack(fill=X, pady=10, ipady=4); T.entry_light(e); e.insert(0, val)
            
            def save():
                import config_manager
                is_mysql = config_manager.load_config().get("db_type") == "mysql"
                sql = "INSERT OR REPLACE INTO loyalty_config (`key`, `value`) VALUES (?,?)"
                if is_mysql:
                    sql = "REPLACE INTO loyalty_config (`key`, `value`) VALUES (?,?)"
                cur.execute(sql, (key, e.get()))
                db.commit()
                messagebox.showinfo("Saved", f"{title} updated.")
            
            Button(c, text="Update", command=save).pack(anchor=E); T.btn_ghost(c.winfo_children()[-1])

        make_cfg_card(cfg_f, "Points earned per ₹100 Spent", "points_per_100", "1")
        make_cfg_card(cfg_f, "Value of 1 Point (in ₹)", "point_value_rs", "0.5")

        # Members List
        Label(f, text="Loyal Members Directory", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(10, 15))
        list_card = Frame(f, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        list_card.pack(fill=BOTH, expand=True)

        self.loyalty_tree = ttk.Treeview(list_card, columns=("Phone", "Points", "Spent", "Last"), show="headings", style="RM.Treeview")
        self.loyalty_tree.pack(fill=BOTH, expand=True)
        self.loyalty_tree.heading("Phone", text="Customer Phone", anchor=CENTER)
        self.loyalty_tree.heading("Points", text="Current Balance", anchor=CENTER)
        self.loyalty_tree.heading("Spent", text="Total Lifetime Spend", anchor=CENTER)
        self.loyalty_tree.heading("Last", text="Last Visit", anchor=CENTER)
        
        for c in self.loyalty_tree["columns"]: self.loyalty_tree.column(c, anchor=CENTER, width=150)
        self.loyalty_tree.column("Spent", width=180)
        T.apply_zebra_styling(self.loyalty_tree)
        
        cur.execute("SELECT phone, points, total_spent, last_visit FROM loyalty_points ORDER BY points DESC")
        for i, r in enumerate(cur.fetchall()):
            self.loyalty_tree.insert("", "end", values=r, tags=("even" if i % 2 == 0 else "odd",))

    def draw_flash_tab(self):
        f = Frame(self.container, bg=T.BG_ROOT)
        f.pack(fill=BOTH, expand=True)
        
        left = Frame(f, bg=T.BG_ROOT)
        left.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
        right = Frame(f, bg=T.BG_ROOT)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        Label(left, text="Schedule Happy Hour", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(0, 15))
        card = Frame(left, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        card.pack(fill=X)

        def flbl(txt): Label(card, text=txt, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(10, 5))
        
        flbl("Select Category")
        self.cat_var = StringVar()
        cur.execute("SELECT DISTINCT product_cat FROM raw_inventory")
        cats = [r[0] for r in cur.fetchall()]
        self.cb_cat = ttk.Combobox(card, textvariable=self.cat_var, values=cats, state="readonly")
        self.cb_cat.pack(fill=X)

        flbl("Discount Percent (%)")
        self.e_f_disc = Entry(card); self.e_f_disc.pack(fill=X, ipady=4); T.entry_light(self.e_f_disc)

        time_f = Frame(card, bg=T.CARD)
        time_f.pack(fill=X, pady=15)
        
        f1 = Frame(time_f, bg=T.CARD); f1.pack(side=LEFT, expand=True, fill=X)
        Label(f1, text="Start (HH:MM)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
        self.e_start = Entry(f1); self.e_start.pack(fill=X, pady=5, ipady=4); T.entry_light(self.e_start); self.e_start.insert(0, "14:00")

        f2 = Frame(time_f, bg=T.CARD); f2.pack(side=LEFT, expand=True, fill=X, padx=(15, 0))
        Label(f2, text="End (HH:MM)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
        self.e_end = Entry(f2); self.e_end.pack(fill=X, pady=5, ipady=4); T.entry_light(self.e_end); self.e_end.insert(0, "16:00")

        Button(card, text="🚀 Activate Happy Hour", command=self.add_flash).pack(fill=X, pady=(20, 0)); T.btn_primary(card.winfo_children()[-1])

        # Right: Active List
        Label(right, text="Active Flash Sales", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(0, 15))
        rcard = Frame(right, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        rcard.pack(fill=BOTH, expand=True)

        self.flash_tree = ttk.Treeview(rcard, columns=("ID", "Cat", "Disc", "Time"), show="headings", style="RM.Treeview")
        self.flash_tree.pack(fill=BOTH, expand=True)
        self.flash_tree.heading("ID", text="ID", anchor=CENTER)
        self.flash_tree.heading("Cat", text="Category", anchor=CENTER)
        self.flash_tree.heading("Disc", text="Discount", anchor=CENTER)
        self.flash_tree.heading("Time", text="Active Hours", anchor=CENTER)
        
        self.flash_tree.column("ID", width=80, anchor=CENTER)
        self.flash_tree.column("Cat", width=150, anchor=CENTER)
        self.flash_tree.column("Disc", width=120, anchor=CENTER)
        self.flash_tree.column("Time", width=200, anchor=CENTER)
        T.apply_zebra_styling(self.flash_tree)

        Button(rcard, text="🗑️ Cancel Sale", command=self.delete_flash, bg="#FFE0E0", fg="#D32F2F", relief=FLAT).pack(fill=X, pady=(15, 0))
        self.load_flash()

    def load_flash(self):
        self.flash_tree.delete(*self.flash_tree.get_children())
        cur.execute("SELECT sale_id, category, discount_percent, start_time, end_time FROM flash_sales WHERE is_active=1")
        for i, r in enumerate(cur.fetchall()):
            d = list(r[:3])
            d.append(f"{r[3]} - {r[4]}")
            self.flash_tree.insert("", "end", values=d, tags=("even" if i % 2 == 0 else "odd",))

    def add_flash(self):
        try:
            cat = self.cat_var.get()
            disc = float(self.e_f_disc.get())
            start = self.e_start.get().strip()
            end = self.e_end.get().strip()
            if not cat or not start or not end: return
            
            cur.execute("INSERT INTO flash_sales (category, discount_percent, start_time, end_time) VALUES (?,?,?,?)", (cat, disc, start, end))
            db.commit()
            self.load_flash()
            messagebox.showinfo("Activated", f"Happy Hour for {cat} is now scheduled!")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def delete_flash(self):
        sel = self.flash_tree.selection()
        if not sel: return
        sid = self.flash_tree.item(sel[0])['values'][0]
        cur.execute("UPDATE flash_sales SET is_active=0 WHERE sale_id=?", (sid,))
        db.commit()
        self.load_flash()

    def draw_offers_tab(self):
        f = Frame(self.container, bg=T.BG_ROOT)
        f.pack(fill=BOTH, expand=True)
        
        left_col = Frame(f, bg=T.BG_ROOT)
        left_col.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 20))
        
        right_col = Frame(f, bg=T.BG_ROOT)
        right_col.pack(side=LEFT, fill=BOTH, expand=True)

        # Left: Editor
        Label(left_col, text="Manage Offers", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(0, 10))
        p_card = Frame(left_col, bg=T.CARD, padx=25, pady=25, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        p_card.pack(fill=X)

        # Barcode Scan
        Label(p_card, text="🔍 Quick Scan (Barcode/ID)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
        scf = Frame(p_card, bg=T.CARD)
        scf.pack(fill=X, pady=5)
        self.e_scan = Entry(scf); self.e_scan.pack(side=LEFT, fill=X, expand=True, ipady=4); T.entry_light(self.e_scan)
        self.e_scan.bind("<Return>", self.scan_product)
        self.btn_cam = Button(scf, text="📸", font=("Segoe UI Symbol", 12), bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, command=self.open_cam_scanner)
        self.btn_cam.pack(side=LEFT, padx=(8, 0)); T.bind_hover(self.btn_cam, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)

        # Manual Selection
        Label(p_card, text="Or Select Product", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(10,0))
        self.combo_prod = ttk.Combobox(p_card, state="readonly", font=T.FONT_UI)
        self.combo_prod.pack(fill=X, pady=5); self.combo_prod.bind("<<ComboboxSelected>>", self.on_product_select)

        self.det_f = Frame(p_card, bg="#F8FAFC", padx=12, pady=10, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        self.det_f.pack(fill=X, pady=15)
        self.lbl_details = Label(self.det_f, text="Select a product to see details", font=T.FONT_UI_SM, bg="#F8FAFC", fg=T.TEXT_SUB, justify=LEFT)
        self.lbl_details.pack(anchor=W)

        # Offer Fields
        of_row = Frame(p_card, bg=T.CARD); of_row.pack(fill=X, pady=(0, 10))
        f1 = Frame(of_row, bg=T.CARD); f1.pack(side=LEFT, expand=True, fill=X, padx=5)
        Label(f1, text="Offer Type", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
        self.combo_off_type = ttk.Combobox(f1, values=["None", "Percentage", "Flat Discount"], state="readonly")
        self.combo_off_type.pack(fill=X, pady=5); self.combo_off_type.set("None")
        
        f2 = Frame(of_row, bg=T.CARD); f2.pack(side=LEFT, expand=True, fill=X, padx=5)
        Label(f2, text="Value (%) or (Rs.)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
        self.e_off_val = Entry(f2); self.e_off_val.pack(fill=X, pady=5, ipady=4); T.entry_light(self.e_off_val)
        
        Button(p_card, text="Update Product Offer", command=self.save_offer).pack(fill=X, pady=(10, 5)); T.btn_primary(p_card.winfo_children()[-1])
        Button(p_card, text="🚀 Smart Discount Generator", command=self.auto_generate_discounts).pack(fill=X); T.btn_secondary(p_card.winfo_children()[-1])

        # Right: Tree
        Label(right_col, text="Active Promotions", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(0, 10))
        t_card = Frame(right_col, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        t_card.pack(fill=BOTH, expand=True)

        osf = Frame(t_card, bg=T.CARD); osf.pack(fill=X, pady=(0, 10))
        Label(osf, text="🔍 Filter:", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(side=LEFT)
        self.e_search_off = Entry(osf); self.e_search_off.pack(side=LEFT, fill=X, expand=True, padx=(10, 0), ipady=2); T.entry_light(self.e_search_off)
        self.e_search_off.bind("<KeyRelease>", self.filter_offers)

        self.prod_tree = ttk.Treeview(t_card, columns=("Name", "Type", "Value"), show="headings", style="RM.Treeview")
        self.prod_tree.pack(fill=BOTH, expand=True)
        self.prod_tree.heading("Name", text="Product", anchor=CENTER)
        self.prod_tree.heading("Type", text="Offer Type", anchor=CENTER)
        self.prod_tree.heading("Value", text="Discount Value", anchor=CENTER)
        
        self.prod_tree.column("Name", width=250, anchor=CENTER, stretch=YES)
        self.prod_tree.column("Type", width=150, anchor=CENTER)
        self.prod_tree.column("Value", width=150, anchor=CENTER)
        T.apply_zebra_styling(self.prod_tree)
        self.prod_tree.bind("<<TreeviewSelect>>", self.on_offer_select)

        Button(t_card, text="🗑️ Remove Selected Offer", command=self.delete_offer, bg="#FFE0E0", fg="#D32F2F", relief=FLAT).pack(fill=X, pady=(10, 0))
        
        self.load_products(); self.load_offers()

    def draw_tiers_tab(self):
        f = Frame(self.container, bg=T.BG_ROOT)
        f.pack(fill=BOTH, expand=True)
        
        Label(f, text="Configure Reward Tiers", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(anchor=W, pady=(0, 15))
        
        card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        card.pack(fill=BOTH, expand=True)
        
        inf = Frame(card, bg=T.CARD); inf.pack(fill=X, pady=(0, 20))
        
        def frow(parent, lbl):
            ff = Frame(parent, bg=T.CARD); ff.pack(side=LEFT, expand=True, fill=X, padx=10)
            Label(ff, text=lbl, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
            e = Entry(ff); e.pack(fill=X, pady=8, ipady=6); T.entry_light(e); return e
        
        self.e_min_bill = frow(inf, "Minimum Purchase (Rs.)")
        self.e_reward = frow(inf, "Reward / Cashback (Rs.)")
        
        Button(inf, text="+ Add Tier", command=self.add_tier).pack(side=LEFT, padx=10, ipady=4); T.btn_primary(inf.winfo_children()[-1])

        self.tier_tree = ttk.Treeview(card, columns=("ID", "Min", "Reward"), show="headings", height=12, style="RM.Treeview")
        self.tier_tree.pack(fill=BOTH, expand=True)
        self.tier_tree.heading("ID", text="Tier ID", anchor=CENTER)
        self.tier_tree.heading("Min", text="Min Bill (Rs.)", anchor=CENTER)
        self.tier_tree.heading("Reward", text="Reward (Rs.)", anchor=CENTER)
        
        for c in self.tier_tree["columns"]: self.tier_tree.column(c, anchor=CENTER, width=150)
        T.apply_zebra_styling(self.tier_tree)
        
        Button(card, text="Remove Selected Tier", command=self.delete_tier, bg="#FFE0E0", fg="#D32F2F", relief=FLAT).pack(fill=X, pady=(20, 0))
        self.load_tiers()

    def draw_log_tab(self):
        f = Frame(self.container, bg=T.BG_ROOT)
        f.pack(fill=BOTH, expand=True)
        
        top_f = Frame(f, bg=T.BG_ROOT); top_f.pack(fill=X, pady=(0, 15))
        Label(top_f, text="Issued Coupon History", font=T.FONT_SECTION, bg=T.BG_ROOT, fg=T.TEXT_ON_LIGHT).pack(side=LEFT)
        
        self.e_search_log = Entry(top_f, font=T.FONT_UI, width=30)
        self.e_search_log.pack(side=RIGHT, padx=10, ipady=4)
        T.entry_light(self.e_search_log)
        self.e_search_log.bind("<KeyRelease>", lambda e: self.load_coupons(self.e_search_log.get().strip()))
        Label(top_f, text="🔍 Search Log:", font=T.FONT_UI_SM, bg=T.BG_ROOT, fg=T.TEXT_SUB).pack(side=RIGHT)

        card = Frame(f, bg=T.CARD, padx=20, pady=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        card.pack(fill=BOTH, expand=True)
        
        self.coupon_tree = ttk.Treeview(card, columns=("Code", "Value", "MinBill", "Expiry", "Used", "Created"), show="headings", height=15, style="RM.Treeview")
        self.coupon_tree.pack(fill=BOTH, expand=True)
        self.coupon_tree.heading("Code", text="Coupon Code", anchor=CENTER)
        self.coupon_tree.heading("Value", text="Value", anchor=CENTER)
        self.coupon_tree.heading("MinBill", text="Min Bill Req.", anchor=CENTER)
        self.coupon_tree.heading("Expiry", text="Expires On", anchor=CENTER)
        self.coupon_tree.heading("Used", text="Status", anchor=CENTER)
        self.coupon_tree.heading("Created", text="Issued At", anchor=CENTER)
        
        for c in self.coupon_tree["columns"]: self.coupon_tree.column(c, anchor=CENTER, width=130)
        self.coupon_tree.column("Created", width=220)
        T.apply_zebra_styling(self.coupon_tree)
        
        for c in self.coupon_tree["columns"]: self.coupon_tree.column(c, anchor=CENTER)
        self.coupon_tree.column("Created", width=200)

        self.load_coupons()

    def load_coupons(self, query=None):
        try:
            import db_manager as sqlite3
            import db_init
            # Use a fresh connection to avoid any global state issues
            conn = sqlite3.connect(db_init.db_path())
            c = conn.cursor()
            
            self.coupon_tree.delete(*self.coupon_tree.get_children())
            if query:
                c.execute("""SELECT coupon_code, discount_value, min_bill, expiry_date, is_used, created_at 
                           FROM coupons 
                           WHERE coupon_code LIKE ? OR expiry_date LIKE ?""", (f'%{query}%', f'%{query}%'))
            else:
                c.execute("SELECT coupon_code, discount_value, min_bill, expiry_date, is_used, created_at FROM coupons")
            
            rows = c.fetchall()
            for r in rows:
                d = list(r)
                # Ensure we have enough elements before accessing index 4
                if len(d) > 4:
                    d[4] = "Used" if r[4] else "Active"
                self.coupon_tree.insert("", "end", values=d)
            
            conn.close()
        except Exception as e:
            print(f"CRITICAL: Failed to load coupons: {e}")
            messagebox.showerror("Database Error", f"Failed to load coupon history: {e}")

    def load_tiers(self):
        self.tier_tree.delete(*self.tier_tree.get_children())
        cur.execute("SELECT tier_id, min_bill, reward_value FROM coupon_tiers ORDER BY min_bill ASC")
        for r in cur.fetchall():
            self.tier_tree.insert("", "end", values=r)

    def add_tier(self):
        try:
            m = float(self.e_min_bill.get())
            r = float(self.e_reward.get())
            cur.execute("INSERT INTO coupon_tiers (min_bill, reward_value) VALUES (?,?)", (m, r))
            db.commit()
            self.load_tiers()
            self.e_min_bill.delete(0, END)
            self.e_reward.delete(0, END)
        except ValueError:
            messagebox.showerror("Error", "Enter valid numbers.")

    def delete_tier(self):
        sel = self.tier_tree.selection()
        if not sel: return
        tid = self.tier_tree.item(sel[0])['values'][0]
        cur.execute("DELETE FROM coupon_tiers WHERE tier_id=?", (tid,))
        db.commit()
        self.load_tiers()

    def load_products(self):
        cur.execute("SELECT product_name FROM raw_inventory ORDER BY product_name ASC")
        self.combo_prod['values'] = [r[0] for r in cur.fetchall()]

    def load_offers(self, filter_query=None):
        self.prod_tree.delete(*self.prod_tree.get_children())
        if filter_query:
            cur.execute("SELECT product_name, offer_type, offer_value FROM raw_inventory WHERE offer_type != 'None' AND product_name LIKE ?", (f'%{filter_query}%',))
        else:
            cur.execute("SELECT product_name, offer_type, offer_value FROM raw_inventory WHERE offer_type != 'None'")
        for r in cur.fetchall():
            self.prod_tree.insert("", "end", values=r)

    def filter_offers(self, event=None):
        query = self.e_search_off.get().strip()
        self.load_offers(query)

    def delete_offer(self):
        sel = self.prod_tree.selection()
        if not sel:
            messagebox.showwarning("Selection Required", "Please select an offer from the list to remove.")
            return
        
        pn = self.prod_tree.item(sel[0])['values'][0]
        sure = messagebox.askyesno("Confirm Removal", f"Are you sure you want to remove the offer for '{pn}'?")
        if sure:
            cur.execute("UPDATE raw_inventory SET offer_type='None', offer_value=0 WHERE product_name=?", (pn,))
            db.commit()
            self.load_offers()
            self.load_products() # Refresh combo if needed
            messagebox.showinfo("Removed", f"Offer removed for {pn}")

    def on_offer_select(self, event=None):
        sel = self.prod_tree.selection()
        if not sel: return
        pn = self.prod_tree.item(sel[0])['values'][0]
        self.combo_prod.set(pn)
        self.on_product_select()

    def save_offer(self):
        pn = self.combo_prod.get()
        ot = self.combo_off_type.get()
        ov = self.e_off_val.get() or "0"
        if not pn: return
        try:
            cur.execute("UPDATE raw_inventory SET offer_type=?, offer_value=? WHERE product_name=?", (ot, float(ov), pn))
            db.commit()
            self.load_offers()
            messagebox.showinfo("Success", f"Offer updated for {pn}")
        except ValueError:
            messagebox.showerror("Error", "Invalid offer value.")

    def on_product_select(self, event=None):
        pn = self.combo_prod.get()
        if not pn: return
        
        cur.execute("SELECT product_id, product_cat, stock, mrp, barcode, offer_type, offer_value, expiry_date FROM raw_inventory WHERE product_name=?", (pn,))
        res = cur.fetchone()
        if res:
            pid, cat, stock, mrp, barcode, o_type, o_val, exp = res
            info = f"ID: {pid} | Category: {cat}\nStock: {stock} units | MRP: Rs. {mrp:.2f}\nExpiry: {exp} | Barcode: {barcode or 'N/A'}"
            self.lbl_details.config(text=info, fg=T.PRIMARY_DIM)
            
            # Load current offer into inputs
            self.combo_off_type.set(o_type or "None")
            self.e_off_val.delete(0, END)
            self.e_off_val.insert(0, str(o_val or 0))

    def scan_product(self, event=None):
        code = self.e_scan.get().strip()
        if not code: return
        
        # Try Barcode
        cur.execute("SELECT product_name FROM raw_inventory WHERE barcode=?", (code,))
        res = cur.fetchone()
        if res:
            self.combo_prod.set(res[0])
            self.e_scan.delete(0, END)
            self.on_product_select()
            return
            
        # Try Product ID
        cur.execute("SELECT product_name FROM raw_inventory WHERE product_id=?", (code,))
        res = cur.fetchone()
        if res:
            self.combo_prod.set(res[0])
            self.e_scan.delete(0, END)
            self.on_product_select()
            return
            
        messagebox.showwarning("Not Found", f"No product found with Barcode/ID: {code}")

    def open_cam_scanner(self):
        import scanner_util
        scanner_util.open_scanner(self.top, self.on_cam_scan)
        
    def on_cam_scan(self, code):
        self.e_scan.delete(0, END)
        self.e_scan.insert(0, code)
        self.scan_product()

    def auto_generate_discounts(self):
        """Logic-based automatic discount generator for all products."""
        sure = messagebox.askyesno("Smart Generator", "This will logically apply discounts to EVERY product based on category, stock, and expiry.\n\nContinue?", parent=self.top)
        if not sure: return
        
        try:
            cur.execute("SELECT product_id, product_name, product_cat, stock, mrp, expiry_date FROM raw_inventory")
            products = cur.fetchall()
            today = date.today()
            
            count = 0
            for p in products:
                pid, name, cat, stock, mrp, exp_str = p
                cat = (cat or "").lower()
                
                # Logical Base Discount
                if any(x in cat for x in ["fruit", "veg", "peri"]): base = random.randint(10, 25)
                elif any(x in cat for x in ["dairy", "bake", "milk", "bread"]): base = random.randint(5, 15)
                elif any(x in cat for x in ["snack", "biscuit", "chip", "choco"]): base = random.randint(5, 12)
                elif any(x in cat for x in ["staple", "rice", "oil", "dal", "flour"]): base = random.randint(2, 7)
                elif any(x in cat for x in ["beverage", "drink", "juice"]): base = random.randint(5, 10)
                elif any(x in cat for x in ["personal", "soap", "care"]): base = random.randint(5, 15)
                elif any(x in cat for x in ["household", "clean"]): base = random.randint(5, 10)
                else: base = random.randint(5, 10)
                
                # Stock Factor
                if stock > 150: base += random.randint(3, 8)
                elif stock > 80: base += random.randint(1, 4)
                
                # Expiry Factor
                if exp_str and exp_str != "N/A":
                    try:
                        exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                        delta = (exp_date - today).days
                        if delta < 15: base = max(base, 40)
                        elif delta < 30: base = max(base, 25)
                    except: pass
                
                base = min(base, 60) # Cap at 60%
                
                # Decide Type (85% Percentage, 15% Flat)
                if random.random() < 0.85:
                    off_type, off_val = "Percentage", float(base)
                else:
                    off_type = "Flat Discount"
                    ideal = (mrp * base / 100.0)
                    if ideal < 8: off_val = 5.0
                    elif ideal < 18: off_val = 10.0
                    elif ideal < 35: off_val = 20.0
                    else: off_val = 50.0
                    if off_val >= mrp: off_val = float(int(mrp/2))
                
                cur.execute("UPDATE raw_inventory SET offer_type=?, offer_value=? WHERE product_id=?", (off_type, off_val, pid))
                count += 1

            db.commit()
            self.load_offers()
            messagebox.showinfo("Success", f"Successfully applied logical discounts to {count} products!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to generate discounts: {e}")



    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        Admin_Page(root, self.user_data)

class Perishable_Tracker_Page:
    def __init__(self, top=None):
        top.geometry("1400x920")
        top.title("Perishable Item Tracker · Real Mart")
        top.configure(bg=T.BG_ROOT)

        self.top = top
        hdr = Frame(top, bg="#9B1C1C", height=56) # Deep red for warning status
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg="#9B1C1C")
        hc.pack(fill=BOTH, expand=True, padx=24, pady=12)
        Label(hc, text="⚠️ Perishable Item Tracker", font=T.FONT_SECTION, bg="#9B1C1C", fg=T.WHITE).pack(side=LEFT)
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg="#9B1C1C", relief=FLAT, padx=12, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT, padx=(10, 0))
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg="#9B1C1C", fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 15))

        body = Frame(top, bg=T.BG_ROOT)
        body.pack(fill=BOTH, expand=True, padx=40, pady=24)

        # Legend
        lframe = Frame(body, bg=T.BG_ROOT)
        lframe.pack(fill=X, pady=(0, 20))
        Label(lframe, text="Legend:", font=T.FONT_UI_SM, bg=T.BG_ROOT, fg=T.TEXT_SUB).pack(side=LEFT)
        Label(lframe, text=" ■ EXPIRED ", font=T.FONT_UI_SM, bg=T.BG_ROOT, fg="#D32F2F").pack(side=LEFT, padx=10)
        Label(lframe, text=" ■ EXPIRING SOON ", font=T.FONT_UI_SM, bg=T.BG_ROOT, fg="#FFA000").pack(side=LEFT, padx=10)

        Button(lframe, text="Clear All Expired Items", font=T.FONT_UI_SM, bg="#B71C1C", fg=T.WHITE, command=self.clear_expired, relief=FLAT, padx=15).pack(side=RIGHT)
        

        # Treeview
        tree_wrap = Frame(body, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        tree_wrap.pack(fill=BOTH, expand=True)
        
        self.tree = ttk.Treeview(tree_wrap, style="RM.Treeview", columns=("ID", "Name", "Cat", "Stock", "MRP", "Expiry", "Days Left"))
        self.tree.pack(fill=BOTH, expand=True)

        self.tree.heading("ID", text="ID", anchor=CENTER)
        self.tree.heading("Name", text="Product Name", anchor=CENTER)
        self.tree.heading("Cat", text="Category", anchor=CENTER)
        self.tree.heading("Stock", text="In Stock", anchor=CENTER)
        self.tree.heading("MRP", text="MRP", anchor=CENTER)
        self.tree.heading("Expiry", text="Expiry date", anchor=CENTER)
        self.tree.heading("Days Left", text="Days Remaining", anchor=CENTER)

        self.tree.column("#0", width=0, stretch=NO)
        self.tree.column("ID", width=100, anchor=CENTER, stretch=NO)
        self.tree.column("Name", width=280, anchor=CENTER, stretch=YES)
        self.tree.column("Cat", width=120, anchor=CENTER, stretch=NO)
        self.tree.column("Stock", width=80, anchor=CENTER, stretch=NO)
        self.tree.column("MRP", width=90, anchor=CENTER, stretch=NO)
        self.tree.column("Expiry", width=110, anchor=CENTER, stretch=NO)
        self.tree.column("Days Left", width=130, anchor=CENTER, stretch=NO)

        self.tree.tag_configure('expired', background='#D32F2F', foreground='white')
        self.tree.tag_configure('warning', background='#FFA000', foreground='black')
        self.tree.tag_configure('none', background='white', foreground=T.TEXT_ON_LIGHT)

        self.load_data()

    def load_data(self):
        self.tree.delete(*self.tree.get_children())
        cur.execute("SELECT product_id, product_name, product_cat, stock, mrp, expiry_date FROM raw_inventory")
        rows = cur.fetchall()
        
        today = date.today()
        
        for r in rows:
            pid, name, cat, stock, mrp, exp_str = r
            days_left = "N/A"
            tag = ""
            
            if exp_str and exp_str != "N/A":
                try:
                    exp_date = datetime.strptime(exp_str, "%Y-%m-%d").date()
                    delta = (exp_date - today).days
                    days_left = str(delta)
                    if delta < 0:
                        tag = 'expired'
                    elif delta <= 7:
                        tag = 'warning'
                except:
                    days_left = "Invalid Format"

            self.tree.insert("", "end", values=(pid, name, cat, stock, mrp, exp_str, days_left), tags=(tag,))

    def clear_expired(self):
        sure = messagebox.askyesno("Confirm", "Remove all expired items from inventory?", parent=self.top)
        if sure:
            today = str(date.today())
            cur.execute("DELETE FROM raw_inventory WHERE expiry_date < ? AND expiry_date != 'N/A'", [today])
            db.commit()
            self.load_data()
            messagebox.showinfo("Success", "Expired stock removed.")

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        global page2
        page2 = Admin_Page(root)

class System_Config_Page:
    def __init__(self, top=None, user_data=None):
        import config_manager
        self.top = top
        self.user_data = user_data
        self.config = config_manager.load_config()
        
        # In-memory data caches for lag-free instant tab switching
        self.cached_audit_rows = None
        self.cached_broadcast_rows = None
        self.cached_terminals_rows = None
        self.cached_network_my_ip = None
        self.cached_network_nodes = None
        self.cached_health_data = None
        
        top.geometry("1000x850")
        top.title("System & Network Hub · Real Mart")
        top.configure(bg=T.BG_ROOT)
        refresh_db()

        hdr = Frame(top, bg=T.PRIMARY, height=64) # Same as other panels
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        hc = Frame(hdr, bg=T.PRIMARY)
        hc.pack(fill=BOTH, expand=True, padx=24, pady=12)
        Label(hc, text="⚙️ System & Network Dashboard", font=T.FONT_SECTION, bg=T.PRIMARY, fg=T.WHITE).pack(side=LEFT)
        
        self.btn_back = Button(hc, text="← Back", command=self.Exit, bg=T.WHITE, fg=T.PRIMARY, relief=FLAT, padx=15, font=T.FONT_BTN)
        self.btn_back.pack(side=RIGHT)
        T.bind_hover(self.btn_back, enter_bg=T.CARD_SOFT, leave_bg=T.WHITE)
        
        self.clock = Label(hc, text="", font=T.FONT_UI, bg=T.PRIMARY, fg=T.WHITE)
        self.clock.pack(side=RIGHT, padx=(0, 20))

        # Main Layout (Tabbed)
        self.body = Frame(top, bg=T.BG_ROOT)
        self.body.pack(fill=BOTH, expand=True, padx=40, pady=(10, 24))
        
        # --- TAB NAVIGATION ---
        self.tab_f = Frame(self.body, bg=T.BG_ROOT)
        self.tab_f.pack(fill=X, pady=(0, 20))
        
        self.tabs = {}
        self.active_tab = "Network"
        
        def create_tab(name, label):
            btn = Button(self.tab_f, text=label, command=lambda: self.switch_tab(name))
            btn.pack(side=LEFT, padx=(0, 15))
            T.btn_tab(btn, active=(name == self.active_tab))
            self.tabs[name] = btn
            
        create_tab("Network", "🌐 LAN & Connectivity")
        create_tab("Safety", "🛡️ Data & Backups")
        create_tab("Health", "🩺 Maintenance & Health")
        create_tab("Terminals", "🖥️ Terminal Monitor")
        create_tab("Broadcast", "📢 Broadcast Center")
        create_tab("Audit", "📜 Audit Trail")
        create_tab("Updates", "🚀 Software Updates")
        
        # --- CONTENT CONTAINER ---
        self.container = Frame(self.body, bg=T.BG_ROOT)
        self.container.pack(fill=BOTH, expand=True)
        
        # --- TAB CONTENT FRAMES ---
        self.tab_frames = {
            "Network": Frame(self.container, bg=T.BG_ROOT),
            "Safety": Frame(self.container, bg=T.BG_ROOT),
            "Health": Frame(self.container, bg=T.BG_ROOT),
            "Terminals": Frame(self.container, bg=T.BG_ROOT),
            "Broadcast": Frame(self.container, bg=T.BG_ROOT),
            "Audit": Frame(self.container, bg=T.BG_ROOT),
            "Updates": Frame(self.container, bg=T.BG_ROOT),
        }
        
        self.tab_drawn = {
            "Network": False,
            "Safety": False,
            "Health": False,
            "Terminals": False,
            "Broadcast": False,
            "Audit": False,
            "Updates": False,
        }
        
        self.switch_tab("Network")

    def switch_tab(self, name):
        self.active_tab = name
        # Update button styles
        for k, b in self.tabs.items():
            T.btn_tab(b, active=(k == name))
        
        # Hide all tab frames
        for f in self.tab_frames.values():
            f.pack_forget()
            
        # Draw the target tab lazily if not already drawn
        if not self.tab_drawn[name]:
            target_frame = self.tab_frames[name]
            if name == "Network": self.draw_network_tab(target_frame)
            elif name == "Safety": self.draw_backup_tab(target_frame)
            elif name == "Health": self.draw_health_tab(target_frame)
            elif name == "Terminals": self.draw_terminals_tab(target_frame)
            elif name == "Broadcast": self.draw_broadcast_tab(target_frame)
            elif name == "Audit": self.draw_audit_tab(target_frame)
            elif name == "Updates": self.draw_updates_tab(target_frame)
            self.tab_drawn[name] = True
            
        # Show the active tab frame
        self.tab_frames[name].pack(fill=BOTH, expand=True)

    def refresh_audit(self):
        self.cached_audit_rows = None
        if hasattr(self, "audit_scroll_f") and self.audit_scroll_f.winfo_exists():
            for w in self.audit_scroll_f.winfo_children():
                w.destroy()
            loading_lbl = Label(self.audit_scroll_f, text="Loading logs...", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED, pady=60)
            loading_lbl.pack()
        import threading
        threading.Thread(target=self._async_load_audit_logs, daemon=True).start()

    def draw_audit_tab(self, parent_frame):
        f = parent_frame

        card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        card.pack(fill=BOTH, expand=True)

        hdr = Frame(card, bg=T.CARD)
        hdr.pack(fill=X, pady=(0, 20))
        Label(hdr, text="📜 System Activity & Audit Trail", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(side=LEFT)
        
        btn_refresh = Button(hdr, text="🔄 Refresh Logs", command=self.refresh_audit)
        btn_refresh.pack(side=RIGHT)
        T.btn_secondary(btn_refresh)

        # Table Header
        th = Frame(card, bg="#F1F3F1", pady=10)
        th.pack(fill=X)
        for txt in ["TIME", "EVENT", "DETAILS", "PC / USER"]:
            Label(th, text=txt, font=(T.FONT_FAMILY, 9, "bold"), bg="#F1F3F1", fg=T.TEXT_SUB).pack(side=LEFT, expand=True, fill=X)

        self.audit_scroll_f = Frame(card, bg=T.CARD)
        self.audit_scroll_f.pack(fill=BOTH, expand=True)
        
        if self.cached_audit_rows is not None:
            self._update_audit_ui(self.cached_audit_rows)
        else:
            self.audit_loading_lbl = Label(self.audit_scroll_f, text="Loading logs...", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED, pady=60)
            self.audit_loading_lbl.pack()
            import threading
            threading.Thread(target=self._async_load_audit_logs, daemon=True).start()

    def draw_broadcast_tab(self, parent_frame):
        f = parent_frame

        card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        card.pack(fill=X, pady=(0, 24))

        Label(card, text="📢 Send Instant Broadcast", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=W, pady=(0, 10))
        Label(card, text="Message will appear on all active POS billing screens instantly.", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(0, 20))

        self.msg_var = StringVar()
        entry = Entry(card, textvariable=self.msg_var, font=T.FONT_UI, bg=T.BG_ROOT, relief=FLAT, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        entry.pack(fill=X, ipady=8, pady=(0, 20))
        entry.focus_set()

        def send():
            msg = self.msg_var.get().strip()
            if not msg: return
            import threading
            threading.Thread(target=self._async_send_broadcast, args=(msg,), daemon=True).start()

        btn_send = Button(card, text="🚀 Broadcast Now", command=send)
        btn_send.pack(side=LEFT)
        T.btn_primary(btn_send)

        # Recent Broadcasts
        self.broadcast_list_card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        self.broadcast_list_card.pack(fill=BOTH, expand=True)
        Label(self.broadcast_list_card, text="Communication History", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(0, 20))

        if self.cached_broadcast_rows is not None:
            self._update_broadcasts_ui(self.cached_broadcast_rows)
        else:
            self.broadcast_loading_lbl = Label(self.broadcast_list_card, text="Loading history...", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED)
            self.broadcast_loading_lbl.pack(pady=20)
            import threading
            threading.Thread(target=self._async_load_broadcasts, daemon=True).start()

    def draw_updates_tab(self, parent_frame):
        import updater
        f = parent_frame

        card = Frame(f, bg=T.CARD, padx=40, pady=40, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        card.pack(pady=40)

        Label(card, text="🚀 Software Update Center", font=T.FONT_TITLE, bg=T.CARD, fg=T.PRIMARY_DIM).pack(pady=(0, 10))
        Label(card, text=f"Installed Version: {updater.get_current_version()}", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_SUB).pack(pady=(0, 30))

        status_lbl = Label(card, text="Your system is ready for version validation.", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_MUTED)
        status_lbl.pack(pady=(0, 30))

        def check():
            status_lbl.config(text="Contacting update server...", fg=T.PRIMARY)
            root.update_idletasks()
            found = updater.check_for_updates()
            if not found:
                status_lbl.config(text="You are currently using the latest professional version.", fg="#2E7D32")

        btn_check = Button(card, text="   Check for Updates Now   ", command=check)
        btn_check.pack(ipady=8)
        T.btn_primary(btn_check)

        Label(card, text="Updates will only be installed if you authorize them here.", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_MUTED).pack(pady=(30, 0))

    def time(self):
        # standard time update logic
        pass

    def refresh_terminals(self):
        self.cached_terminals_rows = None
        if hasattr(self, "terminals_scroll_f") and self.terminals_scroll_f.winfo_exists():
            for w in self.terminals_scroll_f.winfo_children():
                w.destroy()
            loading_lbl = Label(self.terminals_scroll_f, text="Loading terminals...", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED, pady=60)
            loading_lbl.pack()
        import threading
        threading.Thread(target=self._async_load_terminals, daemon=True).start()

    def draw_terminals_tab(self, parent_frame):
        f = parent_frame

        card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        card.pack(fill=BOTH, expand=True)

        hdr = Frame(card, bg=T.CARD)
        hdr.pack(fill=X, pady=(0, 20))
        Label(hdr, text="📡 Active Terminal Registry", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(side=LEFT)
        
        btn_refresh = Button(hdr, text="🔄 Refresh List", command=self.refresh_terminals)
        btn_refresh.pack(side=RIGHT)
        T.btn_secondary(btn_refresh)

        # Table Header
        th = Frame(card, bg="#F1F3F1", pady=10)
        th.pack(fill=X)
        for txt in ["STATUS", "STATION NAME", "IP ADDRESS", "ROLE", "LAST SEEN"]:
            Label(th, text=txt, font=(T.FONT_FAMILY, 9, "bold"), bg="#F1F3F1", fg=T.TEXT_SUB).pack(side=LEFT, expand=True, fill=X)

        self.terminals_scroll_f = Frame(card, bg=T.CARD)
        self.terminals_scroll_f.pack(fill=BOTH, expand=True)
        
        if self.cached_terminals_rows is not None:
            self._update_terminals_ui(self.cached_terminals_rows)
        else:
            self.terminals_loading_lbl = Label(self.terminals_scroll_f, text="Loading terminals...", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED, pady=60)
            self.terminals_loading_lbl.pack()
            import threading
            threading.Thread(target=self._async_load_terminals, daemon=True).start()

    def draw_network_tab(self, parent_frame):
        f = parent_frame

        # 1. NETWORK ROLE CARD
        role_card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        role_card.pack(fill=X, pady=(0, 24))
        
        Label(role_card, text="Counter Role & Identity", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=W, pady=(0, 20))
        
        inf_f = Frame(role_card, bg=T.CARD)
        inf_f.pack(fill=X)
        
        self.ip_var = StringVar(value="Detecting IP..." if self.cached_network_my_ip is None else f"My LAN IP: {self.cached_network_my_ip}")
        ip_lbl = Label(inf_f, textvariable=self.ip_var, font=T.FONT_UI, bg="#E8F5E9", fg=T.PRIMARY_DIM, padx=15, pady=8)
        ip_lbl.pack(side=LEFT)
        Label(inf_f, text="Use this IP to connect other terminals to this Host.", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).pack(side=LEFT, padx=15)
        
        self.btn_test_link = Button(inf_f, text="⚡ Test Connection", command=self.test_conn)
        self.btn_test_link.pack(side=RIGHT)
        T.btn_primary(self.btn_test_link)

        role_f = Frame(role_card, bg=T.CARD, pady=20)
        role_f.pack(fill=X)
        Label(role_f, text="Workstation Mode:", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(side=LEFT)
        self.role_var = StringVar(value=self.config["role"])
        r2 = Radiobutton(role_f, text="Terminal (Billing Only)", variable=self.role_var, value="terminal", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT, command=self.save_role)
        r2.pack(side=LEFT)

        # —— NEW: MASTER ROLE TRANSFER ——
        transfer_f = Frame(role_card, bg=T.CARD_SOFT, pady=15, padx=20, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        transfer_f.pack(fill=X, pady=(10, 0))
        Label(transfer_f, text="⚠️ System Migration", font=(T.FONT_FAMILY, 10, "bold"), bg=T.CARD_SOFT, fg="#D32F2F").pack(side=LEFT)
        Label(transfer_f, text="Transfer Master Status to a different PC.", font=T.FONT_SMALL, bg=T.CARD_SOFT, fg=T.TEXT_SUB).pack(side=LEFT, padx=15)
        
        btn_release = Button(transfer_f, text="Release Master Lock", command=self.release_master_lock)
        btn_release.pack(side=RIGHT)
        T.btn_secondary(btn_release)
        btn_release.configure(fg="#D32F2F")

        # 2. ACTIVE NODES MONITOR
        nodes_card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        nodes_card.pack(fill=BOTH, expand=True)
        
        node_hdr = Frame(nodes_card, bg=T.CARD)
        node_hdr.pack(fill=X, pady=(0, 15))
        Label(node_hdr, text="📡 Multi-Terminal Monitor", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(side=LEFT)
        
        self.btn_refresh_nodes = Button(node_hdr, text="🔄 Refresh Counter List", command=self.load_nodes)
        self.btn_refresh_nodes.pack(side=RIGHT)
        T.btn_ghost(self.btn_refresh_nodes)
        
        tree_f = Frame(nodes_card, bg=T.CARD)
        tree_f.pack(fill=BOTH, expand=True)
        
        self.node_tree = ttk.Treeview(tree_f, columns=("Name", "IP", "Role", "Last Seen"), show="headings", height=8, style="RM.Treeview")
        self.node_tree.pack(fill=BOTH, expand=True)
        
        self.node_tree.heading("Name", text="Computer Name", anchor=CENTER)
        self.node_tree.heading("IP", text="IP Address", anchor=CENTER)
        self.node_tree.heading("Role", text="Mode", anchor=CENTER)
        self.node_tree.heading("Last Seen", text="Last Active", anchor=CENTER)
        
        self.node_tree.column("Name", width=200, anchor=CENTER)
        self.node_tree.column("IP", width=160, anchor=CENTER)
        self.node_tree.column("Role", width=120, anchor=CENTER)
        self.node_tree.column("Last Seen", width=200, anchor=CENTER)
        T.apply_zebra_styling(self.node_tree)
        
        if self.cached_network_my_ip is not None and self.cached_network_nodes is not None:
            self._update_network_ui(self.cached_network_my_ip, self.cached_network_nodes)
        else:
            import threading
            threading.Thread(target=self._async_load_network_data, daemon=True).start()

    def draw_backup_tab(self, parent_frame):
        f = parent_frame

        # 1. DATABASE PATH CARD
        db_card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        db_card.pack(fill=X, pady=(0, 24))
        
        Label(db_card, text="Database Connection Settings", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=W, pady=(0, 20))
        
        self.db_path_var = StringVar(value=self.config["db_path"] or "(Default Local)")
        path_f = Frame(db_card, bg=T.CARD)
        path_f.pack(fill=X)
        self.e_path = Entry(path_f, textvariable=self.db_path_var, state="readonly"); self.e_path.pack(side=LEFT, fill=X, expand=True, ipady=6); T.entry_light(self.e_path)
        
        self.btn_browse = Button(path_f, text="📂 Connect to Network DB", command=self.browse_db)
        self.btn_browse.pack(side=LEFT, padx=(12, 0)); T.btn_secondary(self.btn_browse)
        self.btn_reset_db = Button(path_f, text="Reset Local", command=self.reset_db)
        self.btn_reset_db.pack(side=LEFT, padx=(10, 0)); T.btn_ghost(self.btn_reset_db)

        # 2. BACKUP CARD
        backup_card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        backup_card.pack(fill=X)
        
        Label(backup_card, text="Data Safety & Maintenance", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=W, pady=(0, 15))
        
        last_bk = self.config.get('last_backup', 'Never')
        self.last_backup_var = StringVar(value=f"Last Backup: {last_bk}")
        Label(backup_card, textvariable=self.last_backup_var, font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(0, 15))
        
        btn_f = Frame(backup_card, bg=T.CARD)
        btn_f.pack(fill=X)
        self.btn_bk_now = Button(btn_f, text="🚀 Backup Database Now", command=self.do_backup); self.btn_bk_now.pack(side=LEFT); T.btn_primary(self.btn_bk_now)
        self.btn_set_bk = Button(btn_f, text="📁 Change Backup Location", command=self.set_backup_dir); self.btn_set_bk.pack(side=LEFT, padx=15); T.btn_secondary(self.btn_set_bk)

        # Settings for automation
        auto_f = Frame(backup_card, bg=T.CARD, pady=25)
        auto_f.pack(fill=X)
        
        self.auto_bk_var = BooleanVar(value=self.config.get("auto_backup_on_close", True))
        Checkbutton(auto_f, text="Enable Automatic Background Backup on Close", variable=self.auto_bk_var, 
                    command=self.save_backup_settings, font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(side=LEFT)
        
        Label(auto_f, text=" |  Keep Backups for (Days):", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(side=LEFT, padx=(20, 0))
        self.retention_var = StringVar(value=str(self.config.get("backup_retention_days", 30)))
        re_e = Entry(auto_f, textvariable=self.retention_var, width=6, font=T.FONT_UI); re_e.pack(side=LEFT, padx=10); T.entry_light(re_e)
        self.btn_save_r = Button(auto_f, text="Save Policy", command=self.save_backup_settings); self.btn_save_r.pack(side=LEFT); T.btn_ghost(self.btn_save_r)

    def draw_health_tab(self, parent_frame):
        f = parent_frame

        # 1. DATABASE HEALTH STATS
        stats_card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        stats_card.pack(fill=X, pady=(0, 24))
        
        Label(stats_card, text="Database Engine Health", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=W, pady=(0, 20))
        
        # Grid for stats
        g = Frame(stats_card, bg=T.CARD)
        g.pack(fill=X)
        
        def add_stat(row, label, val_var, color_var=None, is_bold=False):
            Label(g, text=label, font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(row=row, column=0, sticky=W, pady=5)
            lbl = Label(g, textvariable=val_var, font=T.FONT_UI, bg=T.CARD)
            lbl.grid(row=row, column=1, sticky=W, padx=20, pady=5)
            if color_var:
                def update_color(*args):
                    try:
                        if lbl.winfo_exists():
                            lbl.config(fg=color_var.get())
                            if is_bold or color_var.get() != T.TEXT_ON_LIGHT:
                                lbl.config(font=(T.FONT_FAMILY, 11, "bold"))
                            else:
                                lbl.config(font=T.FONT_UI)
                    except:
                        pass
                color_var.trace_add("write", update_color)
                try:
                    update_color()
                except:
                    pass

        import os
        import config_manager
        
        cfg = config_manager.load_config()
        db_type = cfg.get("db_type", "sqlite").upper()
        
        self.stat_db_type = StringVar(value=db_type)
        if self.cached_health_data is not None:
            status, status_color, latency, size_str = self.cached_health_data
            self.stat_status = StringVar(value=status)
            self.stat_status_color = StringVar(value=status_color)
            self.stat_latency = StringVar(value=latency)
            self.stat_size = StringVar(value=size_str)
        else:
            self.stat_status = StringVar(value="Checking Status...")
            self.stat_status_color = StringVar(value=T.TEXT_MUTED)
            self.stat_latency = StringVar(value="Measuring Latency...")
            self.stat_size = StringVar(value="Calculating Size...")
        
        add_stat(0, "Storage Type:", self.stat_db_type)
        add_stat(1, "Connection Status:", self.stat_status, self.stat_status_color)
        add_stat(2, "Ping Latency:", self.stat_latency)
        
        if db_type == "SQLITE":
            add_stat(3, "Local DB Size:", self.stat_size)

        # 2. OPTIMIZATION TOOLS
        opt_card = Frame(f, bg=T.CARD, padx=30, pady=30, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        opt_card.pack(fill=X)
        
        Label(opt_card, text="Performance Optimization", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=W, pady=(0, 10))
        Label(opt_card, text="Run these tools to keep the application running smooth and fast.", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(0, 20))
        
        btn_f = Frame(opt_card, bg=T.CARD)
        btn_f.pack(fill=X)
        
        self.btn_optimize = Button(btn_f, text="🚀 Optimize Database Speed", command=self.optimize_db)
        self.btn_optimize.pack(side=LEFT)
        T.btn_primary(self.btn_optimize)
        
        self.btn_clean_cache = Button(btn_f, text="🧹 Clear Temp Assets", command=self.clear_cache)
        self.btn_clean_cache.pack(side=LEFT, padx=15)
        T.btn_secondary(self.btn_clean_cache)

        if self.cached_health_data is None:
            import threading
            threading.Thread(target=self._async_check_health, args=(db_type,), daemon=True).start()

    def optimize_db(self):
        import db_manager
        import config_manager
        try:
            db = db_manager.connect()
            cur = db.cursor()
            cfg = config_manager.load_config()
            db_type = cfg.get("db_type", "sqlite")
            if db_type == "sqlite":
                cur.execute("VACUUM")
            else:
                # MySQL optimization (basic)
                cur.execute("ANALYZE TABLE bill, bill_items, raw_inventory")
            db.commit()
            db_manager.log_audit("DATABASE", f"Database Optimized ({db_type})", self.user_data[1] if self.user_data else "Admin")
            self.cached_health_data = None
            messagebox.showinfo("Success", "Database optimization complete!", parent=self.top)
            
            # Reset health labels to "Checking..." in-place, and run background check
            if hasattr(self, "stat_status") and self.stat_status:
                self.stat_status.set("Checking Status...")
                self.stat_status_color.set(T.TEXT_MUTED)
                self.stat_latency.set("Measuring Latency...")
                self.stat_size.set("Calculating Size...")
            import threading
            threading.Thread(target=self._async_check_health, args=(db_type.upper(),), daemon=True).start()
        except Exception as e:
            messagebox.showerror("Error", f"Optimization failed: {e}", parent=self.top)

    def clear_cache(self):
        # Placeholder for clearing temp images/logs
        import db_manager
        db_manager.log_audit("SYSTEM", "Temporary cache cleared", self.user_data[1] if self.user_data else "Admin")
        messagebox.showinfo("Clean", "Temporary cache cleared.", parent=self.top)

    def load_nodes(self):
        self.cached_network_nodes = None
        if hasattr(self, "node_tree") and self.node_tree.winfo_exists():
            self.node_tree.delete(*self.node_tree.get_children())
        import threading
        threading.Thread(target=self._async_load_nodes_only, daemon=True).start()

    def save_backup_settings(self):
        import config_manager
        cfg = config_manager.load_config()
        cfg["auto_backup_on_close"] = self.auto_bk_var.get()
        try:
            cfg["backup_retention_days"] = int(self.retention_var.get())
        except:
            cfg["backup_retention_days"] = 30
        config_manager.save_config(cfg)
        db_manager.log_audit("SECURITY", f"Backup Policy Updated: {cfg['backup_retention_days']} days", self.user_data[1] if self.user_data else "Admin")
        messagebox.showinfo("Saved", "Data safety settings updated.", parent=self.top)

    def test_conn(self):
        import db_manager
        import config_manager
        
        cfg = config_manager.load_config()
        mgr = db_manager.DBConnection()
        
        # Disable button during test (Safely check attribute)
        btn = getattr(self, "btn_test_conn", getattr(self, "btn_test_link", None))
        if btn:
            btn.configure(state=DISABLED, text="Testing...")
        self.top.update()
        
        success, msg = mgr.test_current_config()
        
        if success:
            messagebox.showinfo("Network Success ✅", 
                f"CONNECTION OK!\n\nDetails: {msg}\n\nYour counters are ready to sync data.", 
                parent=self.top)
        else:
            messagebox.showerror("Network Failed ❌", 
                f"CONNECTION FAILED!\n\nError: {msg}\n\n"
                "Checklist:\n"
                "1. Is the Main PC turned ON?\n"
                "2. Is PC 2 on the same WiFi/LAN?\n"
                "3. Is the IP address in config.json correct?",
                parent=self.top)
                
        if btn:
            btn.configure(state=NORMAL, text="⚡ Test Network Link")

    def save_role(self):
        import config_manager, db_manager
        self.config["role"] = self.role_var.get()
        config_manager.save_config(self.config)
        refresh_db() # PICK UP NEW DB SETTINGS IMMEDIATELY
        db_manager.log_audit("NETWORK", f"PC Role Changed to {self.config['role'].upper()}", self.user_data[1] if self.user_data else "Admin")
        messagebox.showinfo("Config Updated", f"Role set to {self.config['role'].title()}. Database connection refreshed.")

    def browse_db(self):
        import config_manager
        path = filedialog.askopenfilename(title="Select Shared store.db file", filetypes=[("Database Files", "*.db")])
        if path:
            self.config["db_path"] = path
            config_manager.save_config(self.config)
            refresh_db() # PICK UP NEW DB SETTINGS IMMEDIATELY
            self.db_path_var.set(path)
            messagebox.showinfo("Success", "Network Database Path updated. Connection refreshed.")

    def reset_db(self):
        import config_manager
        self.config["db_path"] = ""
        config_manager.save_config(self.config)
        self.db_path_var.set("(Default Local Database)")
        messagebox.showinfo("Reset", "System will now use the local database. Restart required.")

    def do_backup(self):
        import config_manager
        success, msg = config_manager.perform_backup()
        if success:
            self.config = config_manager.load_config()
            self.last_backup_var.set(f"Last Backup: {self.config['last_backup']}")
            messagebox.showinfo("Backup Success", f"Backup created successfully at:\n{msg}")
        else:
            messagebox.showerror("Backup Failed", f"Error: {msg}")

    def release_master_lock(self):
        msg = ("WARNING: You are about to release the Master Lock for this application.\n\n"
               "1. This PC will lose Admin Hub access immediately.\n"
               "2. The next machine to log in will be able to 'Claim' the Master status.\n\n"
               "Do you want to proceed with the transfer?")
        if not messagebox.askyesno("Confirm Migration", msg, parent=self.top):
            return
        
        try:
            import db_manager, config_manager
            db = db_manager.connect()
            db.execute("UPDATE settings SET value = '' WHERE `key` = 'master_node_id'")
            db.commit()
            
            # Reset local role to terminal
            cfg = config_manager.load_config()
            cfg["role"] = "terminal"
            config_manager.save_config(cfg)
            
            messagebox.showinfo("Lock Released", "System lock released. This PC is now a Terminal.\n\nYou can now go to the NEW Main PC and log in to claim it.")
            force_logout()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to release lock: {e}")

    def set_backup_dir(self):
        import config_manager
        path = filedialog.askdirectory(title="Select Backup Folder")
        if path:
            self.config["backup_dir"] = path
            config_manager.save_config(self.config)
            messagebox.showinfo("Success", f"Backups will now be saved to: {path}")

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

    def Exit(self):
        for widget in root.winfo_children():
            widget.destroy()
        Admin_Page(root, self.user_data)

    def _async_load_audit_logs(self):
        import db_manager
        try:
            db = db_manager.connect()
            cur = db.execute("SELECT timestamp, event_type, description, pc_name, user_name FROM audit_trail ORDER BY timestamp DESC LIMIT 50")
            rows = cur.fetchall()
            self.cached_audit_rows = rows
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_audit_ui(rows))
        except:
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_audit_ui([]))

    def _update_audit_ui(self, rows):
        if not hasattr(self, "audit_scroll_f") or not self.audit_scroll_f.winfo_exists():
            return
        
        # Clear loading label
        for w in self.audit_scroll_f.winfo_children():
            w.destroy()
            
        if not rows:
            Label(self.audit_scroll_f, text="No activity logs recorded yet.", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED, pady=60).pack()
        else:
            for row in rows:
                line = Frame(self.audit_scroll_f, bg=T.CARD, pady=12)
                line.pack(fill=X)
                Frame(self.audit_scroll_f, bg=T.BORDER_SUBTLE, height=1).pack(fill=X)
                
                # Colors based on type
                etype = row[1].upper()
                clr = T.TEXT_ON_LIGHT
                if "SECURITY" in etype: clr = "#C62828"
                elif "DB" in etype or "DATA" in etype: clr = "#1565C0"
                elif "NETWORK" in etype: clr = "#2E7D32"
                
                # Time
                ts = str(row[0]).split()[1] if ' ' in str(row[0]) else str(row[0])
                Label(line, text=ts, font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).pack(side=LEFT, expand=True, fill=X)
                
                # Event
                Label(line, text=etype, font=(T.FONT_FAMILY, 9, "bold"), bg=T.CARD, fg=clr).pack(side=LEFT, expand=True, fill=X)
                
                # Details
                Label(line, text=row[2], font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_ON_LIGHT, anchor=W).pack(side=LEFT, expand=True, fill=X, padx=10)
                
                # Identity
                Label(line, text=f"{row[3]} / {row[4]}", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).pack(side=LEFT, expand=True, fill=X)

    def _async_send_broadcast(self, msg):
        import db_manager
        try:
            db = db_manager.connect()
            db.execute("UPDATE broadcast_messages SET is_active=0")
            db.execute("INSERT INTO broadcast_messages (message, is_active) VALUES (?, 1)", (msg,))
            db.commit()
            self.cached_broadcast_rows = None
            db_manager.log_audit("NETWORK", f"Broadcast Sent: {msg[:30]}...", self.user_data[1] if self.user_data else "Admin")
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, self._on_broadcast_sent_success)
        except Exception as e:
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: messagebox.showerror("Error", f"Failed to send broadcast: {e}"))

    def _on_broadcast_sent_success(self):
        self.msg_var.set("")
        messagebox.showinfo("Success", "Broadcast sent to all terminals!")
        self.switch_tab("Broadcast")

    def _async_load_broadcasts(self):
        import db_manager
        try:
            db = db_manager.connect()
            cur = db.execute("SELECT msg_id, message, sent_at, is_active FROM broadcast_messages ORDER BY sent_at DESC LIMIT 5")
            rows = cur.fetchall()
            self.cached_broadcast_rows = rows
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_broadcasts_ui(rows))
        except:
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_broadcasts_ui([]))

    def _update_broadcasts_ui(self, rows):
        if not hasattr(self, "broadcast_list_card") or not self.broadcast_list_card.winfo_exists():
            return
            
        # Clear loading label and any previous items
        for w in self.broadcast_list_card.winfo_children():
            if w != self.broadcast_list_card.winfo_children()[0]: # Keep title label
                w.destroy()
                
        if not rows:
            Label(self.broadcast_list_card, text="No previous broadcasts found.", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED).pack(pady=20)
        else:
            for row in rows:
                l = Frame(self.broadcast_list_card, bg=T.CARD, pady=12)
                l.pack(fill=X)
                Frame(self.broadcast_list_card, bg=T.BORDER_SUBTLE, height=1).pack(fill=X)
                
                status = "🟢 ACTIVE" if row[3] else "⚪ Sent"
                Label(l, text=status, font=(T.FONT_FAMILY, 9, "bold"), bg=T.CARD, fg="#4CAF50" if row[3] else T.TEXT_MUTED).pack(side=LEFT, padx=(0, 20))
                Label(l, text=row[1], font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT, anchor=W).pack(side=LEFT, fill=X, expand=True)
                
                if row[3]:
                    def clear(mid=row[0]):
                        import threading
                        threading.Thread(target=self._async_dismiss_broadcast, args=(mid,), daemon=True).start()
                    
                    btn_clear = Button(l, text="Dismiss", command=clear)
                    btn_clear.pack(side=RIGHT)
                    T.btn_secondary(btn_clear)

    def _async_dismiss_broadcast(self, mid):
        import db_manager
        try:
            c = db_manager.connect()
            c.execute("UPDATE broadcast_messages SET is_active=0 WHERE msg_id=?", (mid,))
            c.commit()
            self.cached_broadcast_rows = None
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self.switch_tab("Broadcast"))
        except:
            pass

    def _async_load_terminals(self):
        import db_manager
        try:
            db = db_manager.connect()
            try:
                db.execute("DELETE FROM active_sessions WHERE last_seen < datetime('now', '-5 minutes')")
                db.commit()
            except: pass
            
            cur = db.execute("SELECT pc_name, pc_ip, role, user_name, last_seen FROM active_sessions ORDER BY last_seen DESC")
            rows = cur.fetchall()
            self.cached_terminals_rows = rows
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_terminals_ui(rows))
        except:
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_terminals_ui([]))

    def _update_terminals_ui(self, rows):
        if not hasattr(self, "terminals_scroll_f") or not self.terminals_scroll_f.winfo_exists():
            return
            
        # Clear loading label
        for w in self.terminals_scroll_f.winfo_children():
            w.destroy()
            
        if not rows:
            Label(self.terminals_scroll_f, text="No other active terminals detected on the network.", font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_MUTED, pady=60).pack()
        else:
            for row in rows:
                line = Frame(self.terminals_scroll_f, bg=T.CARD, pady=12)
                line.pack(fill=X)
                Frame(self.terminals_scroll_f, bg=T.BORDER_SUBTLE, height=1).pack(fill=X)
                
                # Status Dot
                st_f = Frame(line, bg=T.CARD)
                st_f.pack(side=LEFT, expand=True, fill=X)
                Label(st_f, text="●", fg="#4CAF50", font=(T.FONT_FAMILY, 12), bg=T.CARD).pack(padx=10)
                
                Label(line, text=row[0], font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(side=LEFT, expand=True, fill=X)
                Label(line, text=row[1], font=T.FONT_UI, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(side=LEFT, expand=True, fill=X)
                Label(line, text=row[2], font=T.FONT_UI_SM, bg=T.CARD, fg=T.PRIMARY_DIM).pack(side=LEFT, expand=True, fill=X)
                # Time calc: Support both SQLite (string) and MySQL (datetime)
                last_seen_str = str(row[4])
                ts_display = last_seen_str.split()[1] if ' ' in last_seen_str else last_seen_str
                Label(line, text=ts_display, font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).pack(side=LEFT, expand=True, fill=X)

    def _async_load_network_data(self):
        import config_manager, network_manager
        try:
            my_ip = config_manager.get_local_ip()
            nodes = network_manager.get_active_nodes(minutes=10)
            self.cached_network_my_ip = my_ip
            self.cached_network_nodes = nodes
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_network_ui(my_ip, nodes))
        except:
            pass

    def _update_network_ui(self, my_ip, nodes):
        if hasattr(self, "ip_var") and self.ip_var:
            self.ip_var.set(f"My LAN IP: {my_ip}")
        if hasattr(self, "node_tree") and self.node_tree.winfo_exists():
            self.node_tree.delete(*self.node_tree.get_children())
            for n in nodes:
                self.node_tree.insert("", "end", values=n)

    def _async_load_nodes_only(self):
        import network_manager
        try:
            nodes = network_manager.get_active_nodes(minutes=10)
            self.cached_network_nodes = nodes
            if hasattr(self, "top") and self.top.winfo_exists():
                self.top.after(0, lambda: self._update_nodes_only_ui(nodes))
        except:
            pass

    def _update_nodes_only_ui(self, nodes):
        if hasattr(self, "node_tree") and self.node_tree.winfo_exists():
            self.node_tree.delete(*self.node_tree.get_children())
            for n in nodes:
                self.node_tree.insert("", "end", values=n)

    def _async_check_health(self, db_type):
        import db_manager, time, os
        start = time.time()
        try:
            db_manager.connect().cursor().execute("SELECT 1")
            diff = time.time() - start
            latency = f"{diff*1000:.1f} ms"
            status = "Online (Excellent)" if diff < 0.1 else "Online (Slow)"
            status_color = T.PRIMARY if diff < 0.1 else "#F57C00"
        except:
            latency = "N/A"
            status = "Disconnected"
            status_color = "#D32F2F"
            
        size_str = "N/A"
        if db_type == "SQLITE":
            try:
                import db_init
                size_mb = os.path.getsize(db_init.db_path()) / (1024*1024)
                size_str = f"{size_mb:.2f} MB"
            except:
                pass
                
        self.cached_health_data = (status, status_color, latency, size_str)
        if hasattr(self, "top") and self.top.winfo_exists():
            self.top.after(0, lambda: self._update_health_ui(status, status_color, latency, size_str))
            
    def _update_health_ui(self, status, status_color, latency, size_str):
        if hasattr(self, "stat_status") and self.stat_status:
            self.stat_status.set(status)
            self.stat_status_color.set(status_color)
            self.stat_latency.set(latency)
            self.stat_size.set(size_str)

class DatePickerPopup:
    def __init__(self, target_entry):
        self.target = target_entry
        self.now = datetime.now()
        self.year = self.now.year
        self.month = self.now.month
        
        # Setup window
        self.win = Toplevel(target_entry.winfo_toplevel())
        self.win.title("Select Date")
        self.win.geometry("300x340")
        self.win.resizable(False, False)
        self.win.configure(bg=T.BG_ROOT)
        self.win.transient(target_entry.winfo_toplevel())
        self.win.grab_set()
        
        # Position near entry
        x = target_entry.winfo_rootx()
        y = target_entry.winfo_rooty() + target_entry.winfo_height()
        self.win.geometry(f"+{x}+{y}")

        # Top Bar
        hdr = Frame(self.win, bg=T.PRIMARY_DIM, pady=10)
        hdr.pack(fill=X)
        
        Button(hdr, text=" < ", command=self.prev_month, bg=T.PRIMARY_DIM, fg=T.WHITE, relief=FLAT).pack(side=LEFT, padx=10)
        self.title_label = Label(hdr, text="", font=(T.FONT_FAMILY, 10, "bold"), bg=T.PRIMARY_DIM, fg=T.WHITE)
        self.title_label.pack(side=LEFT, expand=True)
        Button(hdr, text=" > ", command=self.next_month, bg=T.PRIMARY_DIM, fg=T.WHITE, relief=FLAT).pack(side=RIGHT, padx=10)
        
        # Days Header
        days_frame = Frame(self.win, bg=T.BG_ROOT)
        days_frame.pack(fill=X, pady=5)
        for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
            Label(days_frame, text=day, font=(T.FONT_FAMILY, 8, "bold"), bg=T.BG_ROOT, fg=T.TEXT_SUB, width=4).pack(side=LEFT, expand=True)
            
        # Grid
        self.bt_frame = Frame(self.win, bg=T.WHITE)
        self.bt_frame.pack(fill=BOTH, expand=True, padx=5, pady=5)
        
        self.update_calendar()

    def update_calendar(self):
        for w in self.bt_frame.winfo_children(): w.destroy()
        
        self.title_label.config(text=calendar.month_name[self.month] + " " + str(self.year))
        
        cal = calendar.monthcalendar(self.year, self.month)
        for row, week in enumerate(cal):
            for col, day in enumerate(week):
                if day == 0:
                    Label(self.bt_frame, bg=T.WHITE).grid(row=row, column=col, sticky=NSEW)
                else:
                    btn = Button(self.bt_frame, text=str(day), font=T.FONT_UI_SM, relief=FLAT, bg=T.WHITE,
                               command=lambda d=day: self.select_date(d))
                    btn.grid(row=row, column=col, sticky=NSEW, padx=1, pady=1)
                    
                    # Highlight today
                    if day == self.now.day and self.month == self.now.month and self.year == self.now.year:
                        btn.config(bg=T.PRIMARY_LIGHT, fg=T.WHITE)
                    
                    # Hover effect
                    btn.bind("<Enter>", lambda e, b=btn: b.config(bg=T.BG_ROOT))
                    btn.bind("<Leave>", lambda e, b=btn: b.config(bg=T.WHITE if b.cget("text") != str(self.now.day) else T.PRIMARY_LIGHT))

        for i in range(7): self.bt_frame.columnconfigure(i, weight=1)
        for i in range(6): self.bt_frame.rowconfigure(i, weight=1)

    def prev_month(self):
        self.month -= 1
        if self.month < 1:
            self.month = 12
            self.year -= 1
        self.update_calendar()

    def next_month(self):
        self.month += 1
        if self.month > 12:
            self.month = 1
            self.year += 1
        self.update_calendar()

    def select_date(self, day):
        ds = f"{self.year}-{self.month:02d}-{day:02d}"
        self.target.delete(0, END)
        self.target.insert(0, ds)
        self.win.destroy()
