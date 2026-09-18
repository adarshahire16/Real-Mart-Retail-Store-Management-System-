"""
Fresh market · light organic design system for Real Mart (tkinter).

Palette: forest greens, warm wood accents, soft citrus highlights — premium grocery UI.
Legacy names ORANGE / ORANGE_* map to primary greens so existing screens keep working.
"""
import sys
import os
import math
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk, ImageOps, ImageFilter, ImageEnhance, ImageDraw


def check_tkinter_or_exit():
    """
    Fail fast with a clear message if Tcl/Tk is missing (common with broken
    or partial Python installs, e.g. wrong PATH to python.exe).
    """
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            import ctypes
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    try:
        import tkinter
    except ImportError as e:
        msg = (
            "Real Mart could not find the Tkinter module.\n\n"
            "What to do:\n"
            "1. Install or repair Python from https://www.python.org/downloads/\n"
            '   Enable "tcl/tk and IDLE" in the installer.\n'
            "2. Avoid embedded/incomplete Python builds that omit Tcl."
        )
        print(msg, file=sys.stderr)
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "Real Mart — Tkinter error", 0x10)
        except Exception:
            pass
        raise SystemExit(1) from e


# —— Palette (Light organic green & white theme) ——
BG_ROOT = "#F4F7F4"  # Very soft green-tinted white
BG_ELEVATED = "#FFFFFF"
BG_PANEL = "#FFFFFF"
CARD = "#FFFFFF"
CARD_SOFT = "#F8FAF8"

# —— Background System Config ——
class Backgrounds:
    HUB   = "images/background.png"
    ADMIN = "images/admin_login_bg.png"
    POS   = "images/staff_login_bg.png"

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # If not frozen, use the folder where main.py/theme.py is
        base_path = os.path.dirname(os.path.abspath(__file__))

    return os.path.join(base_path, relative_path)


# Primary = forest green (kept as ORANGE* for backward compatibility)
PRIMARY = "#2E7D32"
PRIMARY_LIGHT = "#4CAF50"
PRIMARY_DIM = "#1B5E20"
ACCENT_SUN = "#FFB74D"
ACCENT_SUN_SOFT = "#312F24"
WOOD_BORDER = "#403D34"
WOOD_MUTED = "#554C47"

ORANGE = PRIMARY
ORANGE_HOVER = PRIMARY_LIGHT
ORANGE_DIM = PRIMARY_DIM
ORANGE_GLOW = PRIMARY_LIGHT

# —— Standard Buttons ——
BTN_GREEN = "#2E7D32" # Forest green
BTN_HOVER = "#1B5E20" # Darker green for hover

WHITE = "#FFFFFF"
TEXT_ON_DARK = "#FFFFFF"
TEXT_MUTED = "#5C665C"
TEXT_ON_LIGHT = "#1A1C1A"
TEXT_SUB = "#384038"

BORDER_SUBTLE = "#DAE0DA"
SHADOW = "#D0D0D0"
TRANSPARENT_TAG = "transparent_theme"

# Prefer Inter / Poppins if the OS lists them; otherwise Segoe UI.
_FONT_FAMILY_CACHE = None
def _pick_ui_family():
    global _FONT_FAMILY_CACHE
    if _FONT_FAMILY_CACHE: return _FONT_FAMILY_CACHE
    
    import tkinter.font as tkfont
    # If a Tk instance already exists, use it. Otherwise, return Segoe UI default fast to prevent import-time lag
    try:
        r = getattr(tk, "_default_root", None)
        if not r:
            return "Segoe UI"
            
        fams = set(tkfont.families())
        for name in ("Inter", "Inter Medium", "Poppins Medium", "Poppins", "Segoe UI Variable Display", "Segoe UI"):
            if name in fams:
                _FONT_FAMILY_CACHE = name
                break
    except Exception:
        _FONT_FAMILY_CACHE = "Segoe UI"
    
    if not _FONT_FAMILY_CACHE: _FONT_FAMILY_CACHE = "Segoe UI"
    return _FONT_FAMILY_CACHE

