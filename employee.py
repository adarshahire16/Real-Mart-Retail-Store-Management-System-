#==================imports===================

import db_manager as sqlite3
import re
import random
import string
import os
import time
from tkinter import *
import tkinter as tk
from tkinter import messagebox
from tkinter import filedialog
from tkinter import ttk
from time import strftime
from datetime import date, datetime, timedelta
from tkinter import scrolledtext as tkst
from tkinter import simpledialog, filedialog
import qrcode
import io
import json
import threading
import urllib.request
import urllib.parse
import webbrowser
import socket
import http.server
import socketserver
from PIL import Image, ImageTk, ImageDraw, ImageFont
# ============================================

def get_local_ip():
    """Returns the local IP address of this machine, prioritizing Wi-Fi/LAN over virtual adapters."""
    try:
        # Method 1: The UDP 'Connect' trick (Best for finding the primary internet-facing adapter)
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(0.5)
        try:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            if ip and not ip.startswith("127."):
                return ip
        except:
            pass

        # Method 2: Fallback for Offline Networks (Scan all interfaces)
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            # Filter out loopback and virtual adapter ranges if possible
            if not ip.startswith("127.") and not ip.startswith("169.254"):
                # Prioritize common local ranges
                if ip.startswith("192.168.") or ip.startswith("10.") or ip.startswith("172."):
                    return ip
        
        return socket.gethostbyname(hostname)
    except:
        return "127.0.0.1"


# --- GLOBAL BACKGROUND SERVER ---
SERVER_PORT = 8080
def start_bill_server():
    """Starts a simple HTTP server to serve the 'bills' directory on the local network."""
    import config_manager
    bill_dir = os.path.join(config_manager.get_base_path(), "bills")
    if not os.path.exists(bill_dir):
        os.makedirs(bill_dir)
        
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=bill_dir, **kwargs)
        def log_message(self, format, *args): pass # Mute server logs

    socketserver.TCPServer.allow_reuse_address = True
    
    # Port Failover logic
    global SERVER_PORT
    # Use ThreadingTCPServer to handle multiple mobile requests simultaneously (prevents hanging)
    class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True
        pass

    for port in [8080, 8081, 8888, 9999]:
        try:
            with ThreadedServer(("", port), QuietHandler) as httpd:
                SERVER_PORT = port
                print(f"Bill Server started at port {SERVER_PORT}")
                httpd.serve_forever()
            break
        except Exception as e:
            print(f"Port {port} failed: {e}")
            continue

# Start server in a background thread
threading.Thread(target=start_bill_server, daemon=True).start()

