import os
import subprocess
import sys

def build_app():
    print("Starting Real Mart Build Process...")
    
    # 1. Install PyInstaller if not present
    try:
        import PyInstaller
    except ImportError:
        print("Installing PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

    # 2. Define the command
    # --noconsole: Hides the black command prompt window when opening the app
    # --onefile: Bundles everything into a single EXE (can be slower to start)
    # --onedir: Creates a folder with the EXE (faster and better for assets like images)
    # --add-data: Includes your images and database
    
    # 2. Dynamically locate pyzbar DLLs
    try:
        import pyzbar
        pyzbar_path = os.path.dirname(pyzbar.__file__)
        print(f"Located pyzbar at: {pyzbar_path}")
        
        # Check for the required DLLs
        iconv = os.path.join(pyzbar_path, "libiconv.dll")
        zbar64 = os.path.join(pyzbar_path, "libzbar-64.dll")
        
        if not os.path.exists(iconv) or not os.path.exists(zbar64):
            # Try to find them in the 'site-packages' parent if not in the direct module
            print("DLLs not found in direct path, checking package root...")
            # Some versions of pyzbar might have them slightly higher up
            
    except ImportError:
        print("Installing pyzbar...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyzbar"])
        import pyzbar
        pyzbar_path = os.path.dirname(pyzbar.__file__)

    # Use ; for Windows paths
    separator = ";"
    
    cmd = [
        "pyinstaller",
        "--noconsole",
        "--onedir",
        "--name=RealMart",
        f"--add-data=images{separator}images",
        f"--add-data=Database{separator}Database",
        f"--add-data=fonts{separator}fonts",
        f"--add-data=bills{separator}bills",
        f"--add-data={os.path.join(pyzbar_path, 'libiconv.dll')}{separator}.",
        f"--add-data={os.path.join(pyzbar_path, 'libzbar-64.dll')}{separator}.",
        "--clean",
        "--icon=images/app_icon.ico",
        "-y",
        "main.py"
    ]

    print(f"Running build command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\nBUILD SUCCESSFUL!")
        print("--------------------------------------------------")
        print("Your application is ready in the 'dist/RealMart' folder.")
        print("You can now copy the 'dist/RealMart' folder to any PC.")
        print("Just run 'RealMart.exe' inside that folder to start.")
        print("--------------------------------------------------")
    except Exception as e:
        print(f"\nBuild failed: {e}")

if __name__ == "__main__":
    build_app()