# Delay heavy font lookup until first use or manual call
FONT_FAMILY = "Segoe UI" # Default placeholder

ZOOM_FACTOR = 0

def update_zoom(amount):
    global ZOOM_FACTOR
    ZOOM_FACTOR += amount
    _refresh_fonts()

def _refresh_fonts():
    global FONT_UI, FONT_UI_SM, FONT_BTN, FONT_SECTION, FONT_TITLE, FONT_TITLE_MD, FONT_TITLE_LG, FONT_HERO, FONT_SMALL, FONT_MONO, FONT_FAMILY
    FONT_FAMILY = _pick_ui_family()
    FONT_UI = (FONT_FAMILY, 10 + ZOOM_FACTOR)
    FONT_UI_SM = (FONT_FAMILY, 9 + ZOOM_FACTOR)
    FONT_BTN = (FONT_FAMILY, 10 + ZOOM_FACTOR, "bold")
    FONT_SECTION = (FONT_FAMILY, 11 + ZOOM_FACTOR, "bold")
    FONT_TITLE_MD = (FONT_FAMILY, 16 + ZOOM_FACTOR, "bold")
    FONT_TITLE = (FONT_FAMILY, 22 + ZOOM_FACTOR, "bold")
    FONT_TITLE_LG = (FONT_FAMILY, 28 + ZOOM_FACTOR, "bold")
    FONT_HERO = (FONT_FAMILY, 32 + ZOOM_FACTOR, "bold")
    FONT_SMALL = (FONT_FAMILY, 8 + ZOOM_FACTOR)
    FONT_MONO = ("Consolas", 10 + ZOOM_FACTOR)

_refresh_fonts()


def setup_ttk(master):
    try:
        master.tk.call('tk', 'scaling', 1.3333333333333333)
    except:
        pass
    _refresh_fonts()
    s = ttk.Style(master)
    try:
        s.theme_use("clam")
    except tk.TclError:
        pass  # pragma: no cover

    s.configure("RM.TFrame", background=BG_ROOT)
    s.configure("RM.Card.TFrame", background=CARD)

    s.configure(
        "RM.Treeview",
        background=WHITE,
        fieldbackground=WHITE,
        foreground=TEXT_ON_LIGHT,
        rowheight=40,
        font=FONT_UI,
        borderwidth=0,
        relief="flat"
    )
    s.configure(
        "RM.Treeview.Heading",
        background=PRIMARY, # Strong Forest Green
        foreground=WHITE,    # High contrast text
        font=(FONT_FAMILY, 10, "bold"),
        relief="flat",
        borderwidth=1
    )
    s.map(
        "RM.Treeview.Heading",
        background=[("active", PRIMARY_DIM)], # Darker on hover
    )
    s.map(
        "RM.Treeview",
        background=[("selected", "#2E7D32")],
        foreground=[("selected", "#FFFFFF")],
    )

    s.configure(
        "RM.TCombobox",
        fieldbackground=WHITE,
        background="#F5F7F5",
        foreground=TEXT_ON_LIGHT,
        arrowcolor=PRIMARY,
        padding=10,
    )
    s.map("RM.TCombobox", fieldbackground=[("readonly", WHITE)])

    s.configure(
        "RM.TEntry",
        fieldbackground=WHITE,
        foreground=TEXT_ON_LIGHT,
        padding=10,
    )

    # —— DEFINTIVE GLOBAL TREEVIEW COLUMN LOCK ——
    def handle_tree_press(event):
        try:
            # Check if the user is clicking on the column separator
            region = event.widget.identify("region", event.x, event.y)
            if region == "separator":
                return "break" # Block resizing attempt
            
            # For all other regions (cell, heading, etc.), allow standard behavior
            # by calling the internal Tcl/Tk Treeview Press handler manually.
            # This ensures selection and column moving still work perfectly.
            event.widget.tk.call('ttk::treeview::Press', event.widget._w, event.x, event.y)
        except: pass
        return "break"

    def handle_tree_drag(event):
        try:
            # Prevent the dragging motion if it's a resize attempt
            if event.widget.identify("region", event.x, event.y) == "separator":
                return "break"
            # Otherwise, allow the standard drag logic (like reordering columns)
            event.widget.tk.call('ttk::treeview::Drag', event.widget._w, event.x, event.y)
        except: pass
        return "break"

    def disable_tree_cursor(event):
        try:
            # Force the cursor to stay as a standard arrow over separators
            if event.widget.identify("region", event.x, event.y) == "separator":
                event.widget.configure(cursor="arrow")
                return "break"
        except: pass

    # Replace class-level bindings (no '+' used here for press/drag) 
    # to ensure our logic runs instead of the default Tcl script.
    master.bind_class("Treeview", "<Button-1>", handle_tree_press)
    master.bind_class("Treeview", "<B1-Motion>", handle_tree_drag)
