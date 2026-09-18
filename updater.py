import os
import sys
import urllib.request
import json
import subprocess
import tempfile
import webbrowser
from tkinter import messagebox

# The version of this software instance
CURRENT_VERSION = "1.0.0"

# The URL where your version.json file is hosted on GitHub
VERSION_INFO_URL = "https://raw.githubusercontent.com/NEPAAA-01/RealMart/main/version.json"

def get_current_version():
    return CURRENT_VERSION

def check_for_updates(quiet=False):
    """
    Checks if a new version is available using standard urllib (no dependencies required).
    """
    try:
        req = urllib.request.Request(VERSION_INFO_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                latest_version = str(data.get("version", CURRENT_VERSION)).strip()
                curr_version = CURRENT_VERSION.strip()
                update_url = data.get("url", "")
                changelog = data.get("changelog", "No description provided.")

                # DEBUG: Print versions to terminal
                print(f"Update Check: Local={curr_version}, Remote={latest_version}")

                if latest_version > curr_version:
                    msg = f"A new version ({latest_version}) is available!\n\nWhat's New:\n{changelog}\n\nWould you like to download it now?"
                    if messagebox.askyesno("Update Available", msg):
                        start_update_process(update_url)
                    return True
                else:
                    if not quiet:
                        messagebox.showinfo("Up to Date", f"You are running the latest version ({CURRENT_VERSION}).")
                    return False
            else:
                if not quiet:
                    messagebox.showerror("Update Error", f"Could not reach update server (Status: {response.status})")
    except Exception as e:
        if not quiet:
            # We don't show error if it's just a 404 (file not uploaded yet)
            if "404" in str(e):
                messagebox.showwarning("Update Center", "Your version.json is not found on GitHub yet.\nMake sure you uploaded it to the 'main' branch.")
            else:
                messagebox.showerror("Update Error", f"Failed to check for updates:\n{str(e)}")
    return False

def check_in_background(root):
    """
    Runs the update check in a separate thread and prompts the user on the main thread if needed.
    This prevents the UI from freezing during startup.
    """
    import threading
    def _run():
        # Perform check quietly (no popups for 'up to date' or minor errors)
        try:
            req = urllib.request.Request(VERSION_INFO_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    latest_version = data.get("version", CURRENT_VERSION)
                    update_url = data.get("url", "")
                    changelog = data.get("changelog", "No description provided.")

                    if latest_version > CURRENT_VERSION:
                        # Found update! Schedule the prompt on the main thread
                        root.after(0, lambda: _prompt_update(latest_version, update_url, changelog))
        except:
            # Silently fail in background mode to avoid disturbing the user
            pass

    def _prompt_update(latest_version, update_url, changelog):
        msg = f"🚀 A new version ({latest_version}) of Real Mart is available!\n\nWhat's New:\n{changelog}\n\nWould you like to install the update now?"
        if messagebox.askyesno("Update Available", msg, parent=root):
            start_update_process(update_url)

    threading.Thread(target=_run, daemon=True).start()

def start_update_process(url):
    """
    Downloads the new installer and runs it using standard urllib.
    """
    try:
        if url.endswith(".exe") or url.endswith(".msi"):
            messagebox.showinfo("Downloading", "The update will download in the background. Please wait for the installer to launch.")
            
            # Download to temp
            temp_dir = tempfile.gettempdir()
            filename = os.path.join(temp_dir, "RealMart_Setup_New.exe")
            
            urllib.request.urlretrieve(url, filename)
            
            # Run the installer and exit this app
            subprocess.Popen([filename], shell=True)
            sys.exit(0)
        else:
            # If it's a website/github release page, just open it
            webbrowser.open(url)
            messagebox.showinfo("Update", "Please download and install the new version from the opened page.")
            
    except Exception as e:
        messagebox.showerror("Download Failed", f"Could not download update:\n{str(e)}")

if __name__ == "__main__":
    check_for_updates()
