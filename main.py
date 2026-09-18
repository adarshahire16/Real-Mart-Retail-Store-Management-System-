import os
import shutil
import subprocess
import sys

# Suppress __pycache__ creation for a clean project folder
sys.dont_write_bytecode = True

# --- Relaunch Repair Logic (Ensures app starts with a stable Python) ---
def maybe_relaunch_this_script():
    # Avoid infinite loops when relaunched
    if os.environ.get("REAL_MART_CHILD") == "1":
        return
    # Only relaunch if strictly broken (cannot even start Tkinter or PIL)
    try:
        import tkinter
        from PIL import Image
    except ImportError:
        # It's actually broken, proceed to find a stable Python
        pass
    else:
        # Core libraries are fine, no need to relaunch
        return




    # Proactively find a stable Python
    script = os.path.abspath(sys.argv[0])
    root = os.path.dirname(script)
    
    # We prioritize 3.12 as it is confirmed to have Pillow installed
    candidates = [
        ["py", "-3.12"],
        ["py", "-3.13"],
        ["python"],
    ]
        
    for cmd in candidates:
        try:
            # We skip the complex test here because the 'prefix' error might 
            # make subprocess calls fail or return weird codes.
            # We just try to launch the script with the candidate.
            env = os.environ.copy()
            env["REAL_MART_CHILD"] = "1"
            
            # Show output so we can see why it's failing
            p = subprocess.Popen(cmd + [script] + sys.argv[1:], cwd=root, env=env)
            
            # Give it a tiny moment to see if it crashed immediately
            import time
            time.sleep(0.3)
            if p.poll() is None:
                # Still running? Success!
                sys.exit(0)
        except Exception:
            continue
    
    # If we made it here without finding another Python, return and try running anyway
    return

maybe_relaunch_this_script()

print("Real Mart - Launching POS...")
import sys
import tkinter as tk
from tkinter import messagebox, simpledialog
import config_manager
import theme as T

def get_app_root():
    if getattr(sys, 'frozen', False):
        # Path to the actual folder where the EXE is located
        return os.path.dirname(sys.executable)
    # Path to the script's folder
    return os.path.dirname(os.path.abspath(__file__))

_APP_ROOT = get_app_root()
os.chdir(_APP_ROOT)
T.check_tkinter_or_exit()


main = tk.Tk()
main._is_exiting = False # Flag to stop redraws during shutdown
main.geometry("1100x700")
try: main.state('zoomed') # Start Maximized
except: pass

main.title("Real Mart")
main.resizable(True, True)
T.style_root(main)
T.setup_ttk(main)
main.update() # Force initial window mapping for correct dimensions


def Exit():
    main._is_exiting = True # Block any further redraw jobs
    sure = messagebox.askyesno("Exit", "Are you sure you want to exit?", parent=main)
    if sure:
        # —— DATA SAFETY: AUTO BACKUP ——
        cfg = config_manager.load_config()
        if cfg.get("auto_backup_on_close") and cfg.get("role") == "host":
            # Only the Host PC performs the shared database backup
            print("Real Mart: Performing safety backup before exit...")
            config_manager.perform_backup()
            
        main.destroy()
    else:
        main._is_exiting = False # Resume if they canceled


main.protocol("WM_DELETE_WINDOW", Exit)


# Heavy modules moved to lazy imports in emp() and adm() to speed up startup
# Optimized Startup: Warm up heavy assets and modules in background
# Staggered Asset Loading: Allow the main window frame to show before starting heavy tasks
main.after(100, T.warm_up_backgrounds)

def pre_load_heavy_modules():
    import threading
    def _task():
        try:
            import admin
            import employee
            import network_manager
            import updater
            network_manager.check_in()
            updater.check_in_background(main) # Auto-check for GitHub updates
        except Exception as e:
            print(f"Background pre-load warning: {e}")
            
    threading.Thread(target=_task, daemon=True).start()

# Delay heavy module loading until after the main UI is fully interactive
main.after(800, pre_load_heavy_modules)