def apply_zebra_styling(tree):
    """Configures a treeview with modern alternating row colors."""
    tree.tag_configure("odd", background="#FFFFFF")
    tree.tag_configure("even", background="#F4F8F4") # Soft sage zebra stripe


_DPI_CACHE = None
def get_dpi_factor(window=None):
    """Calculates the physical vs logical pixel ratio for high-DPI crystal clear rendering."""
    global _DPI_CACHE
    if _DPI_CACHE is not None: return _DPI_CACHE
    try:
        # Standard Tkinter uses 72 or 96 DPI as '100%'. 
        # Use provided window or fall back to default root
        target = window or tk._default_root
        if not target:
            return 1.0
        _DPI_CACHE = target.winfo_fpixels('1i') / 96.0
        return _DPI_CACHE
    except:
        return 1.0

_RAW_IMAGE_CACHE = {}
_PHOTO_IMAGE_CACHE = {} # Global cache for fitted PhotoImage objects
_GLASS_CACHE = {}       # Global cache for rounded panels and shapes

def get_raw_image(path, dim=None):
    """Memory Cache to prevent redundant disk I/O and pre-process heavy backgrounds."""
    global _RAW_IMAGE_CACHE
    abs_path = get_resource_path(path)
    
    cache_key = (abs_path, dim)
    if cache_key not in _RAW_IMAGE_CACHE:
        if not os.path.exists(abs_path): return None
        try:
            img = Image.open(abs_path)
            img.load()
            
            # If dimming is requested, apply it once and cache the result
            if dim is not None:
                enhancer = ImageEnhance.Brightness(img)
                img = enhancer.enhance(dim)
                
            _RAW_IMAGE_CACHE[cache_key] = img
        except Exception as e:
            print(f"IMAGE ERROR: Failed to load {abs_path} - {e}")
            return None
    return _RAW_IMAGE_CACHE[cache_key]

def warm_up_backgrounds():
    """Background thread to pre-load and pre-dim heavy images to prevent UI lag."""
    import threading
    def _task():
        # 1. Pre-load and pre-dim the common background assets
        for bg in [Backgrounds.HUB, Backgrounds.ADMIN, Backgrounds.POS]:
            get_raw_image(bg, dim=0.85)
            
        # 2. Pre-cache common font lookup
        _pick_ui_family()
        
    threading.Thread(target=_task, daemon=True).start()

def style_root(window):
    """ Sets the root window background to a dark tone that blends with the UI theme. """
    try:
        window.tk.call('tk', 'scaling', 1.3333333333333333)
    except:
        pass
    window.configure(bg=BG_ROOT)

def clear_bg_image(window):
    """Removes any background images and stops automatic redraws on this window."""
    try:
        # Unbind the redraw trigger
        window.unbind("<Configure>")
        # Remove any existing bg widgets
        for child in window.winfo_children():
            if getattr(child, "_is_bg_label", False) or getattr(child, "_is_bg_canvas", False):
                child.destroy()
        if hasattr(window, "_bg_img_ref"):
            del window._bg_img_ref
    except Exception as e:
        print(f"THEME: Failed to clear background: {e}")

