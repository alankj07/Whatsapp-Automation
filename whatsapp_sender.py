"""
WhatsApp Message Sender — backend sending & scheduling logic.
"""

from __future__ import annotations

import argparse
import ctypes
import datetime
import subprocess
import sys
import time
from ctypes import wintypes
from pywinauto import Application, findwindows
from pywinauto.keyboard import send_keys

# Win32 Clipboard Helpers to avoid external packages like pyperclip
OpenClipboard = ctypes.windll.user32.OpenClipboard
OpenClipboard.argtypes = [wintypes.HWND]
OpenClipboard.restype = wintypes.BOOL

EmptyClipboard = ctypes.windll.user32.EmptyClipboard
EmptyClipboard.argtypes = []
EmptyClipboard.restype = wintypes.BOOL

SetClipboardData = ctypes.windll.user32.SetClipboardData
SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
SetClipboardData.restype = wintypes.HANDLE

CloseClipboard = ctypes.windll.user32.CloseClipboard
CloseClipboard.argtypes = []
CloseClipboard.restype = wintypes.BOOL

CF_UNICODETEXT = 13
CF_HDROP = 15

GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
GlobalAlloc.restype = wintypes.HGLOBAL

GlobalLock = ctypes.windll.kernel32.GlobalLock
GlobalLock.argtypes = [wintypes.HGLOBAL]
GlobalLock.restype = ctypes.c_void_p

GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
GlobalUnlock.argtypes = [wintypes.HGLOBAL]
GlobalUnlock.restype = wintypes.BOOL

GMEM_MOVEABLE = 0x0002

def set_clipboard_text(text: str) -> None:
    """Safely copies a unicode string to the Windows clipboard."""
    if not isinstance(text, str):
        text = str(text)
    encoded = text.encode('utf-16le') + b'\x00\x00'
    h_global = GlobalAlloc(GMEM_MOVEABLE, len(encoded))
    if not h_global:
        raise OSError("GlobalAlloc failed")
    
    ptr = GlobalLock(h_global)
    if not ptr:
        raise OSError("GlobalLock failed")
    
    ctypes.memmove(ptr, encoded, len(encoded))
    GlobalUnlock(h_global)
    
    if not OpenClipboard(None):
        raise OSError("OpenClipboard failed")
    try:
        EmptyClipboard()
        if not SetClipboardData(CF_UNICODETEXT, h_global):
            raise OSError("SetClipboardData failed")
    finally:
        CloseClipboard()


def set_clipboard_files(paths: list[str]) -> None:
    """Copies a list of file paths to the clipboard as CF_HDROP."""
    import struct
    import os
    abs_paths = [os.path.abspath(p) for p in paths]
    joined = "\x00".join(abs_paths) + "\x00\x00"
    data = joined.encode('utf-16le')
    
    # DROPFILES structure is 20 bytes long
    dropfiles_header = struct.pack("IIIII", 20, 0, 0, 0, 1)
    full_data = dropfiles_header + data
    
    h_global = GlobalAlloc(GMEM_MOVEABLE, len(full_data))
    if not h_global:
        raise OSError("GlobalAlloc failed")
        
    ptr = GlobalLock(h_global)
    if not ptr:
        raise OSError("GlobalLock failed")
        
    try:
        ctypes.memmove(ptr, full_data, len(full_data))
    finally:
        GlobalUnlock(h_global)
        
    if not OpenClipboard(None):
        raise OSError("OpenClipboard failed")
    try:
        EmptyClipboard()
        if not SetClipboardData(CF_HDROP, h_global):
            raise OSError("SetClipboardData failed")
    finally:
        CloseClipboard()