def check_db_and_start():
    import config_manager
    import db_manager
    import db_setup
    config = config_manager.load_config()
    
    # Test connection
    success, msg = db_manager.DBConnection().test_current_config()
    
    # Show wizard if connection fails OR if setup hasn't been completed yet
    if not success or not config.get("setup_complete"):
        print(f"Setup required (Success: {success}, SetupDone: {config.get('setup_complete')})")
        db_setup.show_wizard(main, check_db_and_start)
    else:
        # Proceed to main menu
        render_main_menu()


def render_main_menu():
    main.current_view = "main_menu" # Set state before clearing
    main.config(cursor="") # Reset root cursor
    
    # —— CLEAN TRANSITION ——
    # Find existing canvas and clear it
    cv = None
    for widget in tk.Misc.winfo_children(main):
        if getattr(widget, "_is_bg_canvas", False):
            cv = widget
            break
            
    if cv:
        T.clear_ui_content(cv)
        cv.config(cursor="") # Reset canvas cursor
    
    # Destroy all root-level widgets that might have been added by sub-modules
    # Use tk.Misc.winfo_children directly to bypass any potential shielding
    for widget in tk.Misc.winfo_children(main):
        # PROTECT the background canvas to avoid flickering/re-processing
        if getattr(widget, "_is_bg_canvas", False):
            continue
            
        try:
            widget.destroy()
        except: pass
            
    # —— Navigation Cleanup ——
    # Force the next refresh_ui call to redraw by clearing the size and master caches
    main._last_rendered_size = None
    if hasattr(main, "_cached_master_id"):
        del main._cached_master_id

    
    build_main_menu(main)

def emp():
    main.config(cursor="watch")
    main.update_idletasks()
    try:
        import employee
        main.current_view = "pos_login" 
        employee.start_staff_pos(main, render_main_menu)
    except Exception as e:
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Failed to open POS:\n{e}", parent=main)
    finally:
        main.config(cursor="")

def adm():
    main.config(cursor="watch")
    main.update_idletasks()
    try:
        import admin
        main.current_view = "admin_login"
        admin.start_admin_hub(main, render_main_menu)
    except Exception as e:
        import traceback
        traceback.print_exc()
        messagebox.showerror("Error", f"Failed to open Admin Hub:\n{e}", parent=main)
    finally:
        main.config(cursor="")



def toggle_admin_mode():
    """
    Secret toggle to switch between HOST and TERMINAL modes.
    Triggered by clicking the main title.
    """
    import config_manager, db_manager, db_init, hardware_util
    
    cfg = config_manager.load_config()
    current_role = cfg.get("role", "host")
    
    # —— HARDWARE VALIDATION ——
    master_id = ""
    try:
        db = db_manager.connect()
        cur = db.execute("SELECT value FROM settings WHERE `key` = 'master_node_id'")
        res = cur.fetchone()
        master_id = res[0] if res else ""
    except: pass

    current_hwid = hardware_util.get_machine_id()
    if master_id and master_id != current_hwid:
        messagebox.showwarning("Access Restricted", "Admin mode can only be enabled on the Master PC.\n\nThis workstation is locked to Terminal mode.", parent=main)
        return

    if current_role == "terminal":
        # Ask for password to UPGRADE to Host
        pw = simpledialog.askstring("Maintenance Mode", "Enter Admin Password to enable Admin Hub:", show='*', parent=main)
        if pw:
            try:
                hashed = db_init.hash_password(pw)
                enc = db_init.secure_store(pw)
                db = db_manager.connect()
                cur = db.execute("SELECT 1 FROM employee WHERE (password=? OR password=?) AND designation='Admin'", (hashed, enc))
                if cur.fetchone():
                    cfg["role"] = "host"
                    config_manager.save_config(cfg)
                    messagebox.showinfo("Success", "Admin Hub enabled. Mode set to HOST.", parent=main)
                    render_main_menu()
                else:
                    messagebox.showerror("Error", "Incorrect Admin Password.", parent=main)
            except Exception as e:
                messagebox.showerror("Error", f"Verification failed: {e}", parent=main)
    else:
        # Ask for confirmation to DOWNGRADE to Terminal
        msg = "Switch to TERMINAL MODE?\n\nThe Admin Hub button will be hidden for staff safety.\n\n(You can click the 'REAL MART' title and enter your password to switch back at any time.)"
        if messagebox.askyesno("Switch Workstation Mode", msg, parent=main):
            cfg["role"] = "terminal"
            config_manager.save_config(cfg)
            render_main_menu()