def apply_bg_image(window, image_name=Backgrounds.HUB):
    """Draws or preserves the grocery background over the root window seamlessly."""
    try:
        # Check if the parent is a Canvas (common for login/hubs)
        is_canvas = isinstance(window, tk.Canvas)
        
        # Cleanup existing background elements to prevent duplicates
        for child in window.winfo_children():
            if getattr(child, "_is_bg_label", False):
                child.destroy()
        if is_canvas:
            window.delete("bg_image_tag")
                
        bg_img_raw = get_raw_image(image_name)
        if bg_img_raw is None:
            print(f"IMAGE ERROR: get_raw_image returned None for {image_name}")
            return
        
        # Store for reference
        bg_ref = {"img": None}
        
        def update_bg_image(*args):
             if not window.winfo_exists(): return
             window.update_idletasks()
             w = window.winfo_width()
             h = window.winfo_height()
             
             if w < 100 or h < 100:
                 window.after(200, update_bg_image)
                 return
                 
             cache_key = (image_name + "_simple", w, h)
             if cache_key in _PHOTO_IMAGE_CACHE:
                 window._bg_img_ref = _PHOTO_IMAGE_CACHE[cache_key]
                 if is_canvas:
                     window.delete("bg_image_tag")
                     window.create_image(w/2, h/2, image=window._bg_img_ref, tags="bg_image_tag")
                     window.tag_lower("bg_image_tag")
                 else:
                     bg_label = None
                     for child in window.winfo_children():
                         if getattr(child, "_is_bg_label", False):
                             bg_label = child; break
                     if not bg_label:
                         bg_label = tk.Label(window, bg=BG_ROOT)
                         bg_label._is_bg_label = True
                         bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                         tk.Misc.lower(bg_label)
                     bg_label.configure(image=window._bg_img_ref)
                 return
                 
             try:
                 scale = get_dpi_factor(window)
                 pw, ph = int(w * scale), int(h * scale)
                 
                 resample = getattr(Image, 'Resampling', Image).BILINEAR
                 bg_img = ImageOps.fit(bg_img_raw, (pw, ph), resample)
                 
                 enhancer = ImageEnhance.Brightness(bg_img)
                 bg_img = enhancer.enhance(0.75)
                 
                 bg_ref["img"] = ImageTk.PhotoImage(bg_img)
                 # STRONG REFERENCE to prevent garbage collection
                 window._bg_img_ref = bg_ref["img"] 
                 
                 if is_canvas:
                     window.delete("bg_image_tag")
                     window.create_image(w/2, h/2, image=window._bg_img_ref, tags="bg_image_tag")
                     window.tag_lower("bg_image_tag")
                 else:
                     # Standard Label fallback for non-canvas windows
                     bg_label = None
                     for child in window.winfo_children():
                         if getattr(child, "_is_bg_label", False):
                             bg_label = child; break
                     
                     if not bg_label:
                         bg_label = tk.Label(window, bg=BG_ROOT)
                         bg_label._is_bg_label = True
                         bg_label.place(x=0, y=0, relwidth=1, relheight=1)
                         tk.Misc.lower(bg_label)
                     
                     bg_label.configure(image=window._bg_img_ref)
             except Exception as inner_e:
                 print(f"DEBUG ERROR: update_bg_image failed: {inner_e}")
             


        window.bind("<Configure>", lambda e: window.after(100, update_bg_image) if e.widget == window else None, add="+")
        update_bg_image()
            
    except Exception as e:
        print("Failed to apply background image:", e)


