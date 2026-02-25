"""Create a desktop shortcut for Bar Cart (Windows)."""
import os
import sys
import subprocess
import tempfile

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SHORTCUT_NAME = "Bar Cart.lnk"
TARGET = os.path.join(APP_DIR, "start.pyw")
ICON = os.path.join(APP_DIR, "bar_cart.ico")


def get_desktop():
    """Return the actual Desktop path, handling OneDrive redirection."""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders",
        )
        desktop, _ = winreg.QueryValueEx(key, "Desktop")
        winreg.CloseKey(key)
        desktop = os.path.expandvars(desktop)
        if os.path.isdir(desktop):
            return desktop
    except Exception:
        pass

    for candidate in [
        os.path.join(os.environ["USERPROFILE"], "OneDrive", "Desktop"),
        os.path.join(os.environ["USERPROFILE"], "Desktop"),
    ]:
        if os.path.isdir(candidate):
            return candidate

    return os.path.join(os.environ["USERPROFILE"], "Desktop")


def create_shortcut():
    desktop = get_desktop()
    shortcut_path = os.path.join(desktop, SHORTCUT_NAME)

    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = "pythonw.exe"

    icon_arg = f'sc.IconLocation = "{ICON},0"\n' if os.path.exists(ICON) else ""

    vbs = tempfile.NamedTemporaryFile(mode="w", suffix=".vbs", delete=False)
    try:
        vbs.write(
            'Set ws = WScript.CreateObject("WScript.Shell")\n'
            f'Set sc = ws.CreateShortcut("{shortcut_path}")\n'
            f'sc.TargetPath = "{pythonw}"\n'
            f'sc.Arguments = """{TARGET}"""\n'
            f'sc.WorkingDirectory = "{APP_DIR}"\n'
            f'{icon_arg}'
            f'sc.Description = "Launch Bar Cart"\n'
            "sc.Save\n"
        )
        vbs.close()
        subprocess.run(["cscript", "//NoLogo", vbs.name], check=True)
    finally:
        os.unlink(vbs.name)

    print(f"Desktop shortcut created: {shortcut_path}")


if __name__ == "__main__":
    if sys.platform != "win32":
        print("This installer is for Windows only.")
        sys.exit(1)

    if not os.path.exists(TARGET):
        print(f"Error: {TARGET} not found. Run from the bar-cart directory.")
        sys.exit(1)

    try:
        create_shortcut()
        print("Done! Double-click 'Bar Cart' on your desktop to launch.")
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        sys.exit(1)