def build_main_menu(window):
    # —— Iron-Clad Layering Setup ——
    # Layer 1: Persistent Background Canvas
    # Re-setup or recovery existing background layer
    cv = T.setup_glass_canvas(main, image_name=T.Backgrounds.HUB)
    
    # Safety: ensure it is at the bottom
    tk.Misc.lower(cv)

    def refresh_ui(*args):
        # Safety: Check if the canvas still exists
        try:
            if not cv.winfo_exists(): return
        except: return

        # Ensure background fits
        if hasattr(cv, "refresh_bg"):
            cv.refresh_bg()

        # —— Navigation Guard ——
        # ONLY update the background fit and bail if not in main menu.
        # This stops the Hub from wiping out the Staff POS during window restore.
        # —— FLICKER & EXIT PROTECTION ——
        # Check this BEFORE clearing the canvas to prevent disappearing panels during exit confirmation
        if getattr(main, "_is_exiting", False):
            return

        # —— NAVIGATION & MAPPING GUARD ——
        if getattr(main, "current_view", "main_menu") != "main_menu":
            return

        # Measure dimensions for Main Menu placement
        cv.update_idletasks()
        w, h = cv.winfo_width(), cv.winfo_height()
        
        # —— IMPROVED: Initial Size Detection ——
        if w < 100 or h < 100: 
            # If window isn't mapped, retry after a short delay to get real dims
            main.after(200, refresh_ui)
            return

        # Only redraw if the size has changed OR if cache was explicitly cleared (None)
        if hasattr(main, "_last_rendered_size") and main._last_rendered_size == (w, h):
            return

        # —— SAFE CLEAR & CACHE ——
        if cv: T.clear_ui_content(cv)
        main._last_rendered_size = (w, h)
        
        cx, cy = w / 2, h / 2

        # —— Draw Dynamic UI on Canvas ——
        T.draw_glass_panel(cv, cx, cy - 80, 800, 320, opacity=0.35)
        
        title_id = cv.create_text(cx, cy - 160, text="REAL MART", font=T.FONT_HERO, fill=T.WHITE, tags="ui_content")
        
        # —— DYNAMIC VISIBILITY LOGIC (PRE-FETCH FOR BINDING) ——
        import config_manager, db_manager, hardware_util
        cfg = config_manager.load_config()
        
        master_id = ""
        try:
            db = db_manager.connect()
            cur = db.execute("SELECT value FROM settings WHERE `key` = 'master_node_id'")
            res = cur.fetchone()
            master_id = res[0] if res else ""
        except: pass

        current_hwid = hardware_util.get_machine_id()
        is_master = (master_id == current_hwid)
        is_unallotted = (not master_id)

        # —— RESTRICTED CLICKABILITY ——
        # Only the Master PC or an unassigned PC can trigger the Admin toggle
        if is_master or is_unallotted:
            cv.tag_bind(title_id, "<Button-1>", lambda e: toggle_admin_mode())


        cv.create_text(cx, cy - 100, text="A clean, modern checkout for fresh retail.", font=T.FONT_UI, fill=T.WHITE, tags="ui_content")
        cv.create_line(cx - 200, cy - 60, cx + 200, cy - 60, fill=T.BORDER_SUBTLE, width=1, tags="ui_content")
        cv.create_text(cx, cy - 30, text="CHOOSE WORKSPACE", font=T.FONT_SECTION, fill=T.WHITE, tags="ui_content")

        # —— Buttons (Now correctly parented as direct children of the Canvas) ——
        import config_manager, db_manager, hardware_util
        cfg = config_manager.load_config()
        
        # —— DYNAMIC VISIBILITY LOGIC (CACHED) ——
        # Check if a Master is registered in the DB
        if not hasattr(main, "_cached_master_id"):
            master_id = ""
            try:
                db = db_manager.connect()
                cur = db.execute("SELECT value FROM settings WHERE `key` = 'master_node_id'")
                res = cur.fetchone()
                master_id = res[0] if res else ""
                main._cached_master_id = master_id
            except: pass
        else:
            master_id = main._cached_master_id

        if not hasattr(main, "_cached_hwid"):
            main._cached_hwid = hardware_util.get_machine_id()
        
        current_hwid = main._cached_hwid
        
        is_terminal = (cfg.get("role") == "terminal")
        
        # —— DYNAMIC VISIBILITY LOGIC ——
        # 1. Show if NO master is registered (allows anyone to claim)
        # 2. Show if THIS pc is the registered master
        # 3. HIDE if local mode is set to 'terminal' (Staff Safety)
        is_master = (master_id == current_hwid)
        is_unallotted = (not master_id)
        
        # HARDWARE ENFORCEMENT: Even if role is 'host', hide if we are not the master
        show_admin_button = (is_master or is_unallotted) and not is_terminal


        if not show_admin_button:
            # Hide Admin button: Show only centered Billing button
            btn_staff = tk.Button(cv, text=" START BILLING ", command=emp, bg=T.BTN_GREEN, fg=T.WHITE, 
                                   font=T.FONT_TITLE_MD, padx=60, pady=20, relief="flat", cursor="hand2")
            cv.create_window(cx, cy + 80, window=btn_staff, tags="ui_content")
            T.bind_hover(btn_staff)
        else:
            # Show both buttons
            btn_staff = tk.Button(cv, text=" STAFF POS ", command=emp, bg=T.BTN_GREEN, fg=T.WHITE, 
                                   font=T.FONT_TITLE_MD, padx=40, pady=15, relief="flat", cursor="hand2")
            cv.create_window(cx - 180, cy + 80, window=btn_staff, tags="ui_content")
            T.bind_hover(btn_staff)

            btn_admin = tk.Button(cv, text=" ADMIN HUB ", command=adm, bg=T.BTN_GREEN, fg=T.WHITE,
                                   font=T.FONT_TITLE_MD, padx=40, pady=15, relief="flat", cursor="hand2")
            cv.create_window(cx + 180, cy + 80, window=btn_admin, tags="ui_content")
            T.bind_hover(btn_admin)
            
            if is_unallotted:
                cv.create_text(cx + 180, cy + 140, text="(Click to allot this PC)", font=T.FONT_SMALL, fill=T.WHITE, tags="ui_content")



        # Footer & Utilities
        footer_y = h - 50
        
        cv.create_text(40, footer_y, text="Fresh · Organized · Premium", font=T.FONT_SMALL, fill=T.TEXT_MUTED, anchor="w", tags="ui_content")
        
        # Exit button stays on the far right
        exit_btn = tk.Button(cv, text="Exit App", command=Exit, bg=T.BG_ROOT, fg=T.TEXT_MUTED, relief="flat", padx=12, pady=5, font=T.FONT_UI_SM)
        cv.create_window(w - 60, footer_y, window=exit_btn, tags="ui_content", anchor="e")

        # Footer & Utilities

    # INCREASED DEBOUNCE: Prevents lag during active window dragging
    def handle_resize(event):
        if event.widget != main:
            return
        if hasattr(main, "_resize_job") and main._resize_job:
            main.after_cancel(main._resize_job)
        # DEBOUNCE: Reduced to 30ms for snappier maximization
        main._resize_job = main.after(30, refresh_ui)


    main.bind("<Configure>", handle_resize)
    
    main.state("zoomed")

    # Final rendering pass: Just one trigger to ensure initial visibility
    # —— PERFORMANCE OPTIMIZED STARTUP ——
    # Reduced passes for snappier hardware-accelerated loading
    main.after(10, refresh_ui) 

# Note: The background canvas preservation is now handled explicitly in transitions
# to avoid shadowing core Tkinter methods which can interfere with module logic.




# STARTUP SEQUENCE:
# 1. Show window immediately (Window frame appears)
# 2. Run initial UI render (Background and buttons appear)
# 3. Then perform the DB connection check
main.after(50, check_db_and_start)
main.mainloop()