def setup_glass_canvas(window, image_name=Backgrounds.HUB):
    """
    Creates a full-screen Canvas that scales a background image automatically.
    Returns the canvas object for direct drawing (transparent text/rects).
    """
    try:
        from PIL import Image, ImageTk, ImageOps
        import threading
        
        # Find existing background layer to prevent duplication and z-order bugs
        for widget in tk.Misc.winfo_children(window):
            if getattr(widget, "_is_bg_canvas", False):
                # If image changed, update reference and refresh
                if getattr(widget, "_image_name", None) != image_name:
                    widget._image_name = image_name
                    widget.bg_img_raw = get_raw_image(image_name, dim=0.85)
                    widget._last_bg_size = None # Force re-render
                if hasattr(widget, "refresh_bg"):
                    widget.refresh_bg()
                return widget

        canvas = tk.Canvas(window, bg=BG_ROOT, highlightthickness=0, borderwidth=0)
        canvas._is_bg_canvas = True  
        canvas._image_name = image_name
        canvas.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.lower(canvas)

        if not image_name:
            return canvas

        canvas.bg_img_raw = get_raw_image(image_name, dim=0.85)
        if canvas.bg_img_raw is None: 
            return canvas

        def apply_bg(photo, w, h):
            """Final step to apply PhotoImage on the main thread."""
            if not canvas.winfo_exists(): return
            canvas.image_ref = photo
            canvas.delete("bg_img")
            canvas.create_image(0, 0, image=canvas.image_ref, anchor="nw", tags="bg_img")
            canvas.tag_lower("bg_img")
            canvas._last_bg_size = (w, h)

        def update_bg():
            if not canvas.winfo_exists(): return
            w, h = window.winfo_width(), window.winfo_height()
            
            if w < 100 or h < 100:
                window.after(100, update_bg)
                return

            if hasattr(canvas, "_last_bg_size") and canvas._last_bg_size == (w, h):
                return
            
            # Check Global Cache for this specific image and size
            current_img = getattr(canvas, "_image_name", image_name)
            cache_key = (current_img, w, h)
            if cache_key in _PHOTO_IMAGE_CACHE:
                apply_bg(_PHOTO_IMAGE_CACHE[cache_key], w, h)
                return

            def _process():
                try:
                    scale = get_dpi_factor(window)
                    pw, ph = int(w * scale), int(h * scale)
                    
                    # PERFORMANCE FIX: Faster resampling for low-end hardware
                    resample = getattr(Image, 'Resampling', Image).BILINEAR
                    
                    # fit is expensive, done in thread
                    fitted = ImageOps.fit(canvas.bg_img_raw, (pw, ph), resample)
                    
                    # PhotoImage must be created on main thread, but we can prepare the image
                    window.after(0, _complete, fitted, w, h)
                except Exception as e:
                    print(f"Async bg error: {e}")

            def _complete(fitted_img, width, height):
                if not canvas.winfo_exists(): return
                photo = ImageTk.PhotoImage(fitted_img)
                _PHOTO_IMAGE_CACHE[cache_key] = photo # Store in global cache
                apply_bg(photo, width, height)

            threading.Thread(target=_process, daemon=True).start()

        canvas.refresh_bg = update_bg

        def on_resize(event):
            if event.widget != window:
                return
            # Only trigger if the size actually changed significantly
            w, h = window.winfo_width(), window.winfo_height()
            if hasattr(canvas, "_last_req_size") and canvas._last_req_size == (w, h):
                return
            canvas._last_req_size = (w, h)
            
            if hasattr(window, "_bg_canvas_job") and window._bg_canvas_job:
                window.after_cancel(window._bg_canvas_job)
            # DEBOUNCE: Reduced to 60ms for snappier window maximization
            window._bg_canvas_job = window.after(60, update_bg)

        window.bind("<Configure>", on_resize, add="+")

        
        # Reduced initial delay for snappier startup
        window.after(50, update_bg)
        return canvas
    except Exception as e:
        print(f"Glass Canvas error: {e}")
        return tk.Canvas(window, bg=BG_ROOT, highlightthickness=0)
    except Exception as e:
        print(f"Glass Canvas error: {e}")
        return tk.Canvas(window, bg=BG_ROOT, highlightthickness=0)