def force_foreground(hwnd: int) -> None:
    """Restores the window if minimized and forces it to the foreground, bypassing Windows focus locks."""
    # SW_RESTORE = 9, SW_SHOW = 5
    if ctypes.windll.user32.IsIconic(hwnd):
        ctypes.windll.user32.ShowWindow(hwnd, 9)
    else:
        ctypes.windll.user32.ShowWindow(hwnd, 5)
        
    # Alt key bypass to release Windows focus lock
    try:
        # VK_MENU = 0x12, KEYEVENTF_KEYUP = 0x0002
        ctypes.windll.user32.keybd_event(0x12, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x12, 0, 2, 0)
    except Exception:
        pass

    ctypes.windll.user32.SetForegroundWindow(hwnd)
        
    fore_hwnd = ctypes.windll.user32.GetForegroundWindow()
    if fore_hwnd != hwnd:
        try:
            fore_thread = ctypes.windll.user32.GetWindowThreadProcessId(fore_hwnd, None)
            target_thread = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
            if fore_thread != target_thread:
                ctypes.windll.user32.AttachThreadInput(fore_thread, target_thread, True)
                ctypes.windll.user32.SetForegroundWindow(hwnd)
                ctypes.windll.user32.AttachThreadInput(fore_thread, target_thread, False)
        except Exception:
            pass

    # Use pywinauto set_focus as a robust fallback
    try:
        app = Application().connect(handle=hwnd)
        app.top_window().set_focus()
    except Exception:
        pass
        
    ctypes.windll.user32.SetActiveWindow(hwnd)


def normalize_phone(phone: str, default_country_code: str = "91") -> str:
    """Normalizes phone number by removing non-digits and prepending country code if 10 digits."""
    digits = "".join(c for c in phone if c.isdigit())
    if not digits:
        raise ValueError("Phone number contains no digits.")
    
    if len(digits) == 10:
        cc = "".join(c for c in default_country_code if c.isdigit())
        if not cc:
            cc = "91"
        digits = cc + digits
    return digits


def _parse_date(date_str: str) -> datetime.date:
    """Parses date string in YYYY-MM-DD format."""
    try:
        return datetime.datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError("Date must be in YYYY-MM-DD format.")


def _parse_time(time_str: str) -> datetime.time:
    """Parses time string in HH:MM format."""
    try:
        return datetime.datetime.strptime(time_str.strip(), "%H:%M").time()
    except ValueError:
        raise ValueError("Time must be in HH:MM (24-hour) format.")


def wait_until(send_at: datetime.datetime, on_status: callable, should_stop: callable) -> bool:
    """Blocks execution until target time is reached, reporting status periodically."""
    while datetime.datetime.now() < send_at:
        if should_stop():
            return False
        diff = send_at - datetime.datetime.now()
        seconds = diff.total_seconds()
        if seconds > 60:
            on_status(f"Waiting... Send in {int(seconds // 60)} min")
            time.sleep(min(5, seconds - 60))
        else:
            on_status(f"Waiting... Send in {int(seconds)} sec")
            time.sleep(0.5)
    return True


def prepare_whatsapp_chat(
    phone: str,
    default_country_code: str = "91",
    on_status: callable = None,
    show_cmd: int = 7,  # SW_SHOWMINNOACTIVE = 7 by default (opens minimized/background)
) -> int | None:
    """Opens WhatsApp Desktop and loads the target chat. Returns the window handle (hwnd) if found."""
    if on_status is None:
        on_status = lambda msg: print(msg)

    on_status("Normalizing phone number...")
    normalized = normalize_phone(phone, default_country_code)

    on_status("Opening WhatsApp...")
    url = f"whatsapp://send?phone={normalized}"
    try:
        # Use Win32 ShellExecuteW to launch the protocol with show_cmd (keeps window inactive/minimized)
        ctypes.windll.shell32.ShellExecuteW(None, "open", url, None, None, show_cmd)
    except Exception:
        # Fallback to subprocess start if ShellExecuteW fails
        subprocess.Popen(f"start {url}", shell=True)

    on_status("Connecting to WhatsApp window...")
    hwnd = None
    # Wait for the WhatsApp window to appear
    for attempt in range(75):  # 75 attempts * 0.2s = 15s max timeout
        try:
            # Look for any window matching the WhatsApp class that contains "whatsapp" in its title
            elements = [
                el for el in findwindows.find_elements(class_name="WinUIDesktopWin32WindowClass")
                if el.name and "whatsapp" in el.name.lower()
            ]
            if elements:
                hwnd = elements[0].handle
                break
        except Exception:
            pass
        time.sleep(0.2)

    if not hwnd:
        on_status("Error: Could not locate WhatsApp window. Ensure WhatsApp Desktop is installed.")
    return hwnd


