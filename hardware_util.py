import subprocess
import sys
import hashlib
import os

_MACHINE_ID_CACHE = None

def get_machine_id():
    """
    Returns a unique, stable hardware signature for this PC.
    Prioritizes Motherboard Serial Number via PowerShell or WMIC.
    CACHED: The first call performs the slow lookup; subsequent calls are instant.
    """
    global _MACHINE_ID_CACHE
    if _MACHINE_ID_CACHE is not None:
        return _MACHINE_ID_CACHE

    try:
        serial = None
        if sys.platform == "win32":
            # Layer 1: Modern PowerShell (Standard on Win 10/11)
            try:
                ps_cmd = "powershell -NoProfile -Command \"(Get-CimInstance -ClassName Win32_BaseBoard).SerialNumber\""
                proc = subprocess.run(ps_cmd, capture_output=True, text=True, shell=True, timeout=5)
                res = proc.stdout.strip()
                if res and len(res) > 3 and "Default" not in res:
                    serial = res
            except:
                pass

            if not serial:
                # Layer 2: Legacy WMIC (Suppressed errors)
                try:
                    cmd = "wmic baseboard get serialnumber"
                    proc = subprocess.run(cmd, capture_output=True, text=True, shell=True, timeout=5)
                    output = proc.stdout.strip()
                    lines = [l.strip() for l in output.split('\n') if l.strip()]
                    if len(lines) > 1:
                        res = lines[1]
                        if res and len(res) > 3 and "Default" not in res:
                            serial = res
                except:
                    pass
        
        if serial:
            _MACHINE_ID_CACHE = hashlib.sha256(serial.encode()).hexdigest()[:16].upper()
            return _MACHINE_ID_CACHE

        # Layer 3: System UUID (Fallback)
        import uuid
        node = str(uuid.getnode())
        _MACHINE_ID_CACHE = hashlib.sha256(node.encode()).hexdigest()[:16].upper()
        return _MACHINE_ID_CACHE
        
    except Exception:
        # Layer 4: Hostname (Absolute Fallback)
        import platform
        node_name = platform.node() or "UNKNOWN_NODE"
        _MACHINE_ID_CACHE = hashlib.sha256(node_name.encode()).hexdigest()[:16].upper()
        return _MACHINE_ID_CACHE


if __name__ == "__main__":
    print(f"Verified Machine Signature: {get_machine_id()}")
