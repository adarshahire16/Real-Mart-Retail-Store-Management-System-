try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    cv2 = None
    CV2_AVAILABLE = False

try:
    from pyzbar import pyzbar
    PYZBAR_AVAILABLE = True
except ImportError:
    pyzbar = None
    PYZBAR_AVAILABLE = False

import threading
from tkinter import *
from tkinter import messagebox
from PIL import Image, ImageTk, ImageOps
import time
import winsound
import theme as T
import traceback

class CameraScanner:
    """
    A reusable Barcode Scanner Popup using OpenCV and PyZbar.
    Optimized for DroidCam and integrated webcams on Windows.
    """
    def __init__(self, parent, title="Barcode Scanner", callback=None, continuous=False):
        self.parent = parent
        self.callback = callback
        self.continuous = continuous
        self.flipped = False 
        self.running = True
        
        if not CV2_AVAILABLE or not PYZBAR_AVAILABLE:
            messagebox.showerror("Scanner Unavailable", 
                "Camera scanning requires opencv-python and pyzbar.\n\n"
                "Please install them via: pip install opencv-python pyzbar",
                parent=parent)
            return

        # UI Setup
        self.window = Toplevel(parent)
        self.window.title(title)
        self.window.geometry("640x650")
        self.window.resizable(False, False)
        self.window.config(bg="#FFFFFF")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.window.attributes("-topmost", True)
        
        try:
            T.style_root(self.window)
        except: pass
        
        # State Management
        self.cap = None
        self.video_item = None # Persistent canvas item for the video feed
        self.current_imgtk = None # Keep reference to imgtk in main thread
        self.last_decoded = ""
        self.scan_count = 0
        self.last_scan_time = 0
        self.debounce_seconds = 2.5 # Slower scanning as requested
        self.current_cam_index = 1 # Start with DroidCam Port 1
        self.current_cam_index = 1 # Start with DroidCam Port 1
        
        # UI Elements
        self.main_frame = Frame(self.window, bg="#FFFFFF", padx=20, pady=20)
        self.main_frame.pack(fill=BOTH, expand=True)

        # Video Display Container
        self.video_canvas = Canvas(self.main_frame, width=600, height=400, bg="#FFFFFF", highlightthickness=1, highlightbackground=T.BORDER_SUBTLE)
        self.video_canvas.pack(pady=10)
        
        self.tip_label = Label(self.main_frame, text="💡 Tip: Center the barcode inside the lens", font=T.FONT_UI_SM, bg="#FFFFFF", fg=T.PRIMARY)
        self.tip_label.pack(pady=(5, 15))
        
        # Internal state vars
        self.status_var = StringVar(value="⌛ Connecting to Camera...")
        self.status_label = Label(self.main_frame, textvariable=self.status_var, font=T.FONT_UI_SM, bg="#FFFFFF", fg=T.TEXT_SUB)
        self.status_label.pack(pady=2)
        
        self.scanned_var = StringVar(value="")

        # Controls
        self.btn_frame = Frame(self.main_frame, bg="#FFFFFF")
        self.btn_frame.pack(fill=X, pady=10)
        
        self.switch_btn = Button(self.btn_frame, text="🔄 Switch Camera", command=self.switch_camera)
        self.switch_btn.pack(side=LEFT, expand=True, padx=5, ipady=10, fill=X)
        T.btn_primary(self.switch_btn)

        self.flip_btn = Button(self.btn_frame, text="↔️ Mirror Flip", command=self.toggle_flip)
        self.flip_btn.pack(side=LEFT, expand=True, padx=5, ipady=10, fill=X)
        T.btn_primary(self.flip_btn)
        
        self.cancel_btn = Button(self.btn_frame, text="Close", command=self.close)
        self.cancel_btn.pack(side=LEFT, expand=True, padx=5, ipady=10, fill=X)
        T.btn_ghost(self.cancel_btn)

        # Start Camera Thread
        self.thread = threading.Thread(target=self.video_loop, daemon=True)
        self.thread.start()

    def start_camera(self, index):
        if self.cap:
            self.cap.release()
            time.sleep(0.5)
            
        try:
            self.cap = cv2.VideoCapture(index) # BASIC CONNECTION
            return self.cap.isOpened()
        except:
            return False

    def switch_camera(self):
        # ONE-CLICK FIX: Phone(1) <-> Laptop(0)
        if self.current_cam_index == 1:
            self.current_cam_index = 0
        else:
            self.current_cam_index = 1

    def toggle_flip(self):
        self.flipped = not self.flipped
        state = "On" if self.flipped else "Off"
        self.status_var.set(f"Mirror Flip: {state}")

    def video_loop(self):
        last_index = -1
        probe_indices = [1, 0, 2] # Port 1 is target DroidCam
        probe_ptr = 0
        read_failures = 0
        
        while self.running:
            try:
                if self.current_cam_index != last_index or not (self.cap and self.cap.isOpened()):
                    self.window.after(0, lambda: self.status_var.set(f"⌛ Connecting to Camera {self.current_cam_index}..."))
                    
                    if self.start_camera(self.current_cam_index):
                        last_index = self.current_cam_index
                        self.window.after(0, lambda: self.status_var.set("✅ Camera Active - Receiving Data"))
                        read_failures = 0
                    else:
                        self.window.after(0, lambda: self.status_var.set(f"❌ Failed to open Camera {self.current_cam_index}"))
                        probe_ptr = (probe_ptr + 1) % len(probe_indices)
                        self.current_cam_index = probe_indices[probe_ptr]
                        time.sleep(1)
                        continue

                ret, frame = self.cap.read()
                if not ret:
                    read_failures += 1
                    if read_failures > 10: # ~5 seconds of failure
                        last_index = -1 # Force re-init
                        probe_ptr = (probe_ptr + 1) % len(probe_indices)
                        self.current_cam_index = probe_indices[probe_ptr]
                        read_failures = 0
                    time.sleep(0.5)
                    continue
                
                # Reset failures on successful read
                read_failures = 0

                if self.flipped:
                    frame = cv2.flip(frame, 1)
                
                # --- 0. DECODE BEFORE DRAWING ---
                self.scan_count += 1
                if self.scan_count % 6 == 0:
                    # Use a grayscale copy for immunity to UI lines and color noise
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    barcodes = pyzbar.decode(gray)
                    for barcode in barcodes:
                        barcode_data = barcode.data.decode("utf-8")
                        if barcode_data:
                            self.on_barcode_found(barcode_data)
                            break

                # --- 1. Ready for rendering ---
                fh, fw = frame.shape[:2]

                try:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(rgb_frame)
                    
                    if self.running:
                        self.window.after(0, lambda f=img: self._update_canvas(f))
                    time.sleep(0.01)
                except:
                    time.sleep(0.5)

            except:
                time.sleep(0.5)

        if self.cap:
            self.cap.release()

    def _update_canvas(self, frame_image):
        """Standard Tkinter-safe UI update. Call via .after(0)"""
        if not self.running: return
        try:
            if not self.window.winfo_exists(): return
            
            # Restore smooth center-cropping to remove black bars
            resample = getattr(Image, 'Resampling', Image).BILINEAR
            img = ImageOps.fit(frame_image, (600, 400), resample)
            imgtk = ImageTk.PhotoImage(image=img)
            
            if self.video_item is None:
                self.video_item = self.video_canvas.create_image(300, 200, anchor=CENTER, image=imgtk)
            else:
                self.video_canvas.itemconfig(self.video_item, image=imgtk)
            
            # 3. Prevent garbage collection
            self.current_imgtk = imgtk
            self.video_canvas.imgtk = imgtk
        except Exception as e:
            # Silently handle window destruction during update
            pass

    def on_barcode_found(self, data):
        now = time.time()
        # GLOBAL COOLDOWN: Block ANY new scan within the window (decreases speed)
        if (now - self.last_scan_time) < self.debounce_seconds:
            return
            
        try: winsound.Beep(1000, 200)
        except: pass
        
        self.last_decoded = data
        self.last_scan_time = now
        
        # UI Update (Minimal, Thread-Safe)
        try:
            if self.window.winfo_exists():
                txt = f"✅ Scanned: {data}"
                self.window.after(0, lambda: self.status_var.set(txt))
                self.window.after(0, lambda: self.status_label.configure(fg=T.PRIMARY))
        except: pass
        
        if not self.continuous:
            self.running = False
            self.window.after(100, lambda: self._finish(data))
        else:
            if self.callback:
                self.window.after(0, lambda: self.callback(data))

    def _finish(self, data):
        self.close()
        if self.callback:
            self.callback(data)

    def close(self):
        self.running = False
        try: self.window.destroy()
        except: pass

def open_scanner(parent, callback, title="Scan Barcode", continuous=False):
    return CameraScanner(parent, title=title, callback=callback, continuous=continuous)