def send_whatsapp_prepared(
    hwnd: int,
    message: str | None = None,
    skip_send: bool = False,
    on_status: callable = None,
    wait_delay: float = 5.0,
    files: list[str] | None = None,
) -> bool:
    """Focuses the already loaded WhatsApp window, pastes the message and files, and sends them."""
    if on_status is None:
        on_status = lambda msg: print(msg)

    on_status("Focusing WhatsApp...")
    force_foreground(hwnd)
    time.sleep(0.5)

    on_status("Waiting for chat to load...")
    time.sleep(wait_delay)  # Wait for page/chat loading and focus

    if message:
        # Restore focus right before typing/pasting
        try:
            force_foreground(hwnd)
            time.sleep(0.5)
        except Exception:
            pass

        on_status("Copying message to clipboard...")
        set_clipboard_text(message)
        time.sleep(0.1)

        on_status("Pasting message...")
        send_keys("^v")
        time.sleep(0.4)

        if not skip_send:
            on_status("Sending message...")
            send_keys("{ENTER}")
            time.sleep(0.5)
        else:
            on_status("Message pasted (Open chat only).")

    if files:
        # Restore focus right before typing/pasting
        try:
            force_foreground(hwnd)
            time.sleep(0.5)
        except Exception:
            pass

        on_status(f"Copying {len(files)} file(s) to clipboard...")
        set_clipboard_files(files)
        time.sleep(0.1)

        on_status("Pasting file(s)...")
        send_keys("^v")

        # Files take a bit of time to load in the WhatsApp UI
        on_status("Waiting for media preview to load...")
        time.sleep(2.0)

        try:
            force_foreground(hwnd)
            time.sleep(0.5)
        except Exception:
            pass

        if not skip_send:
            on_status("Sending file(s)...")
            send_keys("{ENTER}")
            time.sleep(0.5)
        else:
            on_status("File(s) pasted (Open chat only).")

    return True


def send_whatsapp_message(
    phone: str,
    message: str | None = None,
    default_country_code: str = "91",
    skip_send: bool = False,
    on_status: callable = None,
    wait_delay: float = 5.0,
    files: list[str] | None = None,
) -> bool:
    """Opens WhatsApp Desktop, loads target chat, pastes the message, and sends it (legacy compatibility)."""
    # For immediate send, we want to show it normally (show_cmd = 5)
    hwnd = prepare_whatsapp_chat(phone, default_country_code, on_status, show_cmd=5)
    if not hwnd:
        return False
    return send_whatsapp_prepared(hwnd, message, skip_send, on_status, wait_delay, files)


def main() -> None:
    """CLI mode entry point."""
    parser = argparse.ArgumentParser(description="WhatsApp Scheduled Message Sender CLI")
    parser.add_argument("--phone", help="Recipient phone number", required=True)
    parser.add_argument("--message", help="Message text", required=True)
    parser.add_argument("--cc", help="Default country code", default="91")
    parser.add_argument("--open-only", action="store_true", help="Open chat only, do not send")
    parser.add_argument("--time", help="Time to send (HH:MM) - schedules for today")
    parser.add_argument("--delay", type=float, default=5.0, help="Wait delay for chat loading in seconds")
    
    args = parser.parse_args()
    
    phone = args.phone
    message = args.message
    country = args.cc
    skip_send = args.open_only
    delay = args.delay
    
    if args.time:
        t = _parse_time(args.time)
        dt = datetime.datetime.now()
        send_at = datetime.datetime.combine(dt.date(), t)
        if send_at <= datetime.datetime.now():
            # If time has passed today, schedule for tomorrow
            send_at += datetime.timedelta(days=1)
        print(f"Scheduled for {send_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Simple stop check function for CLI
        should_stop = lambda: False
        wait_until(send_at, print, should_stop)
        
    send_whatsapp_message(phone, message, country, skip_send, print, wait_delay=delay)


if __name__ == "__main__":
    main()