def clear_ui_content(canvas):
    """
    Cleaner for Canvas UI content. 
    Deletes all items with 'ui_content' tag, and explicitly destroys associated widgets
    to prevent memory leaks and 'ghost' overlapping interaction.
    """
    try:
        if not canvas or not canvas.winfo_exists(): return
        
        # 1. Destroy widgets attached to 'ui_content' window items
        for item in canvas.find_withtag("ui_content"):
            try:
                if canvas.type(item) == "window":
                    w_path = canvas.itemconfigure(item, "window")[-1]
                    if w_path:
                        try:
                            w_widget = canvas.nametowidget(w_path)
                            w_widget.destroy()
                        except: pass
            except: pass
        
        # 2. Delete the drawing items
        canvas.delete("ui_content")
        
        # 3. Extra safety: Clear glass panel cache references
        if hasattr(canvas, "_glass_objects"):
            canvas._glass_objects = []
    except: pass


def draw_glass_panel(canvas, x, y, width, height, opacity=0.35, color=(0, 0, 0), radius=30):
    """
    Draws a semi-transparent rounded rectangle on the canvas using a PIL image overlay.
    Matches modern glassmorphic UI patterns with high corner radius.
    """
    from PIL import Image, ImageTk, ImageDraw
    
    # —— Performance Fix: Globalize panel image cache ——
    params = (int(width), int(height), opacity, color, radius)
    
    if params in _GLASS_CACHE:
        photo = _GLASS_CACHE[params]
    else:
        # —— PERFORMANCE FIX: SUPER-SAMPLING (2x) instead of 4x ——
        # 2x is enough for high-DPI screens and 4x faster than 4x
        sw, sh = int(width * 2), int(height * 2)
        sr = int(radius * 2)
        
        # Create larger image with alpha channel
        overlay = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        alpha = int(255 * opacity)
        draw.rounded_rectangle(
            (0, 0, sw, sh), 
            radius=sr, 
            fill=color + (alpha,)
        )
        
        # Downscale with BILINEAR for speed
        resample = getattr(Image, 'Resampling', Image).BILINEAR
        overlay = overlay.resize((int(width), int(height)), resample)
        
        photo = ImageTk.PhotoImage(overlay)
        _GLASS_CACHE[params] = photo
    
    # Store reference on the canvas so it isn't garbage collected
    if not hasattr(canvas, "_glass_objects"):
        canvas._glass_objects = []
    canvas._glass_objects.append(photo)
    
    return canvas.create_image(x, y, image=photo, anchor="center", tags="ui_content")