class QRCodeReceiptPopup:
    def __init__(self, parent, bill_no):
        # Use a full-screen Frame overlay in the same window
        self.win = Frame(parent, bg=T.BG_ROOT)
        self.win.place(relx=0, rely=0, relwidth=1, relheight=1)

        # Header
        hdr = Frame(self.win, bg="#2E7D32", height=80)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        Label(hdr, text="🌱 DIGITAL RECEIPT READY", font=T.FONT_SECTION, bg="#2E7D32", fg=T.WHITE).pack(pady=20)

        # Main Body with centering for large screens
        main_body = Frame(self.win, bg=T.BG_ROOT)
        main_body.pack(fill=BOTH, expand=True)

        body = Frame(main_body, bg=T.CARD, padx=50, pady=40, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        body.place(relx=0.5, rely=0.5, anchor=CENTER, relwidth=0.7, relheight=0.9)
        
        Label(body, text=f"Bill #{bill_no}", font=T.FONT_TITLE, bg=T.CARD, fg=T.PRIMARY).pack()
        Label(body, text="Ask the customer to scan this code with their phone camera to download the receipt.", 
              font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB, wraplength=400, justify=CENTER).pack(pady=(10, 20))

        # Instruction-free QR display
        ip = get_local_ip()
        url = f"http://{ip}:{SERVER_PORT}/Bill_{bill_no}.html"
        
        try:
            qr = qrcode.QRCode(version=1, box_size=12, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            
            # Use 380x380 to ensure everything fits comfortably
            img = img.resize((380, 380))
            self.qr_img = ImageTk.PhotoImage(img)
            
            qr_lbl = Label(body, image=self.qr_img, bg="white", highlightthickness=2, highlightbackground="#2E7D32")
            qr_lbl.pack(pady=10)
            qr_lbl.image = self.qr_img
        except Exception as e:
            print(f"QR Generation Error: {e}")
            Label(body, text="[ QR Display Error ]", font=T.FONT_SECTION, bg=T.CARD, fg="#c0392b").pack(pady=20)

        # Button Area - Unified sizing
        def open_url():
            import webbrowser
            webbrowser.open(url)
            
        btn_f = Frame(body, bg=T.CARD)
        btn_f.pack(fill=X, pady=(20, 0))
        btn_f.grid_columnconfigure(0, weight=1)
        btn_f.grid_columnconfigure(1, weight=1)

        # Shared style for equal sizing
        btn_open = Button(btn_f, text="🔗 OPEN IN BROWSER", command=open_url, font=T.FONT_UI_SM,
                           bg="#F5F5F5", fg=T.PRIMARY, relief=FLAT, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        btn_open.grid(row=0, column=0, padx=(0, 10), sticky="nsew", ipady=15)
        
        def on_h_open(e): btn_open.configure(bg="#EEEEEE", highlightbackground=T.PRIMARY)
        def on_l_open(e): btn_open.configure(bg="#F5F5F5", highlightbackground=T.BORDER_SUBTLE)
        btn_open.bind("<Enter>", on_h_open)
        btn_open.bind("<Leave>", on_l_open)

        btn_next = Button(btn_f, text="NEXT SALE", command=self.win.destroy, font=T.FONT_UI_SM,
                           bg="#2E7D32", fg=T.WHITE, relief=FLAT, highlightthickness=1, highlightbackground="#2E7D32")
        btn_next.grid(row=0, column=1, padx=(10, 0), sticky="nsew", ipady=15)
        
        def on_h_next(e): btn_next.configure(bg="#1B5E20")
        def on_l_next(e): btn_next.configure(bg="#2E7D32")
        btn_next.bind("<Enter>", on_h_next)
        btn_next.bind("<Leave>", on_l_next)

import db_init
import theme as T
import scanner_util

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
biller = None
exit_to_main = None
page2 = None


user = None
passwd = None
fname = None
lname = None
new_user = None
new_passwd = None
cust_name = None
cust_num = None
cust_new_bill = None
cust_search_bill = None
bill_date = None

def init_vars(parent):
    global user, passwd, fname, lname, new_user, new_passwd, cust_name, cust_num, cust_new_bill, cust_search_bill, bill_date
    user = StringVar(parent)
    passwd = StringVar(parent)
    fname = StringVar(parent)
    lname = StringVar(parent)
    new_user = StringVar(parent)
    new_passwd = StringVar(parent)
    cust_name = StringVar(parent)
    cust_num = StringVar(parent)
    cust_new_bill = StringVar(parent)
    cust_search_bill = StringVar(parent)
    bill_date = StringVar(parent)

def start_staff_pos(parent_root, exit_cb):
    global root, biller, exit_to_main, page1, username
    refresh_db() # PICK UP LATEST NETWORK CONFIG
    root = parent_root
    biller = parent_root
    exit_to_main = exit_cb
    
    init_vars(root)
    # —— CLEAN UI LAYER ——
    # Preserve the canvas but clear its content
    cv = T.setup_glass_canvas(root, image_name=T.Backgrounds.POS)
    T.clear_ui_content(cv)
    
    # Destroy other legacy widgets
    for widget in root.winfo_children():
        if not getattr(widget, "_is_bg_canvas", False):
            widget.destroy()
        
    root.title("Real Mart · Staff")
    T.style_root(root)
    T.setup_ttk(root)
    
    page1 = login_page(root, cv)
    root.bind("<Return>", login)


def random_bill_number(stringLength):
    lettersAndDigits = string.ascii_letters.upper() + string.digits
    strr=''.join(random.choice(lettersAndDigits) for i in range(stringLength-2))
    return ('BB'+strr)

def random_emp_id(stringLength):
    Digits = string.digits
    strr=''.join(random.choice(Digits) for i in range(stringLength-3))
    return ('EMP'+strr)

def get_local_ip():
    """Returns the local IP address of this machine on the active network."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # Doesn't need to be reachable, just triggers local IP discovery
        s.connect(('8.8.8.8', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

# Global configuration for local receipt delivery (Consolidated with SERVER_PORT above)
import config_manager
BILLS_DIR = os.path.abspath(os.path.join(config_manager.get_base_path(), "bills"))

def show_digital_bill(parent, bill_no, bill_body):
    """Shows a popup with a QR code that downloads the PDF directly from the POS over Wi-Fi."""
    # Note: Server is already started globally at the top of the file
    
    dlg = Toplevel(parent)
    dlg.title("Offline-Direct PDF Receipt")
    dlg.geometry("450x640")
    dlg.configure(bg=T.BG_ROOT)
    dlg.transient(parent)
    dlg.grab_set()

    wrap = Frame(dlg, bg=T.CARD, padx=20, pady=20)
    wrap.pack(fill=BOTH, expand=True, padx=15, pady=15)
    
    status_label = Label(wrap, text="📄 Generating Direct PDF...", font=T.FONT_TITLE_MD, bg=T.CARD, fg=T.PRIMARY)
    status_label.pack(pady=(10, 5))
    
    loading_label = Label(wrap, text="Preparing your bill for instant Wi-Fi delivery...", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB)
    loading_label.pack()
    
    qr_container = Frame(wrap, bg="white", highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
    
    def prepare_bill():
        # Use the absolute BILLS_DIR for all operations
        try:
            if not os.path.exists(BILLS_DIR): os.makedirs(BILLS_DIR)
            
            # Generate a random short filename for safety
            safe_id = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
            filename = f"bill_{bill_no}_{safe_id}.pdf"
            pdf_path = os.path.join(BILLS_DIR, filename)
            
            # Save PDF to the absolute path
            render_receipt_as_pdf(bill_body, target_path=pdf_path)
            
            # 3. Get Local IP and Create Link
            local_ip = get_local_ip()
            local_url = f"http://{local_ip}:{SERVER_PORT}/{filename}"
            
            def update_ui():
                status_label.config(text="✅ Direct PDF Ready!", fg=T.PRIMARY_DIM)
                loading_label.config(text=f"Customer must be on the same Wi-Fi as POS.")
                
                qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=7, border=2)
                qr.add_data(local_url)
                qr.make(fit=True)
                qr_img = qr.make_image(fill_color="#2b2d42", back_color="white").resize((280, 280))
                
                buffer = io.BytesIO()
                qr_img.save(buffer, format="PNG")
                photo = ImageTk.PhotoImage(data=buffer.getvalue())
                
                qr_container.pack(pady=(20, 10))
                qr_label = Label(qr_container, image=photo, bg="white")
                qr_label.image = photo
                qr_label.pack(padx=2, pady=2)
                
                info_box = Frame(wrap, bg="#E3F2FD", padx=10, pady=8)
                info_box.pack(pady=10, fill=X)
                Label(info_box, text=f"📍 Connection: Local Network", font=(T.FONT_FAMILY, 8, "bold"), bg="#E3F2FD", fg="#1976D2").pack()
                Label(info_box, text=f"IP: {local_ip}", font=(T.FONT_FAMILY, 8), bg="#E3F2FD", fg="#1976D2").pack()
                
            dlg.after(0, update_ui)
            
        except Exception as e:
            def show_err():
                status_label.config(text="❌ Local Server Error", fg="#c0392b")
                loading_label.config(text=f"Error: {str(e)}")
            dlg.after(0, show_err)

    threading.Thread(target=prepare_bill, daemon=True).start()
    
    # Help message
    help_text = Label(wrap, text="Note: Customer phone must scan this QR\nwhile connected to the shop Wi-Fi.", 
                     font=(T.FONT_FAMILY, 8, "italic"), bg=T.CARD, fg=T.TEXT_SUB)
    help_text.pack(side=BOTTOM, pady=10)

    btn = Button(wrap, text="Close", command=dlg.destroy)
    btn.pack(side=BOTTOM, fill=X, ipady=8)
    T.btn_primary(btn)

def render_receipt_as_pdf(bill_body, target_path=None):
    """Renders the bill as an Ultra High Quality (300 DPI) PDF with crisp text."""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import hashlib
        
        # 0. Generate Security Hash
        security_hash = hashlib.md5(bill_body.encode()).hexdigest().upper()[:12]

        # 1. Double the internal canvas size for "Ultra High Definition"
        # This provides more raw pixels before it's saved as a PDF
        width, height = 1200, 3200 
        img = Image.new('RGB', (width, height), color='white')
        d = ImageDraw.Draw(img)
        
        # 2. Load High-Res Fonts (Doubled sizes for the larger canvas)
        try:
            font_path = "consola.ttf"
            fnt_body = ImageFont.truetype(font_path, 36) # Crisp monospace
            fnt_header = ImageFont.truetype("arialbd.ttf", 60)
            fnt_sub = ImageFont.truetype("arial.ttf", 34)
            fnt_tiny = ImageFont.truetype("arial.ttf", 26)
            fnt_watermark = ImageFont.truetype("arial.ttf", 110)
        except:
            fnt_body = ImageFont.load_default()
            fnt_header = fnt_body
            fnt_sub = fnt_body
            fnt_tiny = fnt_body
            fnt_watermark = fnt_body

        # 3. Add High-Res Watermark
        watermark_text = "REAL MART ORIGINAL"
        try:
            txt_img = Image.new('RGBA', (1200, 400), (255, 255, 255, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            txt_draw.text((0, 100), watermark_text, font=fnt_watermark, fill=(200, 220, 200, 50))
            rotated_txt = txt_img.rotate(45, expand=1)
            img.paste(rotated_txt, (-100, 800), rotated_txt)
            img.paste(rotated_txt, (-100, 1800), rotated_txt)
        except: pass

        # 4. Draw Header (Professional Style)
        d.rectangle([0, 0, width, 220], fill="#F1F8E9")
        d.text((60, 50), "REAL MART", font=fnt_header, fill='#1B5E20')
        d.text((60, 130), "AUTHENTIC DIGITAL RECEIPT", font=fnt_sub, fill='#455A64')
        
        # 5. Official Verification Seal (High Res & Multi-layered)
        cx, cy, r = 1000, 110, 85
        # Draw a light green circle background
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#F1F8E9", outline="#2E7D32", width=6)
        # Draw a thin inner border for a premium look
        ir = r - 10
        d.ellipse([cx-ir, cy-ir, cx+ir, cy+ir], outline="#2E7D32", width=2)

        # Use High-Res Bold fonts for the seal text
        try:
            fnt_seal = ImageFont.truetype("arialbd.ttf", 26)
        except:
            fnt_seal = ImageFont.load_default()

        d.text((cx, cy-25), "ORIGINAL", font=fnt_seal, fill="#1B5E20", anchor="mm")
        d.text((cx, cy+15), "VERIFIED", font=fnt_seal, fill="#1B5E20", anchor="mm")

        d.line((0, 220, width, 220), fill='#1B5E20', width=6)
        
        # 6. Draw the body (Using large monospace font)
        y_pos = 280
        for line in bill_body.split('\n'):
            clean_line = line.replace("═", "=").replace("─", "-")
            d.text((80, y_pos), clean_line, font=fnt_body, fill='#263238')
            y_pos += 48 # Increased spacing for high-res
            if y_pos > height - 200: break
            
        # 7. Security Footer
        d.line((80, y_pos + 40, width - 80, y_pos + 40), fill='#2E7D32', width=2)
        y_pos += 80
        d.text((80, y_pos), f"SECURITY HASH: {security_hash}", font=fnt_tiny, fill='#546E7A')
        d.text((80, y_pos + 40), f"ISSUED AT: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", font=fnt_tiny, fill='#546E7A')
        
        d.text((width//2, y_pos + 120), "This is a computer-generated original document.", font=fnt_tiny, fill='#78909C', anchor="mm")
        d.text((width//2, y_pos + 160), "🌱 Real Mart - Fresh & Organized", font=fnt_sub, fill='#1B5E20', anchor="mm")

        # 8. Crop image
        final_img = img.crop((0, 0, width, y_pos + 220))
        
        if target_path is None:
            pdf_path = f"bill_{int(time.time())}.pdf"
        else:
            pdf_path = target_path
            
        # 9. Save as Ultra High Quality PDF (300 DPI)
        # 300 DPI is the industry standard for professional printing
        final_img.save(pdf_path, "PDF", resolution=300.0, title=f"Real Mart Receipt #{security_hash}", author="Real Mart POS System")
        return pdf_path
    except Exception as e:
        print(f"PDF Rendering failed: {e}")
        return None

    except Exception as e:
        print(f"PDF Rendering failed: {e}")
        return None

def valid_phone(phn):
    if re.match(r"[789]\d{9}$", phn):
        return True
    return False


def save_bill_silent(bill_no, bill_body):
    """Saves the bill as a beautiful, mobile-responsive HTML file and a PDF copy."""
    try:
        import config_manager
        bill_dir = os.path.join(config_manager.get_base_path(), "bills")
        if not os.path.exists(bill_dir):
            os.makedirs(bill_dir)
        
        # 1. Generate a PDF copy first (for the download button)
        pdf_filename = f"Bill_{bill_no}.pdf"
        pdf_path = os.path.join(bill_dir, pdf_filename)
        render_receipt_as_pdf(bill_body, target_path=pdf_path)

        # 2. Prepare Responsive HTML Content
        # Replace unicode lines that cause encoding issues in browsers
        clean_body = bill_body.replace("═", "=").replace("─", "-")
        
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Receipt #{bill_no} - Real Mart</title>
    <style>
        body {{ font-family: 'Courier New', Courier, monospace; background: #f0f4f8; padding: 10px; margin: 0; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }}
        .receipt {{ 
            background: white; 
            width: 95%;
            max-width: 420px; 
            margin: 15px auto; 
            padding: 25px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.1); 
            border-top: 10px solid #2E7D32;
            border-radius: 12px;
            white-space: pre-wrap;
            color: #2c3e50;
            line-height: 1.5;
            word-break: break-all;
            font-size: 14px;
        }}
        .btn {{
            display: inline-block;
            background: #2E7D32;
            color: white;
            padding: 14px 24px;
            text-decoration: none;
            border-radius: 8px;
            font-family: sans-serif;
            font-weight: bold;
            margin-top: 10px;
            box-shadow: 0 4px 12px rgba(46, 125, 50, 0.3);
            transition: all 0.2s;
        }}
        .btn:active {{ transform: scale(0.98); background: #1B5E20; }}
        .footer-text {{ text-align: center; margin-top: 15px; color: #7f8c8d; font-size: 13px; font-family: sans-serif; padding: 10px; }}
        
        /* Mobile Specific Tweaks */
        @media (max-width: 480px) {{
            .receipt {{ padding: 15px; font-size: 12px; width: 90%; }}
            .btn {{ width: 80%; padding: 16px; font-size: 16px; }}
        }}
        @media print {{ body {{ background: white; padding: 0; }} .receipt {{ box-shadow: none; margin: 0; max-width: 100%; }} .btn {{ display: none; }} }}
    </style>
</head>
<body>
    <div class="receipt">{clean_body}</div>
    
    <a href="{pdf_filename}" download class="btn">⬇️ Download PDF Receipt</a>

    <div class="footer-text">
        Thank you for choosing a paperless experience! 🌱<br>
        <b>Real Mart - Fresh & Organized</b>
    </div>
</body>
</html>"""

        filename = f"Bill_{bill_no}.html"
        path = os.path.join(bill_dir, filename)
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return path
    except Exception as e:
        print(f"Silent Save Error: {e}")
        return None

    except Exception as e:
        print(f"Silent Save Error: {e}")
        return None

def send_whatsapp_receipt(phone, bill_no, total, items_count):
    # Ensure phone has country code (India default 91)
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) == 10:
        clean_phone = "91" + clean_phone
    
    msg = (
        f"Hello! Thank you for shopping at *Real Mart*! 🛍️\n\n"
        f"📄 *BILL RECEIPT*\n"
        f"Bill No: #{bill_no}\n"
        f"Items: {items_count}\n"
        f"Total: *₹{total:.2f}*\n\n"
        f"Your digital bill has been saved to our records. Thank you for choosing a paperless experience! 🌱"
    )
    encoded_msg = urllib.parse.quote(msg)
    url = f"https://api.whatsapp.com/send?phone={clean_phone}&text={encoded_msg}"
    webbrowser.open(url)

def prompt_save_bill_copy(parent, bill_no, bill_date, bill_time_short, cust_name, cust_num, payment, bill_body):
    """Modal prompt to save a text copy of the bill (non-blocking after Close)."""
    dlg = Toplevel(parent)
    dlg.title("Save bill copy")
    dlg.configure(bg=T.BG_ROOT)
    dlg.transient(parent)
    dlg.resizable(False, False)
    wrap = Frame(
        dlg,
        bg=T.CARD,
        padx=24,
        pady=22,
        highlightthickness=1,
        highlightbackground=T.WOOD_BORDER,
    )
    wrap.pack(fill=BOTH, expand=True, padx=18, pady=18)
    Label(
        wrap,
        text="Bill recorded",
        font=T.FONT_SECTION,
        bg=T.CARD,
        fg=T.TEXT_ON_LIGHT,
    ).pack(anchor=W)
    Label(
        wrap,
        text="The sale is saved in the database. You can also save a readable copy on this computer.",
        font=T.FONT_UI_SM,
        bg=T.CARD,
        fg=T.TEXT_SUB,
        wraplength=420,
        justify=LEFT,
    ).pack(anchor=W, pady=(8, 16))
    meta = "Bill # {} · {} · {} · {}".format(bill_no, bill_date, bill_time_short, payment)
    Label(wrap, text=meta, font=T.FONT_UI, bg=T.CARD, fg=T.PRIMARY_DIM).pack(anchor=W)

    def do_save():
        default = "Bill_{}.txt".format(bill_no)
        path = filedialog.asksaveasfilename(
            parent=dlg,
            title="Save bill copy",
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("All files", "*.*")],
            initialfile=default,
        )
        if not path:
            return
        try:
            # We use the bill_body as is, but we can prepend a small meta header if needed for the file.
            # However, since we overhauled bill_body to include the store header, we just write it.
            with open(path, "w", encoding="utf-8") as f:
                f.write(bill_body)
            messagebox.showinfo("Saved", "Bill saved to:\n{}".format(path), parent=dlg)
            dlg.destroy()
        except OSError as e:
            messagebox.showerror("Save failed", str(e), parent=dlg)

    bf = Frame(wrap, bg=T.CARD)
    bf.pack(fill=X, pady=(20, 0))
    b_save = Button(bf, text="Save copy to file…", command=do_save)
    b_save.pack(side=LEFT, padx=(0, 10))
    T.btn_primary(b_save)
    
    # NEW: Digital Delivery Button
    # We pass the full bill_body so it can be encoded in the QR.
    b_digital = Button(bf, text="Digital Receipt (QR)", command=lambda: show_digital_bill(dlg, bill_no, bill_body))
    b_digital.pack(side=LEFT, padx=(0, 10))
    T.btn_secondary(b_digital)

    b_skip = Button(bf, text="Close", command=dlg.destroy)
    b_skip.pack(side=LEFT)
    T.btn_secondary(b_skip)
    dlg.grab_set()
    dlg.wait_window()

def login(Event=None):
    global username
    username = user.get().strip()
    password = passwd.get().strip()

    # Professional Security: Support both legacy hashing and new reversible encryption for transition
    hashed_pw = db_init.hash_password(password)
    encrypted_pw = db_init.secure_store(password)
    find_user = "SELECT * FROM employee WHERE emp_id = ? AND (password = ? OR password = ?)"
    cur.execute(find_user, [username, hashed_pw, encrypted_pw])
    results = cur.fetchone() # Fetch one since emp_id is PRIMARY KEY
    if results:
        # Check approval status (index 7 in the SELECT * from the new schema)
        if len(results) > 7 and results[7] == 0:
            messagebox.showwarning("Access Denied", "Your account is pending approval from an Admin.\nPlease contact your manager.", parent=root)
            page1.entry2.delete(0, END)
            return

        # messagebox.showinfo("Login Page", "The login is successful")
        page1.entry1.delete(0, END)
        page1.entry2.delete(0, END)
        global page2
        # Safe cleanup: unbind before destroying to prevent event leaks
        root.unbind("<Return>")
        
        # Immediate removal of UI content tags from canvas if it exists
        for child in root.winfo_children():
            if hasattr(child, "delete"):
                child.delete("all")
            child.destroy()
            
        global biller
        biller = root
        # Removed background image for POS internally to ensure clean white/green theme
        # T.apply_bg_image(root) 
        page2 = bill_window(biller)
        page2.time()
        
        

    else:
        messagebox.showerror("Error", "Invalid username or password", parent=root)
        page1.entry2.delete(0, END)

def exitt():
    root.current_view = "main_menu" # Reset view state
    exit_to_main()

class login_page:
    def __init__(self, top, cv):
        self.top = top
        self.cv = cv
        self.view_state = "login" # States: login, forgot, reset
        self.reset_eid = None
        
        # 1. Widgets for Login Fields
        self.entry1 = Entry(self.cv, textvariable=user, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry2 = Entry(self.cv, textvariable=passwd, show="*", width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        
        # 2. Widgets for Forgot Password flow (Created here to be re-used/mapped)
        self.forgot_eid_var = StringVar()
        self.forgot_phone_var = StringVar()
        self.new_pw_var = StringVar()
        
        self.entry_forgot_id = Entry(self.cv, textvariable=self.forgot_eid_var, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_forgot_phone = Entry(self.cv, textvariable=self.forgot_phone_var, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_new_pw = Entry(self.cv, textvariable=self.new_pw_var, show="*", width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)

        # 3. Widgets for Registration flow
        self.reg_name = StringVar()
        self.reg_contact = StringVar()
        self.reg_address = StringVar()
        self.reg_aadhar = StringVar()
        self.reg_pass = StringVar()

        self.entry_reg_name = Entry(self.cv, textvariable=self.reg_name, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_reg_contact = Entry(self.cv, textvariable=self.reg_contact, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_reg_address = Entry(self.cv, textvariable=self.reg_address, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_reg_aadhar = Entry(self.cv, textvariable=self.reg_aadhar, width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        self.entry_reg_pass = Entry(self.cv, textvariable=self.reg_pass, show="*", width=32, font=T.FONT_UI, relief="flat", bg="#FFFFFF", highlightthickness=0)
        
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

    def go_forgot(self, e=None):
        self.forgot_eid_var.set("")
        self.forgot_phone_var.set("")
        self.view_state = "forgot"
        self.refresh_ui(force=True)

    def go_login(self, e=None):
        self.view_state = "login"
        self.refresh_ui(force=True)

    def go_register(self, e=None):
        self.reg_name.set("")
        self.reg_contact.set("")
        self.reg_address.set("")
        self.reg_aadhar.set("")
        self.reg_pass.set("")
        self.view_state = "register"
        self.refresh_ui(force=True)

    def exitt_login(self):
        """Navigates back to main menu without confirmation (used for pre-login back button)."""
        root.current_view = "main_menu"
        exit_to_main()

    def register_staff(self):
        name = self.reg_name.get().strip()
        contact = self.reg_contact.get().strip()
        address = self.reg_address.get().strip()
        aadhar = self.reg_aadhar.get().strip()
        pw = self.reg_pass.get().strip()

        if not (name and contact and address and aadhar and pw):
            messagebox.showerror("Error", "All fields are required.", parent=self.top)
            return
        
        if not valid_phone(contact):
            messagebox.showerror("Error", "Invalid phone number.", parent=self.top)
            return
        
        if not (aadhar.isdigit() and len(aadhar) == 12):
            messagebox.showerror("Error", "Aadhar number must be 12 digits.", parent=self.top)
            return
        
        if len(pw) < 4:
            messagebox.showerror("Error", "Password must be at least 4 characters.", parent=self.top)
            return

        new_id = random_emp_id(7)
        try:
            # Use secure_store for reversible encryption (Allows Admin to reveal plain text)
            stored_pw = db_init.secure_store(pw)
            cur.execute(
                "INSERT INTO employee(emp_id, name, contact_num, address, aadhar_num, password, designation, approved) VALUES(?,?,?,?,?,?,?,?)", 
                (new_id, name, contact, address, aadhar, stored_pw, "Employee", 0)
            )
            db.commit()
            messagebox.showinfo("Registration Submitted", f"Success! Your request has been sent for Admin approval.\n\nYour Employee ID: {new_id}", parent=self.top)
            self.go_login()
        except Exception as e:
            messagebox.showerror("Error", f"Registration failed: {e}", parent=self.top)

    def verify_forgot(self):
        eid = self.forgot_eid_var.get().strip()
        self.forgot_phone_var.set("")
        phone = self.forgot_phone_var.get().strip()
        
        if not eid or not phone:
            messagebox.showerror("Input Required", "Please enter both ID and Phone.", parent=self.top)
            return
            
        cur.execute("SELECT name FROM employee WHERE emp_id=? AND contact_num=?", (eid, phone))
        row = cur.fetchone()
        if row:
            self.reset_eid = eid
            self.new_pw_var.set("")
            self.view_state = "reset"
            messagebox.showinfo("Identity Verified", f"Verified Staff: {row[0]}\nPlease set a new password.", parent=self.top)
            self.refresh_ui(force=True)
        else:
            messagebox.showerror("Verification Failed", "No matching Staff record found.", parent=self.top)

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
            messagebox.showinfo("Success", "✅ Staff password updated successfully!", parent=self.top)
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
        cur.execute("SELECT * FROM employee WHERE emp_id=? AND (password=? OR password=?)", (eid, hashed_pw, encrypted_pw))
        user_row = cur.fetchone()

        if user_row:
            if len(user_row) > 7 and user_row[7] == 0: # Check approved column (index 7)
                messagebox.showwarning("Access Denied", "Your account is pending Admin approval.\nPlease wait or contact the store manager.", parent=self.top)
                return

            self.cv.delete("all")
            # CRITICAL: Preserve the background canvas during transitions
            # Safe cleanup: unbind before destroying to prevent event leaks
            try:
                self.top.unbind("<Return>")
            except Exception: pass
            
            # CRITICAL: Stop background redraws and clear any 'ghost' images
            T.clear_bg_image(self.top)
            
            # Destroy ALL widgets to provide a clean POS interface
            for widget in tk.Misc.winfo_children(self.top):
                try:
                    widget.destroy()
                except: pass
                
            global username
            username = user_row[1]
            global page2
            page2 = bill_window(self.top)
            page2.time()
        else:
            messagebox.showerror("Error", "Incorrect ID or Password.")
            self.reg_pass.set("")

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

        if getattr(self.top, "current_view", "main_menu") != "pos_login":
            return

        self._last_size = curr_size
        self.cv.delete("ui_content")
        
        cx, cy = w / 2, h / 2
        # Dynamic Height: Compact for login/forgot, spacious for enrollment
        card_w = 440
        card_h = 680 if self.view_state == "register" else 520
        T.draw_glass_panel(self.cv, cx, cy + 32, card_w, card_h, opacity=0.8, color=(245, 245, 245), radius=45)
        
        # 3. Card Content
        y_start = cy - 155

        def reg_field(lbl, var, entry_ref, y_pos):
            self.cv.create_text(cx - 165, y_pos, text=lbl, font=(T.FONT_FAMILY, 11, "bold"), fill="#1A1A1A", anchor="w", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_pos + 32, 330, 42, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_pos + 32, window=entry_ref, width=300, height=28, tags="ui_content")
            return y_pos + 72

        if self.view_state == "login":
            # —— SIGN IN VIEW ——
            self.cv.create_text(cx, cy - 205, text="Staff Login", font=(T.FONT_FAMILY, 30, "bold"), fill=T.PRIMARY_DIM, anchor="n", tags="ui_content")
            self.cv.create_text(cx, y_start, text="Access the Point of Sale system.", 
                                font=T.FONT_UI_SM, fill="#333333", anchor="n", width=340, justify="center", tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 50, text="Employee ID", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 100, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 100, window=self.entry1, width=310, height=35, tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 145, text="Password", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 195, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 195, window=self.entry2, width=310, height=35, tags="ui_content")

            forgot_tag = "forgot_link"
            self.cv.create_text(cx + 170, y_start + 237, text="Forgot Password?", font=(T.FONT_FAMILY, 12, "bold"), fill=T.PRIMARY, 
                                anchor="e", tags=("ui_content", forgot_tag))
            self.cv.tag_bind(forgot_tag, "<Button-1>", self.go_forgot)
            T.bind_tag_hover(self.cv, forgot_tag)

            T.draw_pill_button(self.cv, cx, y_start + 295, 340, 60, text="Sign in", color=T.BTN_GREEN, command=self.login)

            reg_tag = "reg_link"
            self.cv.create_text(cx, y_start + 380, text="Don't have an account? Register here", font=(T.FONT_FAMILY, 12, "bold"), fill=T.PRIMARY, tags=("ui_content", reg_tag))
            self.cv.tag_bind(reg_tag, "<Button-1>", self.go_register)
            T.bind_tag_hover(self.cv, reg_tag)

            back_tag = "back_link"
            self.cv.create_text(cx, y_start + 415, text="← Back to Main", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, tags=("ui_content", back_tag))
            self.cv.tag_bind(back_tag, "<Button-1>", lambda e: self.exitt_login())
            T.bind_tag_hover(self.cv, back_tag)
            
            upd_tag = "check_update_link"
            self.cv.create_text(cx, y_start + 450, text="Check for Updates", font=(T.FONT_FAMILY, 10), fill=T.TEXT_SUB, tags=("ui_content", upd_tag))
            import updater
            self.cv.tag_bind(upd_tag, "<Button-1>", lambda e: updater.check_for_updates())
            T.bind_tag_hover(self.cv, upd_tag)


        elif self.view_state == "forgot":
            # —— VERIFICATION VIEW ——
            self.cv.create_text(cx, cy - 205, text="Verification", font=(T.FONT_FAMILY, 30, "bold"), fill=T.PRIMARY_DIM, anchor="n", tags="ui_content")
            self.cv.create_text(cx, y_start, text="Enter details to reset your password.", 
                                font=T.FONT_UI_SM, fill="#333333", anchor="n", width=340, justify="center", tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 50, text="Employee ID", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 100, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 100, window=self.entry_forgot_id, width=300, height=35, tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 145, text="Phone Number", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 195, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 195, window=self.entry_forgot_phone, width=300, height=35, tags="ui_content")

            T.draw_pill_button(self.cv, cx, y_start + 295, 340, 60, text="Verify Identity", color=T.BTN_GREEN, command=self.verify_forgot)

            back_tag = "back_to_login"
            self.cv.create_text(cx, y_start + 380, text="← Back to Login", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, tags=("ui_content", back_tag))
            self.cv.tag_bind(back_tag, "<Button-1>", self.go_login)
            T.bind_tag_hover(self.cv, back_tag)


        elif self.view_state == "reset":
            # —— RESET VIEW ——
            self.cv.create_text(cx, cy - 205, text="Set password", font=(T.FONT_FAMILY, 30, "bold"), fill=T.PRIMARY_DIM, anchor="n", tags="ui_content")
            self.cv.create_text(cx, y_start, text="Enter a new secure password.", 
                                font=T.FONT_UI_SM, fill="#333333", anchor="n", width=340, justify="center", tags="ui_content")

            self.cv.create_text(cx - 170, y_start + 70, text="New Password", font=(T.FONT_FAMILY, 13, "bold"), fill="#1A1A1A", anchor="nw", tags="ui_content")
            T.draw_rounded_shape(self.cv, cx, y_start + 120, 340, 50, color="#FFFFFF", outline="#E0E0E0", outline_width=1)
            self.cv.create_window(cx, y_start + 120, window=self.entry_new_pw, width=300, height=35, tags="ui_content")

            T.draw_pill_button(self.cv, cx, y_start + 295, 340, 60, text="Update Password", color=T.PRIMARY_DIM, command=self.finish_reset)
            
            back_tag = "cancel_reset"
            self.cv.create_text(cx, y_start + 380, text="Cancel Reset", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, tags=("ui_content", back_tag))
            self.cv.tag_bind(back_tag, "<Button-1>", self.go_login)

        elif self.view_state == "register":
            # —— REGISTER VIEW OVERHAUL ——
            y_r_start = cy - 250
            self.cv.create_text(cx, y_r_start, text="Staff Enrollment", font=(T.FONT_FAMILY, 28, "bold"), fill=T.PRIMARY_DIM, anchor="n", tags="ui_content")
            self.cv.create_text(cx, y_r_start + 45, text="Join the Real Mart team.", font=T.FONT_UI_SM, fill="#333333", anchor="n", tags="ui_content")
            
            y_r = y_r_start + 100
            y_r = reg_field("Full Name", self.reg_name, self.entry_reg_name, y_r)
            y_r = reg_field("Contact Number", self.reg_contact, self.entry_reg_contact, y_r)
            y_r = reg_field("Address", self.reg_address, self.entry_reg_address, y_r)
            y_r = reg_field("Aadhar Number", self.reg_aadhar, self.entry_reg_aadhar, y_r)
            y_r = reg_field("Set Password", self.reg_pass, self.entry_reg_pass, y_r)

            T.draw_pill_button(self.cv, cx, y_r + 20, 330, 55, text="Create Staff Account", color=T.BTN_GREEN, command=self.register_staff)
            
            back_tag = "back_from_reg"
            self.cv.create_text(cx, y_r + 75, text="← Back to Login", font=(T.FONT_FAMILY, 13, "bold"), fill=T.PRIMARY, anchor="n", tags=("ui_content", back_tag))
            self.cv.tag_bind(back_tag, "<Button-1>", self.go_login)

        # Dynamic Keyboard Navigation: Bind Enter key to the primary action of the current view
        try:
            if self.view_state == "login":
                self.top.bind("<Return>", self.login)
            elif self.view_state == "forgot":
                self.top.bind("<Return>", lambda e: self.verify_forgot())
            elif self.view_state == "reset":
                self.top.bind("<Return>", lambda e: self.finish_reset())
            elif self.view_state == "register":
                self.top.bind("<Return>", lambda e: self.register_staff())
        except Exception: pass

        # Group Icon (Common)
        self.cv.create_text(cx + 160, y_start + 445, text="👥", font=(T.FONT_FAMILY, 24), fill="#E0E0E0", anchor="se", tags="ui_content")

    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

class Item:
    def __init__(self, name, price, qty, original_price=None):
        self.product_name = name
        self.price = price # Discounted Price
        self.qty = qty
        self.original_price = original_price if original_price else price

class Cart:
    def __init__(self):
        self.items = []
        self.dictionary = {}

    def add_item(self, item):
        self.items.append(item)

    def remove_item(self):
        if self.items:
            self.items.pop()

    def remove_item_at(self, index):
        if 0 <= index < len(self.items):
            self.items.pop(index)

    def remove_items(self):
        self.items.clear()

    def total(self):
        total = 0.0
        for i in self.items:
            total += i.price * i.qty
        return total

    def savings(self):
        sav = 0.0
        for i in self.items:
            sav += (i.original_price - i.price) * i.qty
        return sav

    def isEmpty(self):
        if len(self.items)==0:
            return True
        
    def allCart(self):
        for i in self.items:
            if (i.product_name in self.dictionary):
                self.dictionary[i.product_name] += i.qty
            else:
                self.dictionary.update({i.product_name:i.qty})
    

def exitt():
    # 1. Determine the appropriate message
    if page2 and hasattr(page2, "cart") and not page2.cart.isEmpty():
        msg = "Are you sure you want to exit? Active sale data will be lost."
    else:
        msg = "Are you sure you want to exit to main menu?"
    
    # 2. Show the confirmation pop-up
    sure = messagebox.askyesno("Exit", msg, parent=biller)
    if not sure:
        return

    # 3. Handle session cleanup if logging out from active POS
    if page2 and hasattr(page2, "clear_session"):
        page2.clear_session()
    
    try:
        root.unbind("<Return>")
    except: pass

    if exit_to_main:
        exit_to_main()


class bill_window:
    def __init__(self, top=None):
        import uuid
        self.session_id = str(uuid.uuid4())[:8]
        try:
            self._init_ui(top)
        except Exception as e:
            import traceback
            err = f"POS Crash during startup:\n\n{str(e)}\n\nTraceback:\n{traceback.format_exc()}"
            print(err)
            messagebox.showerror("POS Startup Error", err)
            raise e

    def _init_ui(self, top):
        self.root = top
        top.geometry("1580x920")
        top.minsize(1220, 780)
        top.resizable(True, True)
        top.title("Real Mart · Point of sale")
        T.style_root(top)

        # Initialize variables
        self.preview_name = StringVar(value="")
        self.preview_phone = StringVar(value="")
        self.preview_bill = StringVar(value="")
        self.preview_date = StringVar(value="")
        self.preview_payment = StringVar(value="")
        self.preview_time = StringVar(value="")
        self.pay_method = StringVar(value="Cash")
        self.receipt_mode = StringVar(value="Print")
        self.cash_received = StringVar(value="")
        self.card_num_val = StringVar(value="")
        self.card_exp_val = StringVar(value="")
        self.card_name_val = StringVar(value="")
        self.active_upi_id = None
        
        # Reset global session variables
        if 'cust_name' in globals() and cust_name:
            cust_name.set("")
        if 'cust_num' in globals() and cust_num:
            cust_num.set("")
        if 'cust_search_bill' in globals() and cust_search_bill:
            cust_search_bill.set("")
            
        # --- Smart Coupon State ---
        self.coupon_var = StringVar()
        self.coupon_discount_val = 0.0
        self.applied_coupon_code = None
            
        self._grand_total = 0.0
        self.cart = Cart()
        self.state = 1
        self._qr_list = []
        self._qr_index = 0
        self._last_pay_method = "Cash"
        self._qr_timer_id = None
        self._qr_timer_val = 0
        self.loyalty_redemption_amt = 0.0
        self.current_bill_no = random_bill_number(8)

        hdr = Frame(top, bg=T.ORANGE, height=48)
        hdr.pack(fill=X)
        hdr.pack_propagate(False)
        h_inner = Frame(hdr, bg=T.ORANGE)
        h_inner.pack(fill=BOTH, expand=True, padx=16, pady=6)

        self.message = Label(
            h_inner,
            text=f"Logged in as: {username}",
            font=T.FONT_UI,
            bg=T.ORANGE,
            fg=T.WHITE,
        )
        self.message.pack(side=LEFT)

        self.clock = Label(
            h_inner,
            text="",
            font=T.FONT_UI,
            bg=T.ORANGE,
            fg=T.WHITE,
        )
        self.clock.pack(side=RIGHT, padx=(12, 8))

        self.button1 = Button(h_inner, text="Logout", command=exitt)
        self.button1.pack(side=RIGHT)
        T.btn_white_round(self.button1)
        def z_out():
            T.update_zoom(-1)
            T.setup_ttk(top)
            for widget in top.winfo_children(): widget.destroy()
            global page2
            page2 = bill_window(top)
            page2.time()
        def z_in():
            T.update_zoom(1)
            T.setup_ttk(top)
            for widget in top.winfo_children(): widget.destroy()
            global page2
            page2 = bill_window(top)
            page2.time()
            
        z2 = Button(h_inner, text="+", command=z_in, width=2)
        z2.pack(side=RIGHT, padx=(0,4))
        T.btn_secondary(z2)
        z1 = Button(h_inner, text="-", command=z_out, width=2)
        z1.pack(side=RIGHT, padx=(4,2))
        T.btn_secondary(z1)
    

        # --- REVERT: Reliable 3-Column Static Layout ---
        main = Frame(top, bg=T.BG_ROOT, padx=10, pady=6)
        main.pack(fill=BOTH, expand=True)

        # —— HEADER WITH SYNC STATUS ——
        main.pack(fill=BOTH, expand=True)
        
        left = Frame(main, bg=T.CARD, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=12, pady=12)
        left.pack(side=LEFT, fill=Y, padx=(0, 10))
        left.pack_propagate(False)
        left.configure(width=400)

        Label(left, text="Build the cart", font=T.FONT_TITLE, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        Label(left, text="Category → product → quantity", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(4, 12))

        text_font = T.FONT_UI_SM
        biller.option_add("*TCombobox*Listbox.font", text_font)
        biller.option_add("*TCombobox*Listbox.selectBackground", T.ORANGE)

        text_font = (T.FONT_FAMILY, 11)
        biller.option_add("*TCombobox*Listbox.font", text_font)
        biller.option_add("*TCombobox*Listbox.selectBackground", T.ORANGE)

        # --- Global Search Section ---
        search_f = Frame(left, bg=T.CARD)
        search_f.pack(fill=X, pady=(0, 24))
        Label(search_f, text="GLOBAL QUICK SEARCH", font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY).pack(anchor=W)
        self.search_var = StringVar()
        self.search_entry = Entry(search_f, textvariable=self.search_var, font=T.FONT_UI)
        self.search_entry.pack(fill=X, pady=(4, 0), ipady=8)
        T.entry_light(self.search_entry)
        self.search_entry.bind("<KeyRelease>", self._on_search_key)
        self.search_entry.bind("<FocusIn>", lambda e: self._on_search_key(e))
        self.search_entry.bind("<Return>", self._on_search_enter)
        self.search_entry.bind("<Down>", self._on_search_down)

        def on_camera_scan(data):
            self.last_scan_var.set(f"Last Scan: {data}")
            self.search_var.set(data)
            self._on_search_enter()

        self.last_scan_var = StringVar(value="Last Scan: None")
        Label(search_f, textvariable=self.last_scan_var, font=T.FONT_SMALL, bg=T.CARD, fg=T.ORANGE).pack(anchor=E)

        cam_btn = Button(search_f, text="📷 Scan via Camera", command=lambda: scanner_util.open_scanner(self.root, on_camera_scan, "POS Camera Scanner", continuous=True))
        cam_btn.pack(anchor=W, pady=(4, 0))
        T.btn_primary(cam_btn)
        
        # A listbox for real-time suggestions
        self.search_list_frame = Frame(left, bg=T.CARD)
        self.search_listbox = Listbox(self.search_list_frame, font=T.FONT_UI_SM, height=5, bg=T.WHITE, fg=T.PRIMARY_DIM, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        self.search_listbox.pack(fill=X)
        self.search_listbox.bind("<Return>", self._on_search_enter)
        self.search_listbox.bind("<Double-1>", self._on_search_enter)

        Label(left, text="Category", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        self.combo1 = ttk.Combobox(left, width=60, state="readonly", style="RM.TCombobox", font=text_font)
        self.combo1.pack(fill=X, pady=(4, 20))

        Label(left, text="Product", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        self.combo3 = ttk.Combobox(left, width=60, state="disabled", style="RM.TCombobox", font=text_font)
        self.combo3.pack(fill=X, pady=(4, 20))

        Label(left, text="Quantity", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        self.entry4 = ttk.Entry(left, width=60, state="disabled", style="RM.TEntry", font=text_font)
        self.entry4.pack(fill=X, pady=(4, 16))
        self.entry4.bind("<Return>", lambda e: self.add_to_cart())

        self.qty_label = Label(
            left,
            text="",
            font=T.FONT_UI_SM,
            bg=T.CARD,
            fg=T.ORANGE,
            anchor=W,
        )
        self.qty_label.pack(anchor=W, pady=(0, 10))

        row_btns = Frame(left, bg=T.CARD)
        row_btns.pack(fill=X, pady=(6, 0))
        self.button7 = Button(row_btns, text="Add to cart", command=lambda: self.add_to_cart())
        self.button7.pack(side=LEFT, padx=(0, 6))
        T.btn_primary(self.button7)
        self.button9 = Button(row_btns, text="Remove", command=self.remove_product)
        self.button9.pack(side=LEFT, padx=(0, 6))
        T.btn_secondary(self.button9)
        self.button9.configure(padx=8, pady=6)
        self.button8 = Button(row_btns, text="Reset pick", command=self.clear_selection)
        self.button8.pack(side=LEFT)
        T.btn_ghost(self.button8)
        self.button8.configure(bg=T.CARD, fg=T.TEXT_SUB)

        find_category = "SELECT DISTINCT product_cat FROM raw_inventory WHERE product_cat IS NOT NULL AND TRIM(product_cat) != ''"
        cur.execute(find_category)
        result1 = cur.fetchall()
        cat = [row[0] for row in result1]
        self.combo1.configure(values=cat)
        self.combo1.set("") 

        center = Frame(main, bg=T.BG_ROOT)
        center.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 12))
        
        right = Frame(main, bg=T.BG_ROOT, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        right.pack(side=LEFT, fill=BOTH, expand=True)

        # --- Moved: Find existing bill section to bottom of Left sidebar ---
        search_row = Frame(left, bg=T.CARD, padx=12, pady=10, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        search_row.pack(side=BOTTOM, fill=X, pady=(12, 0))
        Label(
            search_row,
            text="FIND BILL",
            font=T.FONT_SECTION,
            bg=T.CARD,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W)
        sr = Frame(search_row, bg=T.CARD)
        sr.pack(fill=X, pady=(6, 0))
        self.entry3 = Entry(sr, textvariable=cust_search_bill, width=18)
        self.entry3.pack(side=LEFT, padx=(0, 6), ipady=6)
        T.entry_light(self.entry3)
        self.button2 = Button(sr, text="Search", command=self.search_bill)
        self.button2.pack(side=LEFT)
        T.btn_primary(self.button2)
        self.button2.configure(padx=6, pady=4)

        cust_card = Frame(center, bg=T.CARD, padx=12, pady=10)
        cust_card.pack(side=TOP, fill=X, pady=(0, 6))
        Label(
            cust_card,
            text="Customer",
            font=T.FONT_SECTION,
            bg=T.CARD,
            fg=T.TEXT_ON_LIGHT,
        ).pack(anchor=W)
        grid_c = Frame(cust_card, bg=T.CARD)
        grid_c.pack(fill=X, pady=(10, 0))
        Label(grid_c, text="Name", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
        self.entry1 = Entry(grid_c, textvariable=cust_name, width=60, font=(T.FONT_FAMILY, 11))
        self.entry1.pack(anchor=W, pady=(4, 12), ipady=12, fill=X)
        T.entry_light(self.entry1)
        
        Label(grid_c, text="Phone number", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W)
        self.entry2 = Entry(grid_c, textvariable=cust_num, width=60, font=(T.FONT_FAMILY, 11))
        self.entry2.pack(anchor=W, pady=(4, 0), ipady=12, fill=X)
        T.entry_light(self.entry2)
        cust_num.trace_add("write", self.update_loyalty_info)

        # --- LOYALTY STATUS CARD ---
        self.loyalty_frame = Frame(cust_card, bg="#E8F5E9", padx=12, pady=10, highlightthickness=1, highlightbackground="#81C784")
        # Hidden by default
        
        self.loyalty_points_var = StringVar(value="Points: 0")
        self.loyalty_value_var = StringVar(value="Value: ₹0.00")
        
        Label(self.loyalty_frame, text="💎 LOYALTY MEMBER", font=(T.FONT_FAMILY, 9, "bold"), bg="#E8F5E9", fg="#2E7D32").pack(anchor=W)
        l_row = Frame(self.loyalty_frame, bg="#E8F5E9")
        l_row.pack(fill=X, pady=5)
        Label(l_row, textvariable=self.loyalty_points_var, font=T.FONT_UI, bg="#E8F5E9", fg="#1B5E20").pack(side=LEFT)
        Label(l_row, textvariable=self.loyalty_value_var, font=T.FONT_UI_SM, bg="#E8F5E9", fg="#388E3C").pack(side=LEFT, padx=15)
        
        btn_redeem = Button(self.loyalty_frame, text="Redeem Points", command=self.redeem_loyalty, bg="#2E7D32", fg="white", font=T.FONT_UI_SM, relief=FLAT, padx=8)
        btn_redeem.pack(side=RIGHT)

        # --- Smart Coupon Section ---
        coupon_card = Frame(center, bg=T.CARD, padx=12, pady=10)
        coupon_card.pack(side=TOP, fill=X, pady=(0, 6))
        Label(coupon_card, text="Smart Coupon", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        
        cpf = Frame(coupon_card, bg=T.CARD)
        cpf.pack(fill=X, pady=(8, 0))
        self.entry_coupon = Entry(cpf, textvariable=self.coupon_var, width=20)
        self.entry_coupon.pack(side=LEFT, padx=(0, 10), ipady=6)
        T.entry_light(self.entry_coupon)
        
        self.btn_apply_coupon = Button(cpf, text="Apply", command=self.apply_coupon)
        self.btn_apply_coupon.pack(side=LEFT)
        T.btn_primary(self.btn_apply_coupon)
        
        self.coupon_status = Label(coupon_card, text="Enter coupon code for extra discount", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB)
        self.coupon_status.pack(anchor=W, pady=(4, 0))

        cart_lab = Label(
            right,
            text="Line items",
            font=T.FONT_SECTION,
            bg=T.BG_ROOT,
            fg=T.TEXT_ON_LIGHT,
            anchor=W,
        )
        cart_lab.pack(side=TOP, fill=X, pady=(0, 2))

        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", background=T.CARD, foreground=T.TEXT_ON_LIGHT, rowheight=28, fieldbackground=T.CARD, borderwidth=0, font=T.FONT_UI_SM)
        style.map("Treeview", background=[("selected", T.ORANGE)])
        style.configure("Treeview.Heading", background=T.CARD_SOFT, foreground=T.TEXT_SUB, font=T.FONT_SECTION)
        
        self.tree = ttk.Treeview(right, columns=("Product", "Qty", "MRP", "Discount", "Total"), show="headings", height=8, selectmode="browse")
        self.tree.pack(side=TOP, fill=BOTH, expand=True, pady=(0, 4))
        self.tree.heading("Product", text="Product Name", anchor=CENTER)
        self.tree.heading("Qty", text="Qty", anchor=CENTER)
        self.tree.heading("MRP", text="MRP (Rs.)", anchor=CENTER)
        self.tree.heading("Discount", text="Disc. (Rs.)", anchor=CENTER)
        self.tree.heading("Total", text="Total (Rs.)", anchor=CENTER)

        self.tree.column("Product", anchor=CENTER, width=280, stretch=YES)
        self.tree.column("Qty", anchor=CENTER, width=60, stretch=NO)
        self.tree.column("MRP", anchor=CENTER, width=100, stretch=NO)
        self.tree.column("Discount", anchor=CENTER, width=100, stretch=NO)
        self.tree.column("Total", anchor=CENTER, width=110, stretch=NO)
        T.apply_zebra_styling(self.tree)
        
        # Grand Total Display
        self.total_label = Label(
            right,
            text="Net Payable: Rs. 0.00",
            font=T.FONT_SECTION,
            bg=T.BG_ROOT,
            fg=T.PRIMARY_DIM,
        )
        self.total_label.pack(side=TOP, anchor=E, pady=(0, 2))
        
        self.gst_label = Label(
            right,
            text="Incl. GST (5%): Rs. 0.00",
            font=T.FONT_UI_SM,
            bg=T.BG_ROOT,
            fg=T.TEXT_SUB,
        )
        self.gst_label.pack(side=TOP, anchor=E, pady=(0, 4))
        
        self.savings_label = Label(
            right,
            text="Total Savings: Rs. 0.00",
            font=T.FONT_UI_SM,
            bg=T.BG_ROOT,
            fg=T.BTN_GREEN,
        )
        self.savings_label.pack(side=TOP, anchor=E, pady=(0, 4))

        Label(right, text="Live Receipt Preview", font=T.FONT_UI_SM, bg=T.BG_ROOT, fg=T.TEXT_SUB).pack(side=TOP, anchor=W, pady=(8, 0))
        self.live_preview = tkst.ScrolledText(right, font=("Courier New", 10), bg=T.WHITE, fg=T.PRIMARY_DIM, height=15, borderwidth=1, relief=FLAT)
        self.live_preview.pack(side=TOP, fill=BOTH, expand=True, pady=(4, 12))
        self.live_preview.configure(state="disabled")

        actions = Frame(right, bg=T.BG_ROOT)
        actions.pack(side=TOP, fill=X)
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)

        # Enlarged Primary Buttons
        actions.columnconfigure(1, weight=1)
        actions.columnconfigure(2, weight=1)
        actions.columnconfigure(3, weight=1)
        
        self.button4 = Button(actions, text="GENERATE BILL", command=self.gen_bill)
        self.button4.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(0, 2), pady=(0, 10), ipady=12)
        T.btn_primary(self.button4)
        self.button4.configure(font=(T.FONT_FAMILY, 12, "bold"))

        self.button5 = Button(actions, text="CLEAR BILL", command=self.clear_bill)
        self.button5.grid(row=1, column=1, columnspan=2, sticky="ew", padx=(0, 2), pady=(0, 2), ipady=8)
        T.btn_secondary(self.button5)
        self.button5.configure(font=T.FONT_UI_SM)

        pay_card = Frame(center, bg=T.CARD, padx=12, pady=10)
        pay_card.pack(side=TOP, fill=X, pady=(0, 2))
        Label(pay_card, text="Payment", font=T.FONT_SECTION, bg=T.CARD, fg=T.TEXT_ON_LIGHT).pack(anchor=W)
        rf = Frame(pay_card, bg=T.CARD)
        rf.pack(fill=X, pady=(2, 0))
        pay_opts = [("Cash", "Cash"), ("UPI / QR", "UPI"), ("Card", "Card")]
        for i, (txt, val) in enumerate(pay_opts):
            rb = Radiobutton(rf, text=txt, variable=self.pay_method, value=val, bg=T.CARD, font=T.FONT_UI_SM, command=self._on_pay_method)
            rb.pack(side=LEFT, padx=(0, 10))

        # --- DIGITAL RECEIPT PANEL ---
        wa_f = Frame(pay_card, bg="#E8F5E9", padx=12, pady=12, highlightthickness=1, highlightbackground="#C8E6C9")
        wa_f.pack(fill=X, pady=(15, 0))
        
        Label(wa_f, text="🌱 Scan-to-Download Ready", font=(T.FONT_FAMILY, 10, "bold"), bg="#E8F5E9", fg="#2E7D32").pack(anchor=W)
        Label(wa_f, text="A digital QR code will appear after checkout for the customer to scan and download their bill.", font=T.FONT_SMALL, bg="#E8F5E9", fg="#388E3C", wraplength=250, justify=LEFT).pack(anchor=W, pady=(5,0))

        self.cash_pay_frame = Frame(pay_card, bg=T.CARD)
        # QR Container (Back to Payment Section in middle column)
        self.qr_container = Frame(pay_card, bg=T.CARD)
        # We don't pack it yet; it will be packed by _on_pay_method
        
        self.combo1.bind("<<ComboboxSelected>>", self.get_category)
        
        # Live Binds for Real-time Preview
        cust_name.trace_add("write", lambda *a: self._refresh_live_preview())
        cust_num.trace_add("write", lambda *a: self._refresh_live_preview())
        self.pay_method.trace_add("write", lambda *a: self._refresh_live_preview())
        
        self._on_pay_method()
        self._refresh_live_preview()
        
        # Auto-focus search for immediate scanning
        self.search_entry.focus_set()

        # —— DISCREET FOOTER STATUS ——
        self.footer = Frame(top, bg="#F5F7F5", height=24)
        self.footer.pack(side=BOTTOM, fill=X)
        self.footer.pack_propagate(False)
        
        self.sync_f = Frame(self.footer, bg="#F5F7F5")
        self.sync_f.pack(side=RIGHT, padx=15)
        self.sync_dot = Label(self.sync_f, text="●", font=(T.FONT_FAMILY, 10), bg="#F5F7F5", fg="#4CAF50")
        self.sync_dot.pack(side=LEFT)
        self.sync_lbl = Label(self.sync_f, text="SYNCED", font=(T.FONT_FAMILY, 9), bg="#F5F7F5", fg=T.TEXT_SUB)
        self.sync_lbl.pack(side=LEFT, padx=5)
        
        Label(self.footer, text="Billing Station · Network Active", font=(T.FONT_FAMILY, 9), bg="#F5F7F5", fg=T.TEXT_MUTED).pack(side=LEFT, padx=15)
        
        # —— UPDATE CHECKER (Manual trigger for Terminals) ——
        def manual_check():
            import updater
            updater.check_for_updates()
            
        self.update_btn = Button(self.footer, text="Check for Updates", font=(T.FONT_FAMILY, 8), bg="#F5F7F5", fg=T.PRIMARY, 
                                 relief="flat", cursor="hand2", command=manual_check, padx=5)
        self.update_btn.pack(side=LEFT, padx=5)
        
        def on_h_upd(e): self.update_btn.config(fg=T.PRIMARY_LIGHT, underline=True)
        def on_l_upd(e): self.update_btn.config(fg=T.PRIMARY, underline=False)
        self.update_btn.bind("<Enter>", on_h_upd)
        self.update_btn.bind("<Leave>", on_l_upd)
        
        self.check_sync()
        self.heartbeat()
        self.check_broadcast()

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
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.after(30000, self.check_sync)

    def heartbeat(self):
        import db_manager, socket
        try:
            db = db_manager.connect()
            pc_name = socket.gethostname()
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                pc_ip = s.getsockname()[0]
                s.close()
            except:
                pc_ip = socket.gethostbyname(pc_name)
                
            db.execute("REPLACE INTO active_sessions (session_id, pc_name, pc_ip, role, user_name, last_seen) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)", 
                       (self.session_id, pc_name, pc_ip, "POS Terminal", "Active Staff"))
            db.commit()
        except:
            pass
            
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.after(60000, self.heartbeat)

    def check_broadcast(self):
        import db_manager
        try:
            db = db_manager.connect()
            cur = db.execute("SELECT message FROM broadcast_messages WHERE is_active=1 ORDER BY sent_at DESC LIMIT 1")
            res = cur.fetchone()
            
            if res:
                msg = res[0]
                if not hasattr(self, "b_banner") or not self.b_banner.winfo_exists():
                    # Create high-visibility banner at bottom
                    self.b_banner = Frame(self.root, bg="#FFF9C4", height=45, highlightthickness=1, highlightbackground="#FBC02D")
                    self.b_banner.pack(side=BOTTOM, fill=X, before=self.footer)
                    self.b_lbl = Label(self.b_banner, text=f"📢 MESSAGE FROM ADMIN: {msg}", font=(T.FONT_FAMILY, 11, "bold"), bg="#FFF9C4", fg="#5D4037")
                    self.b_lbl.pack(pady=10)
                else:
                    self.b_lbl.config(text=f"📢 MESSAGE FROM ADMIN: {msg}")
            else:
                if hasattr(self, "b_banner") and self.b_banner.winfo_exists():
                    self.b_banner.destroy()
                    delattr(self, "b_banner")
        except:
            pass
            
        if hasattr(self, "root") and self.root.winfo_exists():
            self.root.after(30000, self.check_broadcast)

    def clear_session(self):
        import db_manager
        try:
            db = db_manager.connect()
            db.execute("DELETE FROM active_sessions WHERE session_id=?", (self.session_id,))
            db.commit()
        except:
            pass

    def _on_pay_method(self):
        m = self.pay_method.get()
        
        # Cycle QR if UPI is clicked again
        if m == "UPI" and self._last_pay_method == "UPI":
            self._qr_index += 1
            self._draw_payment_qr()
            return

        self._last_pay_method = m
        # Clean current cash container
        for w in self.cash_pay_frame.winfo_children():
            w.destroy()
            
        if m == "Cash":
            self.cash_pay_frame.pack(fill=X, pady=(4, 0))
            self.qr_container.pack_forget()
            
            Label(self.cash_pay_frame, text="Cash received (Rs.)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(10, 4))
            ce = Entry(self.cash_pay_frame, textvariable=self.cash_received, width=20)
            ce.pack(anchor=W, ipady=6)
            T.entry_light(ce)
            ce.bind("<KeyRelease>", lambda e: self._update_change_display())
            
            self.change_display = Label(self.cash_pay_frame, text="Change to return: Rs. 0.00", font=T.FONT_UI, bg=T.CARD, fg=T.PRIMARY_LIGHT, anchor=W)
            self.change_display.pack(anchor=W, pady=(8, 0))
            self._update_change_display()
            
        elif m == "Card":
            self.cash_pay_frame.pack(fill=X, pady=(4, 0))
            self.qr_container.pack_forget()
            
            Label(self.cash_pay_frame, text="Card Holder Name", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(2, 2))
            c_name = Entry(self.cash_pay_frame, textvariable=self.card_name_val, width=28)
            c_name.pack(anchor=W, ipady=4, fill=X, padx=(0, 20))
            T.entry_light(c_name)

            Label(self.cash_pay_frame, text="Card Number (16 digits)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).pack(anchor=W, pady=(8, 2))
            c_num = Entry(self.cash_pay_frame, textvariable=self.card_num_val, width=28)
            c_num.pack(anchor=W, ipady=4)
            T.entry_light(c_num)
            
            f = Frame(self.cash_pay_frame, bg=T.CARD)
            f.pack(anchor=W, pady=(8,0))
            Label(f, text="Expiry (MM/YY)", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(row=0,column=0, sticky=W)
            c_exp = Entry(f, textvariable=self.card_exp_val, width=12)
            c_exp.grid(row=1,column=0, sticky=W, padx=(0,12), ipady=4)
            T.entry_light(c_exp)
            
            Label(f, text="CVV", font=T.FONT_UI_SM, bg=T.CARD, fg=T.TEXT_SUB).grid(row=0,column=1, sticky=W)
            c_cvv = Entry(f, width=8, show="*")
            c_cvv.grid(row=1,column=1, sticky=W, ipady=4)
            T.entry_light(c_cvv)
            
        elif m == "UPI":
            self.cash_pay_frame.pack_forget()
            self.qr_container.pack(fill=X, pady=(10, 0))
            self._qr_index = 0 # Reset to first on initial switch
            self._draw_payment_qr()
        else:
            self._stop_qr_timer()
            self.cash_pay_frame.pack_forget()
            self.qr_container.pack_forget()
            
    def _draw_payment_qr(self):
        # Stop existing timer
        self._stop_qr_timer()

        # Clear container
        for w in self.qr_container.winfo_children():
            w.destroy()

        # 0. Zero Check
        if self._grand_total <= 0:
            card = Frame(self.qr_container, bg=T.CARD_SOFT, highlightthickness=1, highlightbackground=T.BORDER_SUBTLE, padx=20, pady=20)
            card.pack(fill=X)
            Label(card, text="Cart is empty", font=T.FONT_SECTION, bg=T.CARD_SOFT, fg=T.TEXT_SUB).pack()
            Label(card, text="Please add items to generate payment QR.", font=T.FONT_UI_SM, bg=T.CARD_SOFT, fg=T.TEXT_MUTED).pack(pady=(4,0))
            return
            
        # 1. Fetch active UPI ID from DB
        try:
            cur.execute("SELECT upi_id, filename, payee_name FROM payment_config ORDER BY qr_id ASC")
            options = cur.fetchall()
        except Exception as e:
            print(f"DB Load error: {e}")
            options = []

        if not options:
            card = Frame(self.qr_container, bg=T.CARD, highlightthickness=1, highlightbackground="#FFCCBC", padx=12, pady=12)
            card.pack(fill=X)
            Label(card, text="No UPI ID configured.", font=T.FONT_UI_SM, bg=T.CARD, fg="#D84315").pack()
            return

        # Ensure index is within bounds
        idx = self._qr_index % len(options)
        upi_id, qr_filename, payee_name = options[idx]
        if not upi_id: 
            upi_id = "merchant@upi" # Failsafe
        if not payee_name:
            payee_name = "Real Mart"
            
        display_upi = upi_id
        if len(display_upi) > 28: display_upi = display_upi[:25] + "..."

        card = Frame(self.qr_container, bg=T.CARD, highlightthickness=1, highlightbackground=T.PRIMARY_LIGHT, padx=12, pady=12)
        card.pack(fill=X)
        
        self.active_upi_id = upi_id
        Label(card, text=display_upi, font=T.FONT_SECTION, bg=T.CARD, fg=T.PRIMARY_DIM).pack()
        
        # 2. Generate Dynamic UPI URI
        # upi://pay?pa=商户收款账号&pn=商户名称&am=金额&cu=币种&tn=交易说明
        amount = f"{self._grand_total:.2f}"
        note = f"Bill_{self.current_bill_no}"
        upi_uri = f"upi://pay?pa={upi_id}&pn={payee_name}&am={amount}&cu=INR&tn={note}"
        
        rendered = False
        try:
            # Try dynamic generation with qrcode library
            qr = qrcode.QRCode(version=1, box_size=10, border=2)
            qr.add_data(upi_uri)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")
            
            # Resize for UI
            from PIL import Image, ImageTk
            qr_img = qr_img.resize((170, 170), Image.Resampling.LANCZOS)
            self.qr_photo = ImageTk.PhotoImage(qr_img)
            
            img_lb = Label(card, image=self.qr_photo, bg=T.WHITE)
            img_lb.pack(pady=(8, 4))
            img_lb.image = self.qr_photo
            rendered = True
            Label(card, text=f"Amount: Rs. {amount}", font=T.FONT_BTN, bg=T.CARD, fg=T.PRIMARY).pack()
        except Exception as e:
            print(f"Dynamic QR Error: {e}")
            # Fallback to static image if configured
            if qr_filename:
                path = T.get_resource_path(os.path.join("images", "qrs", qr_filename))
                if os.path.exists(path):
                    try:
                        from PIL import Image, ImageTk
                        img = Image.open(path).convert("RGB")
                        img.thumbnail((180, 180), Image.Resampling.LANCZOS)
                        self.qr_photo = ImageTk.PhotoImage(img)
                        img_lb = Label(card, image=self.qr_photo, bg=T.WHITE)
                        img_lb.pack(pady=8)
                        img_lb.image = self.qr_photo
                        rendered = True
                    except Exception: pass

        if not rendered:
            fallback = Frame(card, bg=T.CARD_SOFT, padx=10, pady=10)
            fallback.pack(fill=X, pady=8)
            Label(fallback, text="⚠️ Using text payment", font=T.FONT_UI_SM, bg=T.CARD_SOFT, fg="#D32F2F").pack()
            Label(fallback, text="Please pay to the ID above.", font=T.FONT_SMALL, bg=T.CARD_SOFT, fg=T.TEXT_SUB).pack()
        
        Label(card, text="Scan to pay via Any UPI App", font=T.FONT_SMALL, bg=T.CARD, fg=T.TEXT_SUB).pack(pady=(4,0))
        
        # 3. Start Expiry Timer (5 Mins)
        timer_frame = Frame(card, bg=T.CARD)
        timer_frame.pack(pady=(12, 0))
        self.qr_timer_label = Label(timer_frame, text="Expires in: 05:00", font=T.FONT_UI_SM, bg=T.CARD, fg=T.PRIMARY)
        self.qr_timer_label.pack()
        
        self._qr_timer_val = 300
        self._run_qr_timer()

    def _stop_qr_timer(self):
        if self._qr_timer_id:
            self.root.after_cancel(self._qr_timer_id)
            self._qr_timer_id = None

    def _run_qr_timer(self):
        if self._qr_timer_val <= 0:
            # Expire
            for w in self.qr_container.winfo_children():
                if isinstance(w, Frame): # The QR card
                    for child in w.winfo_children():
                        if isinstance(child, Label) and child.cget("image"):
                            child.configure(image="", text="EXPIRED", font=T.FONT_HERO, fg="#B71C1C", height=5)
                        if "timer" in str(child) or (isinstance(child, Label) and "Expires" in child.cget("text")):
                             child.configure(text="Payment link expired. Please refresh.", fg="#B71C1C", font=T.FONT_UI_SM)
            return

        self._qr_timer_val -= 1
        mins, secs = divmod(self._qr_timer_val, 60)
        time_str = f"Expires in: {mins:02d}:{secs:02d}"
        
        try:
            self.qr_timer_label.config(text=time_str)
            # Change color to warning if under 1 minute
            if self._qr_timer_val < 60:
                self.qr_timer_label.config(fg="#D32F2F")
        except Exception: pass # Frame might be destroyed

        self._qr_timer_id = self.root.after(1000, self._run_qr_timer)

    def _update_change_display(self):
        if self.pay_method.get() != "Cash":
            return
        try:
            tendered = float(self.cash_received.get().strip() or "0")
        except ValueError:
            self.change_display.configure(text="Enter a valid cash amount", fg=T.TEXT_SUB)
            return
        g = self._grand_total
        ch = tendered - g
        if ch >= 0:
            self.change_display.configure(
                text="Change to return: Rs. {:.2f}".format(ch),
                fg=T.PRIMARY_LIGHT,
            )
        else:
            self.change_display.configure(
                text="Amount still due: Rs. {:.2f}".format(-ch),
                fg="#c0392b",
            )

    def get_category(self, Event):
        self.combo3.configure(state="readonly")
        self.combo3.set("")
        cat = self.combo1.get().strip()
        find_product = (
            "SELECT product_name FROM raw_inventory WHERE TRIM(product_cat) = ? ORDER BY product_name"
        )
        cur.execute(find_product, [cat])
        result3 = cur.fetchall()
        pro = [row[0] for row in result3]
        self.combo3.configure(values=pro)
        self.combo3.bind("<<ComboboxSelected>>", self.show_qty)
        self.entry4.configure(state="disabled")
        self.qty_label.configure(text="", bg=T.CARD)

    def show_qty(self, Event):
        product_name = self.combo3.get()
        if not product_name:
            return
        self.entry4.configure(state="normal")
        find_qty = "SELECT stock FROM raw_inventory WHERE product_name = ?"
        cur.execute(find_qty, [product_name])
        results = cur.fetchone()
        if results:
            self.qty_label.configure(
                text="In stock: {}".format(results[0]),
                fg=T.ORANGE,
                bg=T.CARD,
            )
        else:
            self.qty_label.configure(text="Product no found", fg="#c0392b")

    def fetch_product_info(self, barcode):
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
                    cat = product.get("categories", "").split(",")[0] 
                    return name, cat
        except Exception as e:
            print(f"API Lookup error: {e}")
        return None, None

    def is_expired(self, expiry_str, product_name):
        if not expiry_str or expiry_str.strip().upper() == "N/A":
            return False
        try:
            # Expected format: YYYY-MM-DD
            exp_date = datetime.strptime(expiry_str.strip(), "%Y-%m-%d").date()
            if exp_date < date.today():
                messagebox.showerror("Product Expired", f"Product '{product_name}' has expired on {expiry_str}.\nIt cannot be added to the cart.", parent=biller)
                return True
            return False
        except:
            # If format is invalid, we log it but don't block (to avoid breaking the POS for older entries)
            print(f"Invalid expiry format for {product_name}: {expiry_str}")
            return False

    def apply_coupon(self):
        code = self.coupon_var.get().strip().upper()
        if not code:
            return
            
        cur.execute("SELECT discount_value, discount_type, min_bill, expiry_date, is_used FROM coupons WHERE coupon_code = ?", (code,))
        res = cur.fetchone()
        
        if not res:
            self.coupon_status.config(text="❌ Invalid coupon code.", fg="#c0392b")
            self.coupon_discount_val = 0.0
            self.applied_coupon_code = None
            self.update_total()
            return
            
        val, ctype, min_bill, expiry, used = res
        
        if used:
            self.coupon_status.config(text="❌ Coupon already used.", fg="#c0392b")
            self.coupon_discount_val = 0.0
            self.applied_coupon_code = None
            self.update_total()
            return
            
        try:
            exp_date = datetime.strptime(expiry, "%Y-%m-%d").date()
            if exp_date < date.today():
                self.coupon_status.config(text=f"❌ Coupon expired on {expiry}.", fg="#c0392b")
                self.coupon_discount_val = 0.0
                self.applied_coupon_code = None
                self.update_total()
                return
        except: pass
        
        # Check current subtotal
        subtotal = self.cart.total()
        if subtotal < min_bill:
            self.coupon_status.config(text=f"❌ Min bill for this coupon is Rs. {min_bill:.0f}.", fg="#c0392b")
            self.coupon_discount_val = 0.0
            self.applied_coupon_code = None
            self.update_total()
            return
            
        # Apply discount
        self.applied_coupon_code = code
        if ctype == "Percentage":
            self.coupon_discount_val = (val / 100.0) * subtotal
        else:
            self.coupon_discount_val = val
            
        self.coupon_status.config(text=f"✅ Applied! Rs. {self.coupon_discount_val:.2f} off.", fg=T.BTN_GREEN)
        self.update_total()
        self._refresh_live_preview()

    def update_loyalty_info(self, *args):
        phone = cust_num.get().strip()
        if len(phone) >= 10:
            try:
                cur.execute("SELECT points FROM loyalty_points WHERE phone=?", (phone,))
                res = cur.fetchone()
                if res:
                    pts = float(res[0])
                    cur.execute("SELECT `value` FROM loyalty_config WHERE `key`='point_value_rs'")
                    cv = cur.fetchone()
                    rs_val = float(cv[0]) if cv else 0.5
                    
                    self.loyalty_points_var.set(f"Points: {pts:.1f}")
                    self.loyalty_value_var.set(f"Value: ₹{pts * rs_val:.2f}")
                    self.loyalty_frame.pack(fill=X, pady=(10, 0))
                else:
                    self.loyalty_frame.pack_forget()
            except: pass
        else:
            self.loyalty_frame.pack_forget()

    def redeem_loyalty(self):
        phone = cust_num.get().strip()
        if not phone: return
        try:
            cur.execute("SELECT points FROM loyalty_points WHERE phone=?", (phone,))
            res = cur.fetchone()
            if not res or float(res[0]) <= 0:
                messagebox.showwarning("No Points", "This customer has no points to redeem.", parent=biller)
                return
            
            pts = float(res[0])
            cur.execute("SELECT `value` FROM loyalty_config WHERE `key`='point_value_rs'")
            cv = cur.fetchone()
            rs_val = float(cv[0]) if cv else 0.5
            
            redeem_amt = pts * rs_val
            if redeem_amt > self._grand_total:
                redeem_amt = self._grand_total
            
            self.loyalty_redemption_amt = redeem_amt
            self.update_total()
            messagebox.showinfo("Redeemed", f"₹{redeem_amt:.2f} redeemed from loyalty points!", parent=biller)
        except: pass

    def get_flash_discount(self, category):
        import datetime
        try:
            now = datetime.datetime.now().strftime("%H:%M")
            cur.execute("SELECT discount_percent FROM flash_sales WHERE category=? AND is_active=1 AND start_time <= ? AND end_time >= ?", (category, now, now))
            res = cur.fetchone()
            return float(res[0]) if res else 0.0
        except: return 0.0

    def get_last_chance_discount(self, product_name):
        try:
            # 1. Fetch Config
            cur.execute("SELECT `value` FROM last_chance_config WHERE `key`='enabled'")
            res_en = cur.fetchone()
            if not res_en or res_en[0] != '1': return 0.0
            
            cur.execute("SELECT `value` FROM last_chance_config WHERE `key`='threshold_days'")
            res_t = cur.fetchone()
            t_days = int(res_t[0] or 7) if res_t else 7
            
            cur.execute("SELECT `value` FROM last_chance_config WHERE `key`='discount_percent'")
            res_d = cur.fetchone()
            d_pct = float(res_d[0] or 50) if res_d else 50.0

            # 2. Check Expiry
            cur.execute("SELECT expiry_date FROM raw_inventory WHERE product_name=?", (product_name,))
            res_exp = cur.fetchone()
            if not res_exp: return 0.0
            exp_str = res_exp[0]
            if not exp_str or exp_str == "N/A": return 0.0
            
            import datetime
            exp = datetime.datetime.strptime(exp_str, "%Y-%m-%d").date()
            today = datetime.date.today()
            diff = (exp - today).days
            if diff >= 0 and diff <= t_days:
                return d_pct
        except Exception as e: 
            print(f"Last Chance Calc Error: {e}")
        return 0.0

    def add_to_cart(self):
        try:
            if self.state == 0:
                self.clear_bill()
            
            product_name = self.combo3.get().strip()
            if product_name != "":
                product_qty = self.entry4.get().strip()
                # MySQL can be case-sensitive; use LOWER for safety
                find_mrp = "SELECT mrp, stock, expiry_date, offer_type, offer_value, product_cat FROM raw_inventory WHERE LOWER(product_name) = LOWER(?)"
                try:
                    cur.execute(find_mrp, [product_name])
                    results = cur.fetchall()
                except Exception as e:
                    import traceback
                    error_trace = traceback.format_exc()
                    print(f"DATABASE ERROR in add_to_cart: {e}\n{error_trace}")
                    messagebox.showerror("Database Error", f"Failed to fetch product data: {e}\nCheck terminal for details.", parent=biller)
                    return

                if not results:
                    messagebox.showerror("Error", f"Product '{product_name}' was not found in the inventory database.\n\nPlease check the name and try again.", parent=biller)
                    return
                mrp = float(results[0][0])
                stock = int(results[0][1])
                expiry = results[0][2]
                off_type = results[0][3] or "None"
                off_val = float(results[0][4] or 0.0)
                p_cat = results[0][5]
                
                # Check for expiry before adding
                expired = self.is_expired(expiry, product_name)
                if expired:
                    return
                
                if product_qty.isdigit() == True:
                    req_qty = int(product_qty)
                    if req_qty > stock:
                        req_qty = stock
                        if req_qty <= 0:
                            messagebox.showerror("Out of Stock", "Product is completely out of stock.", parent=biller)
                            return
                        messagebox.showinfo("Limit Reached", f"Only {stock} available. Added {stock} to cart.", parent=biller)
                    
                    # NEW: Last Chance Discount (Expiring soon)
                    lc_pct = self.get_last_chance_discount(product_name)
                    total_off_pct = 0.0
                    if off_type == "Percentage":
                        total_off_pct += off_val
                    
                    # Add Happy Hour
                    total_off_pct += self.get_flash_discount(p_cat)
                    
                    # Add Last Chance (High priority)
                    is_last_chance = False
                    if lc_pct > 0:
                        total_off_pct += lc_pct
                        is_last_chance = True
                    
                    if total_off_pct > 90: total_off_pct = 90
                    
                    final_price = mrp * (1.0 - total_off_pct / 100.0)
                    if off_type == "Flat Discount" and not is_last_chance:
                        final_price -= off_val
                    
                    if final_price < 0: final_price = 0.0
                    
                    sp = final_price * req_qty
                    discount_per_unit = mrp - final_price
                    item = Item(product_name, final_price, req_qty, original_price=mrp)
                    self.cart.add_item(item)
                    # DISPLAY: Show Product, Qty, MRP, Discount, and Line Total
                    tag = "even" if len(self.tree.get_children()) % 2 == 0 else "odd"
                    self.tree.insert("", END, values=(product_name, req_qty, f"{mrp:.2f}", f"{discount_per_unit:.2f}", f"{sp:.2f}"), tags=(tag,))
                    self.clear_selection()
                    self.update_total()
                    self._refresh_live_preview()
                else:
                    messagebox.showerror("Oops!", "Invalid quantity.", parent=biller)
            else:
                messagebox.showerror("Oops!", "Choose a product.", parent=biller)
        except Exception as e:
            import traceback
            messagebox.showerror("CRASH!", f"Error: {e}\n\n{traceback.format_exc()}")

    def remove_product(self):
        selected = self.tree.selection()
        if not selected:
            if len(self.tree.get_children()) > 0:
                selected = (self.tree.get_children()[-1],)
            else:
                messagebox.showerror("Oops!", "Cart is empty", parent=biller)
                return

        for sel in selected:
            idx = self.tree.index(sel)
            self.cart.remove_item_at(idx)
            self.tree.delete(sel)
        self.update_total()
        self._refresh_live_preview()

    def update_total(self):
        subtotal = self.cart.total()
        subtotal = self.cart.total()
        self._grand_total = subtotal - self.coupon_discount_val - self.loyalty_redemption_amt
        if self._grand_total < 0: self._grand_total = 0
        
        # Calculate 5% inclusive GST
        tax_rate = 0.05
        base_amt = self._grand_total / (1 + tax_rate)
        total_tax = self._grand_total - base_amt
        
        self.total_label.configure(text=f"Net Payable: Rs. {self._grand_total:.2f}")
        self.gst_label.configure(text=f"Incl. GST (5%): Rs. {total_tax:.2f}")
        
        # Savings display
        off_sav = self.cart.savings()
        total_sav = off_sav + self.coupon_discount_val
        self.savings_label.configure(text=f"Total Savings: Rs. {total_sav:.2f}")
        
        self._update_change_display()
        if self.pay_method.get() == "UPI":
            self._draw_payment_qr()
        
        self._refresh_live_preview()

    def total_bill(self):
        self.update_total()
        self._refresh_live_preview()

    def _refresh_live_preview(self):
        # Synchronize labels
        self.preview_name.set(cust_name.get() or "Cash Customer")
        self.preview_phone.set(cust_num.get() or "N/A")
        self.preview_bill.set(self.current_bill_no)
        self.preview_date.set(str(date.today()))
        self.preview_payment.set(self.pay_method.get())
        self.preview_time.set(datetime.now().strftime("%H:%M:%S"))

        # Build preview text
        width = 44
        line = "─" * width + "\n"
        preview = "REAL MART - PREVIEW".center(width) + "\n"
        preview += "TAX INVOICE (DRAFT)".center(width) + "\n"
        preview += line
        preview += f"Bill #: {self.current_bill_no}\n"
        preview += f"Cust  : {self.preview_name.get()}\n"
        preview += f"Mode  : {self.preview_payment.get()}\n"
        preview += line
        preview += "%-14s %3s %7s %7s %8s\n" % ("Item", "Qty", "MRP", "Disc", "Total")
        preview += line
        
        for child in self.tree.get_children():
            val = self.tree.item(child, 'values')
            name, qty, mrp, disc, tot = val
            d_name = (name[:12] + '..') if len(name) > 14 else name
            preview += "%-14s %3s %7.2f %7.2f %8.2f\n" % (d_name, qty, float(mrp), float(disc), float(tot))
        
        preview += line
        tax_rate = 0.05
        base_amt = self._grand_total / (1 + tax_rate)
        total_tax = self._grand_total - base_amt
        preview += "%-30s %12.2f\n" % ("Base Amount:", base_amt)
        preview += "%-30s %12.2f\n" % ("GST (5%):", total_tax)
        if self.coupon_discount_val > 0:
            preview += "%-30s %12.2f\n" % ("Coupon Discount:", -self.coupon_discount_val)
        if self.loyalty_redemption_amt > 0:
            preview += "%-30s %12.2f\n" % ("Loyalty Redeem:", -self.loyalty_redemption_amt)
        preview += "%-30s %12.2f\n" % ("NET PAYABLE:", self._grand_total)
        preview += line
        
        self.live_preview.configure(state="normal")
        self.live_preview.delete(1.0, END)
        self.live_preview.insert(END, preview)
        self.live_preview.configure(state="disabled")
        self.live_preview.see(END)


    def gen_bill(self):
        if self.state == 0:
            messagebox.showinfo("Wait", "This bill is already generated.", parent=biller)
            return

        if cust_name.get() == "":
            messagebox.showerror("Oops!", "Please enter a name.", parent=biller)
        elif cust_num.get() == "":
            messagebox.showerror("Oops!", "Please enter a number.", parent=biller)
        elif not valid_phone(cust_num.get()):
            messagebox.showerror("Oops!", "Please enter a valid number.", parent=biller)
        elif self.cart.isEmpty():
            messagebox.showerror("Oops!", "Cart is empty.", parent=biller)
        else:
            payment = self.pay_method.get()
            bill_no = self.current_bill_no
            bill_time_db = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            bill_time_short = datetime.now().strftime("%H:%M:%S")

            # NEW: Calculate the authoritative total from the Tree (UI source of truth)
            # This ensures the printed bill and database always match perfectly.
            item_total_sum = 0.0
            item_count = 0
            temp_lines = ""
            for child in self.tree.get_children():
                val = self.tree.item(child, 'values')
                name = val[0]
                qty_str = val[1]
                mrp_str = val[2]
                disc_str = val[3]
                tot_str = val[4]
                try:
                    qty = float(qty_str)
                    mrp = float(mrp_str)
                    disc = float(disc_str)
                    line_total = float(tot_str)
                except: continue
                
                item_total_sum += line_total
                item_count += 1
                display_name = (name[:14] + '..') if len(name) > 16 else name
                temp_lines += "%-14s %3.0f %7.2f %7.2f %8.2f\n" % (display_name, qty, mrp, disc, line_total)

            # Synchronize authoritative 'grand' total (Subtract discounts)
            grand = item_total_sum - self.coupon_discount_val - self.loyalty_redemption_amt
            if grand < 0: grand = 0

            # Cash math validation now uses the authoritative 'grand'
            cash_t = 0.0
            chg = 0.0
            if payment == "Cash":
                raw = self.cash_received.get().strip()
                if not raw:
                    messagebox.showerror("Oops!", "Enter cash received.", parent=biller)
                    return
                try:
                    cash_t = float(raw)
                except ValueError:
                    messagebox.showerror("Oops!", "Invalid cash amount.", parent=biller)
                    return
                if cash_t < grand:
                    messagebox.showerror("Oops!", f"Insufficient cash (Total: Rs. {grand:.2f})", parent=biller)
                    return
                chg = cash_t - grand
            
            elif payment == "Card":
                cname = self.card_name_val.get().strip()
                cnum = self.card_num_val.get().strip()
                cexp = self.card_exp_val.get().strip()
                if not cname:
                    messagebox.showerror("Oops!", "Enter Card Holder Name.", parent=biller)
                    return
                if not cnum or not cnum.isdigit() or len(cnum) != 16:
                    messagebox.showerror("Oops!", "Enter a valid 16-digit card number.", parent=biller)
                    return
                if not cexp or "/" not in cexp or len(cexp) != 5:
                    messagebox.showerror("Oops!", "Enter a valid expiry (MM/YY).", parent=biller)
                    return

            # Prepare realistic receipt text
            width = 44
            line = "─" * width + "\n"
            
            # 1. Store Header
            bill_body = "REAL MART".center(width) + "\n"
            bill_body += "123, Fresh Street, Green City".center(width) + "\n"
            bill_body += "Phone: +91 98765 43210".center(width) + "\n"
            bill_body += "GSTIN: 27AAACR1234A1Z5".center(width) + "\n"
            bill_body += "═" * width + "\n"
            bill_body += "TAX INVOICE".center(width) + "\n"
            bill_body += "═" * width + "\n"
            
            # 2. Bill Metadata
            bill_body += f"Bill #: {bill_no}\n"
            bill_body += f"Date  : {date.today()} {bill_time_short}\n"
            bill_body += f"Cust  : {cust_name.get()}\n"
            bill_body += f"Phone : {cust_num.get()}\n"
            bill_body += f"Cashier: {username}\n"
            bill_body += line
            
            # 3. Table Header
            bill_body += "%-14s %3s %7s %7s %8s\n" % ("Item", "Qty", "MRP", "Disc", "Total")
            bill_body += line
            bill_body += temp_lines
            bill_body += line
            
            # 4. Financials (Tax Calculation)
            tax_rate = 0.05
            base_amt = grand / (1 + tax_rate)
            total_tax = grand - base_amt
            cgst = total_tax / 2
            sgst = total_tax / 2
            
            bill_body += "%-30s %12.2f\n" % ("Total Item Value:", grand)
            bill_body += "%-30s %12.2f\n" % ("Base Amount:", base_amt)
            bill_body += "%-30s %12.2f\n" % ("CGST (2.5%):", cgst)
            bill_body += "%-30s %12.2f\n" % ("SGST (2.5%):", sgst)
            
            off_sav = self.cart.savings()
            
            if off_sav > 0:
                bill_body += "%-30s %12.2f\n" % ("Product Offers:", -off_sav)
            if self.coupon_discount_val > 0:
                bill_body += "%-30s %12.2f\n" % ("Coupon Discount:", -self.coupon_discount_val)
            if self.loyalty_redemption_amt > 0:
                bill_body += "%-30s %12.2f\n" % ("Loyalty Redeem:", -self.loyalty_redemption_amt)
            
            bill_body += line
            bill_body += "%-30s %12.2f\n" % ("NET PAYABLE:", grand)
            
            total_sav = off_sav + self.coupon_discount_val + self.loyalty_redemption_amt
            if total_sav > 0:
                bill_body += line
                bill_body += f"YOU SAVED: Rs. {total_sav:.2f}".center(width) + "\n"
            
            bill_body += line

            # --- Smart Coupon Tier Selection ---
            cur.execute("SELECT min_bill, reward_value, discount_type FROM coupon_tiers WHERE min_bill <= ? ORDER BY min_bill DESC LIMIT 1", (self._grand_total,))
            row_t = cur.fetchone()
            
            new_coupon = None
            if row_t:
                threshold, reward, c_type = row_t
                new_code = "RM" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
                expiry = (date.today() + timedelta(days=30)).strftime("%Y-%m-%d")
                created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cur.execute("INSERT INTO coupons (coupon_code, discount_value, discount_type, min_bill, expiry_date, created_at) VALUES (?,?,?,?,?,?)",
                            (new_code, reward, c_type, threshold, expiry, created))
                new_coupon = new_code
                
            if new_coupon:
                bill_body += "🎉 CONGRATULATIONS! 🎉".center(width) + "\n"
                bill_body += f"You won a Smart Coupon: {new_coupon}".center(width) + "\n"
                if c_type == "Percentage":
                    bill_body += f"Get {reward:.0f}% OFF on your next visit!".center(width) + "\n"
                else:
                    bill_body += f"Get Rs. {reward:.0f} OFF on your next visit!".center(width) + "\n"
                bill_body += f"(Min bill: Rs. {threshold:.0f} | Valid till: {expiry})".center(width) + "\n"
                bill_body += line
            
            # 6. Footer & Payment Details
            bill_body += f"Items Count: {item_count}\n"
            bill_body += f"Payment Mode: {payment}\n"
            if payment == "Cash":
                bill_body += f"Cash Tendered: Rs. {cash_t:.2f}\n"
                bill_body += f"Change Return: Rs. {chg:.2f}\n"
            elif payment == "Card":
                masked = "**** **** **** " + self.card_num_val.get()[-4:]
                bill_body += f"Card Holder  : {self.card_name_val.get().upper()}\n"
                bill_body += f"Card No      : {masked}\n"
            elif payment == "UPI":
                bill_body += f"UPI ID Used  : {self.active_upi_id}\n"
            
            bill_body += line
            bill_body += "THANK YOU FOR SHOPPING!".center(width) + "\n"
            bill_body += "Items once sold are not returnable.".center(width) + "\n"
            bill_body += "Visit again!".center(width) + "\n"
            bill_body += line
            
            # Save to Database
            insert = (
                "INSERT INTO bill(bill_no, date, customer_name, customer_no, bill_details, "
                "payment_method, cash_tendered, change_amount, bill_time, card_no, card_holder, card_expiry, upi_id_used, total_amount) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)"
            )
            cur.execute(
                insert,
                [
                    bill_no,
                    str(date.today()),
                    cust_name.get(),
                    cust_num.get(),
                    bill_body,
                    payment,
                    cash_t if payment == "Cash" else None,
                    chg if payment == "Cash" else None,
                    bill_time_db,
                    self.card_num_val.get() if payment == "Card" else None,
                    self.card_name_val.get() if payment == "Card" else None,
                    self.card_exp_val.get() if payment == "Card" else None,
                    self.active_upi_id if payment == "UPI" else None,
                    self._grand_total
                ],
            )
            
            # Mark redeemed coupon as used
            if self.applied_coupon_code:
                cur.execute("UPDATE coupons SET is_used = 1 WHERE coupon_code = ?", (self.applied_coupon_code,))
            
            # Update Inventory
            self.cart.allCart()
            for name, qty in self.cart.dictionary.items():
                cur.execute("UPDATE raw_inventory SET stock = stock - ? WHERE product_name = ?", [qty, name])
            
            # Professional Database: Save individual line items for reporting
            for child in self.tree.get_children():
                val = self.tree.item(child, 'values')
                p_name = val[0]
                p_qty = float(val[1])
                p_unit_mrp = float(val[2])
                p_unit_disc = float(val[3])
                p_line_total = float(val[4])
                
                # Fetch product data including cost_price
                cur.execute("SELECT product_id, cost_price FROM raw_inventory WHERE product_name = ?", (p_name,))
                p_row = cur.fetchone()
                p_id = p_row[0] if p_row else None
                p_cost = float(p_row[1] if p_row and p_row[1] else 0.0)
                
                # Store the final price (MRP - Disc) and cost_price in the bill_items
                final_unit_price = p_unit_mrp - p_unit_disc
                cur.execute(
                    "INSERT INTO bill_items(bill_no, product_id, product_name, quantity, mrp, cost_price, total_price) VALUES(?,?,?,?,?,?,?)",
                    (bill_no, p_id, p_name, p_qty, final_unit_price, p_cost, p_line_total)
                )
            
            db.commit()
            
            # Automated Backup (Host only to ensure data safety after every sale)
            try:
                import config_manager
                cfg = config_manager.load_config()
                if cfg.get("role") == "host":
                    config_manager.perform_backup()
            except: pass
            
            # --- LOYALTY POINTS AWARDING ---
            try:
                cur.execute("SELECT `value` FROM loyalty_config WHERE `key`='points_per_100'")
                ev = cur.fetchone()
                rate = float(ev[0]) if ev else 1.0
                earned = (grand / 100.0) * rate
                
                import config_manager
                is_mysql = config_manager.load_config().get("db_type") == "mysql"
                
                if is_mysql:
                    cur.execute("""
                        INSERT INTO loyalty_points (phone, points, total_spent, last_visit) 
                        VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                        ON DUPLICATE KEY UPDATE 
                        points = (CASE WHEN %s > 0 THEN %s ELSE points + %s END),
                        total_spent = total_spent + %s,
                        last_visit = CURRENT_TIMESTAMP
                    """, (cust_num.get(), earned, grand, self.loyalty_redemption_amt, earned, earned, grand))
                else:
                    # SQLite: Check existence
                    cur.execute("SELECT points FROM loyalty_points WHERE phone=?", (cust_num.get(),))
                    exists = cur.fetchone()
                    if exists:
                        new_bal = earned if self.loyalty_redemption_amt > 0 else float(exists[0]) + earned
                        cur.execute("UPDATE loyalty_points SET points=?, total_spent=total_spent+?, last_visit=CURRENT_TIMESTAMP WHERE phone=?", (new_bal, grand, cust_num.get()))
                    else:
                        cur.execute("INSERT INTO loyalty_points (phone, points, total_spent, last_visit) VALUES (?,?,?, CURRENT_TIMESTAMP)", (cust_num.get(), earned, grand))
                db.commit()
            except Exception as e:
                print(f"Loyalty Update Error: {e}")
            
            messagebox.showinfo("Success!!", "Bill generated.", parent=biller)
            
            # 1. Save copy silently in background
            save_bill_silent(bill_no, bill_body)
            
            # 2. Show Scan-to-Download QR Code
            QRCodeReceiptPopup(biller, bill_no)

            self.clear_bill()

    def _on_search_key(self, event):
        val = self.search_var.get().strip()
        if not val:
            self.search_list_frame.pack_forget()
            return

        # --- AUTO-ADD BARCODE LOGIC ---
        # If the input length looks like a barcode, check for an exact match to auto-add
        if len(val) >= 4:
            try:
                cur.execute("SELECT barcode FROM raw_inventory WHERE barcode = ?", (val,))
                if cur.fetchone():
                    self._on_search_enter()
                    return # Exit early as item is already added
            except: pass

        # Fetch matches
        try:
            q = "SELECT product_name FROM raw_inventory WHERE product_name LIKE ? LIMIT 10"
            cur.execute(q, (f"%{val}%",))
            matches = [r[0] for r in cur.fetchall()]
            
            if not matches:
                self.search_list_frame.pack_forget()
                return
                
            self.search_listbox.delete(0, END)
            for m in matches:
                self.search_listbox.insert(END, m)
            
            self.search_list_frame.pack(fill=X, after=self.search_entry.master, pady=(0, 20))
            self.search_list_frame.tkraise()
        except: pass

    def _on_search_down(self, event):
        if self.search_listbox.size() > 0:
            self.search_listbox.focus()
            self.search_listbox.selection_set(0)

    def _on_search_enter(self, event=None):
        query = self.search_var.get().strip()
        if not query: return

        # --- NEW: Barcode Detection Logic ---
        # Look up anything that could be a barcode directly first
        if len(query) >= 4:
            try:
                cur.execute("SELECT product_name, mrp, stock, expiry_date, offer_type, offer_value FROM raw_inventory WHERE barcode = ?", (query,))
                bar_match = cur.fetchone()
                if bar_match:
                    if self.state == 0:
                        self.clear_bill()
                        
                    name, mrp, stock, expiry, off_type, off_val = bar_match
                    mrp = float(mrp)
                    stock = int(stock)
                    off_val = float(off_val or 0.0)
                    off_type = off_type or "None"

                    # NEW: Last Chance Discount
                    lc_pct = self.get_last_chance_discount(name)
                    flash_pct = self.get_flash_discount(name) # Check if category-based flash sale
                    
                    total_off_pct = 0.0
                    if off_type == "Percentage": total_off_pct += off_val
                    total_off_pct += flash_pct
                    
                    is_last_chance = False
                    if lc_pct > 0:
                        total_off_pct += lc_pct
                        is_last_chance = True
                    
                    if total_off_pct > 90: total_off_pct = 90
                    final_price = mrp * (1.0 - total_off_pct / 100.0)
                    if off_type == "Flat Discount" and not is_last_chance:
                        final_price -= off_val
                    
                    if final_price < 0: final_price = 0.0
                    discount_per_unit = mrp - final_price
                    
                    # Cleanup search IMMEDIATELY to prevent double-trigger from queued events
                    self.search_var.set("")
                    self.search_list_frame.pack_forget()
                    self.search_entry.focus()

                    # Check for expiry
                    if self.is_expired(expiry, name):
                        return

                    if stock <= 0:
                        messagebox.showerror("Out of Stock", f"Product '{name}' is out of stock.", parent=biller)
                    else:
                        # --- SMART: Check if item already in bill to increment Qty ---
                        found_item = None
                        existing_child = None
                        for child in self.tree.get_children():
                            if self.tree.item(child)["values"][0] == name:
                                existing_child = child
                                # Find corresponding item in cart
                                idx = self.tree.index(child)
                                found_item = self.cart.items[idx]
                                break
                        
                        if found_item:
                            # Increment Quantity
                            new_qty = found_item.qty + 1
                            if new_qty > stock:
                                messagebox.showwarning("Inadequate Stock", f"Cannot add more '{name}'. Only {stock} in stock.", parent=biller)
                            else:
                                found_item.qty = new_qty
                                new_total = found_item.price * new_qty
                                self.tree.item(existing_child, values=(name, new_qty, f"{mrp:.2f}", f"{discount_per_unit:.2f}", f"{new_total:.2f}"))
                                self.update_total()
                                self._refresh_live_preview()
                        else:
                            # Add to cart immediately with Qty 1
                            sp = final_price * 1
                            item = Item(name, final_price, 1, original_price=mrp)
                            self.cart.add_item(item)
                            tag = "even" if len(self.tree.get_children()) % 2 == 0 else "odd"
                            self.tree.insert("", END, values=(name, 1, f"{mrp:.2f}", f"{discount_per_unit:.2f}", f"{sp:.2f}"), tags=(tag,))
                            self.update_total()
                            self._refresh_live_preview()
                    
                    # Cleanup search
                    self.search_var.set("")
                    self.search_list_frame.pack_forget()
                    self.search_entry.focus()
                    return
                else:
                    # If it's definitely a barcode but NOT found
                    messagebox.showwarning("Unknown Barcode", f"Barcode '{query}' not found in inventory.\n\nPlease add it in the Admin panel.", parent=biller)
                    self.search_var.set("")
                    return
            except Exception as e:
                print(f"Barcode search error: {e}")

        # --- Existing Listbox Selection Logic ---
        sel = self.search_listbox.curselection()
        if not sel:
            if self.search_listbox.size() > 0:
                name = self.search_listbox.get(0)
            else: return
        else:
            name = self.search_listbox.get(sel[0])

        # Find the category and update UI
        try:
            cur.execute("SELECT product_cat FROM raw_inventory WHERE product_name = ?", (name, ))
            row = cur.fetchone()
            if row:
                cat = row[0]
                self.combo1.set(cat)
                self.get_category(None)
                self.combo3.set(name)
                self.show_qty(None)
                
                # Cleanup search
                self.search_var.set("")
                self.search_list_frame.pack_forget()
                
                # Focus quantity
                self.entry4.focus()
        except: pass

    def clear_bill(self):
        self._stop_qr_timer()
        self.pay_method.set("Cash")
        self._on_pay_method()
        
        # Reset coupon state
        self.coupon_var.set("")
        self.coupon_discount_val = 0.0
        self.applied_coupon_code = None
        self.coupon_status.config(text="Enter coupon code for extra discount", fg=T.TEXT_SUB)
        
        # Reset loyalty state
        self.loyalty_redemption_amt = 0.0

        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.current_bill_no = random_bill_number(8)
            
        self.cart.remove_items()
        self.cart.dictionary.clear()
        self.state = 1
        self.total_label.configure(text="Net Payable: Rs. 0.00")
        self.gst_label.configure(text="Incl. GST (5%): Rs. 0.00")
        self.cash_received.set("")
        self.active_upi_id = None
        self._grand_total = 0.0
        self._refresh_live_preview()
        self._update_change_display()
        self.clear_selection()
        
        # Reset preview labels
        self.preview_name.set("")
        self.preview_phone.set("")
        self.preview_bill.set("")
        self.preview_date.set("")
        self.preview_payment.set("")
        self.preview_time.set("")
        
        # Reset input entry variables (Global StringVars)
        if 'cust_name' in globals() and cust_name:
            cust_name.set("")
        if 'cust_num' in globals() and cust_num:
            cust_num.set("")
        if 'cust_search_bill' in globals() and cust_search_bill:
            cust_search_bill.set("")
        self.card_num_val.set("")
        self.card_exp_val.set("")
        self.card_name_val.set("")

    def clear_selection(self):
        self.entry4.delete(0, END)
        self.combo1.configure(state="readonly")
        self.combo3.configure(state="readonly")
        self.combo1.set("")
        self.combo3.set("")
        self.combo3.configure(state="disabled")
             
    def search_bill(self):
        find_bill = "SELECT * FROM bill WHERE bill_no = ?"
        cur.execute(find_bill, [cust_search_bill.get().rstrip()])
        results = cur.fetchall()
        if results:
            row = db_init.parse_bill_row(results[0])
            self.clear_bill()
            cust_name.set(row["customer_name"])
            cust_num.set(row["customer_no"])
            self.preview_name.set(row["customer_name"])
            self.preview_phone.set(row["customer_no"])
            self.preview_bill.set(row["bill_no"])
            self.preview_date.set(row["date"])
            self.preview_payment.set(row["payment_method"] or "Cash")
            bt = row["bill_time"] or ""
            if bt and len(bt) >= 19:
                self.preview_time.set(bt[11:19])
            else:
                self.preview_time.set(bt)

            # For viewing old bills, we can show a pop-up with details or temporarily fill the tree?
            # Treeview is for NEW bills. For historical view, let's use a popup.
            hist_win = Toplevel(biller)
            hist_win.title(f"Bill Detail - {row['bill_no']}")
            hist_win.geometry("500x600")
            hist_win.configure(bg=T.BG_ROOT)
            txt = tkst.ScrolledText(hist_win, font=("Consolas", 10), bg=T.CARD, fg=T.TEXT_ON_LIGHT)
            txt.pack(fill=BOTH, expand=True, padx=10, pady=10)
            txt.insert(END, row["bill_details"])
            txt.configure(state="disabled")

            self.entry1.configure(state="disabled")
            self.entry2.configure(state="disabled")
            self.state = 0
        else:
            messagebox.showerror("Error!!", "Bill not found.", parent=biller)
            self.entry3.delete(0, END)
            
    def time(self):
        string = strftime("%H:%M:%S %p")
        self.clock.config(text=string)
        self.clock.after(1000, self.time)