def draw_rounded_shape(canvas, x, y, width, height, color="#FFFFFF", radius=None, 
                       outline=None, outline_width=0, tags="ui_content"):
    """
    Draws a perfectly smooth rounded rectangle or pill shape using PIL.
    Supports optional outline for better definition on light backgrounds.
    """
    from PIL import Image, ImageTk, ImageDraw
    
    w, h = int(width), int(height)
    if radius is None: radius = h / 2 # Default to Pill shape
    
    # Cache key includes outline properties to avoid collision
    params = (w, h, color, radius, "solid", outline, outline_width)
        
    if params in _GLASS_CACHE:
        photo = _GLASS_CACHE[params]
    else:
        # —— PERFORMANCE FIX: SUPER-SAMPLING (2x) ——
        sw, sh = int(w * 2), int(h * 2)
        sr = int(radius * 2)
        s_outline_w = int(outline_width * 2)
        
        # Create larger image with alpha channel
        overlay = Image.new("RGBA", (sw, sh), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        
        # PIL rounded_rectangle supports fill and outline
        draw.rounded_rectangle(
            (0, 0, sw, sh), 
            radius=sr, 
            fill=color,
            outline=outline,
            width=s_outline_w
        )
        
        # Downscale with BILINEAR
        resample = getattr(Image, 'Resampling', Image).BILINEAR
        overlay = overlay.resize((w, h), resample)
        
        photo = ImageTk.PhotoImage(overlay)
        _GLASS_CACHE[params] = photo

    if not hasattr(canvas, "_glass_objects"):
        canvas._glass_objects = []
    canvas._glass_objects.append(photo)

    return canvas.create_image(x, y, image=photo, anchor="center", tags=tags)


def draw_pill_button(canvas, x, y, width, height, text, color=BTN_GREEN, command=None):
    """
    Creates a high-fidelity, pixel-perfect pill button on the canvas.
    Uses canvas text and shapes to avoid the rectangular limitations of standard Tkinter buttons.
    """
    tag = f"btn_{id(text)}"
    
    # Pre-generate hover color (lighter version of the base color)
    # Simple way to get a lighter color: hex -> rgb -> adjust -> hex
    hover_color = BTN_HOVER if color == BTN_GREEN else "#44444c"
    
    # 1. Draw smooth pill background (Initial state)
    bg_id = draw_rounded_shape(canvas, x, y, width, height, color=color, tags=("ui_content", tag))
    
    # 2. Draw crisp white text
    text_id = canvas.create_text(x, y, text=text, fill=WHITE, font=FONT_BTN, tags=("ui_content", tag))
    
    # 3. Cache images for state swapping
    normal_img = _GLASS_CACHE.get((width, height, color, height/2, "solid"))
    
    # Force creation of hover image so we can swap it
    draw_rounded_shape(canvas, x, y, width, height, color=hover_color, tags=("temp_render"))
    canvas.delete("temp_render") # We just wanted it cached
    hover_img = _GLASS_CACHE.get((width, height, hover_color, height/2, "solid"))

    # 4. Interactive effects
    state = {"hover": False}

    def on_click(e):
        if command:
            # Short delay to allow UI to breathe before potentially heavy login logic
            canvas.after(10, command)
    
    def on_enter(e):
        canvas.config(cursor="hand2")
        if not state["hover"]:
            state["hover"] = True
            if hover_img:
                canvas.itemconfig(bg_id, image=hover_img)

    def on_leave(e):
        canvas.config(cursor="")
        if state["hover"]:
            state["hover"] = False
            if normal_img:
                canvas.itemconfig(bg_id, image=normal_img)


    canvas.tag_bind(tag, "<Button-1>", on_click)
    canvas.tag_bind(tag, "<Enter>", on_enter)
    canvas.tag_bind(tag, "<Leave>", on_leave)
    
    return tag


def animate_slide_up(canvas, tag, distance=35, duration_ms=600):
    """
    [Neutralized] Motion animations removed per user request.
    This function no longer moves or animates UI components.
    """
    pass



def btn_primary(widget):
    widget.configure(
        bg=PRIMARY,
        fg=WHITE,
        activebackground=PRIMARY_LIGHT,
        activeforeground=WHITE,
        relief="flat",
        borderwidth=0,
        cursor="hand2",
        font=FONT_BTN,
        padx=18,
        pady=9,
        highlightthickness=0,
    )

def btn_tab(btn, active=False):
    """
    Modern Pill-style tab button for clean panel navigation.
    Identifiable by background contrast and interaction states.
    """
    if active:
        btn.configure(
            bg=PRIMARY,
            fg=WHITE,
            activebackground=PRIMARY,
            activeforeground=WHITE,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=(FONT_FAMILY, 11, "bold"),
            padx=30,
            pady=10,
            highlightthickness=0,
        )
    else:
        btn.configure(
            bg="#E2E8E2", # Neutral soft background
            fg=TEXT_SUB,
            activebackground="#D0D8D0",
            activeforeground=PRIMARY_DIM,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=(FONT_FAMILY, 11),
            padx=30,
            pady=10,
            highlightthickness=0,
        )

    def _on_enter(e):
        if not active:
            btn.config(bg="#D0D8D0", fg=PRIMARY)
            
    def _on_leave(e):
        if not active:
            btn.config(bg="#E2E8E2", fg=TEXT_SUB)
            
    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)


def btn_white_round(widget):
    widget.configure(
        bg=WHITE,
        fg=PRIMARY,
        activebackground=PRIMARY_DIM,
        activeforeground=WHITE,
        relief="flat",
        borderwidth=0,
        cursor="hand2",
        font=FONT_BTN,
        padx=20,
        pady=8,
        highlightthickness=0,
    )
    # High-visibility hover: Invert colors to match the "clicking" feel
    bind_hover(widget, enter_bg=PRIMARY, leave_bg=WHITE, enter_fg=WHITE, leave_fg=PRIMARY)


def btn_secondary(widget):
    widget.configure(
        bg=CARD,
        fg=PRIMARY_DIM,
        activebackground=CARD_SOFT,
        activeforeground=PRIMARY,
        relief="flat",
        borderwidth=1,
        highlightbackground=WOOD_BORDER,
        highlightcolor=PRIMARY,
        highlightthickness=1,
        cursor="hand2",
        font=FONT_BTN,
        padx=14,
        pady=8,
    )


def btn_ghost(widget):
    widget.configure(
        bg=BG_ROOT,
        fg=TEXT_SUB,
        activebackground=CARD_SOFT,
        activeforeground=PRIMARY,
        relief="flat",
        borderwidth=0,
        cursor="hand2",
        font=FONT_UI,
    )


def entry_light(widget):
    widget.configure(
        relief="flat",
        highlightthickness=1,
        highlightbackground=BORDER_SUBTLE,
        highlightcolor=PRIMARY,
        bg=CARD,
        fg=TEXT_ON_LIGHT,
        insertbackground=TEXT_ON_LIGHT,
        font=FONT_UI,
    )


def label_dark(widget):
    widget.configure(bg=BG_ROOT, fg=TEXT_ON_LIGHT, font=FONT_UI)


def label_muted(widget):
    widget.configure(bg=BG_ROOT, fg=TEXT_MUTED, font=FONT_UI_SM)


def label_on_card(widget):
    widget.configure(bg=CARD, fg=TEXT_ON_LIGHT, font=FONT_UI)


def header_bar(parent, title, right_widget=None):
    """Primary green top bar; returns inner frame for optional extra widgets."""
    bar = tk.Frame(parent, bg=PRIMARY, height=64)
    bar.pack(fill=tk.X)
    bar.pack_propagate(False)
    inner = tk.Frame(bar, bg=PRIMARY)
    inner.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)
    tk.Label(
        inner,
        text=title,
        font=FONT_SECTION,
        bg=PRIMARY,
        fg=WHITE,
    ).pack(side=tk.LEFT)
    if right_widget is not None:
        right_widget.pack(side=tk.RIGHT, padx=(16, 0))
    return bar


def accent_strip(parent):
    """Thin accent under headers."""
    f = tk.Frame(parent, bg=ACCENT_SUN, height=3)
    f.pack(fill=tk.X)
    return f


def bind_hover(widget, enter_bg=BTN_HOVER, leave_bg=BTN_GREEN, enter_fg=None, leave_fg=None):
    """Subtle hover (tkinter has no CSS transitions; instant feedback only)."""

    def on_enter(_):
        widget.configure(bg=enter_bg)
        widget.configure(cursor="hand2")
        if enter_fg is not None:
            widget.configure(fg=enter_fg)

    def on_leave(_):
        widget.configure(bg=leave_bg)
        widget.configure(cursor="")
        if leave_fg is not None:
            widget.configure(fg=leave_fg)

    widget.bind("<Enter>", on_enter)
    widget.bind("<Leave>", on_leave)

def bind_tag_hover(canvas, tag, normal_color=PRIMARY, hover_color=PRIMARY_LIGHT):
    """
    Adds hand cursor and color feedback to a specific canvas tag.
    Used for links and custom buttons.
    """
    def on_enter(e):
        canvas.config(cursor="hand2")
        canvas.itemconfig(tag, fill=hover_color)
    def on_leave(e):
        canvas.config(cursor="")
        canvas.itemconfig(tag, fill=normal_color)
    
    canvas.tag_bind(tag, "<Enter>", on_enter)
    canvas.tag_bind(tag, "<Leave>", on_leave)


