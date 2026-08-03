"""
WhatsMation Release Builder & Packaging Script
Automates:
1. Cleaning previous build artifacts.
2. Compiling PyInstaller binary with Windows metadata & UPX disabled.
3. Packaging Portable ZIP archive.
4. Locating and running Inno Setup Compiler (ISCC) to build Setup Installer.
"""

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

APP_NAME = "WhatsMation"
VERSION = "1.0.0"
BASE_DIR = Path(__file__).parent.resolve()
DIST_DIR = BASE_DIR / "dist"
BUILD_DIR = BASE_DIR / "build"
RELEASE_DIR = BASE_DIR / "dist_release"
SPEC_FILE = BASE_DIR / "WhatsMation.spec"
ISS_FILE = BASE_DIR / "WhatsMation_Setup.iss"


def clean():
    print("[1/5] Cleaning old build & release artifacts...")
    for p in [DIST_DIR, BUILD_DIR, RELEASE_DIR]:
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    print("      Cleaned successfully.")


def build_pyinstaller():
    print("[2/5] Building Executable with PyInstaller...")

    # Build multi-file directory distribution for setup installer
    cmd_dir = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--noconsole",
        f"--icon={BASE_DIR / 'app_icon.ico'}",
        f"--add-data={BASE_DIR / 'app_icon.ico'};.",
        f"--version-file={BASE_DIR / 'file_version_info.txt'}",
        "--name=WhatsMation",
        str(BASE_DIR / "whatsapp_gui.py"),
    ]
    print(f"      Running PyInstaller (onedir)...")
    res_dir = subprocess.run(cmd_dir, cwd=BASE_DIR)
    if res_dir.returncode != 0:
        print("ERROR: PyInstaller onedir build failed!")
        sys.exit(1)

    # Build standalone single file executable
    cmd_onefile = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--noconsole",
        f"--icon={BASE_DIR / 'app_icon.ico'}",
        f"--add-data={BASE_DIR / 'app_icon.ico'};.",
        f"--version-file={BASE_DIR / 'file_version_info.txt'}",
        "--name=WhatsMation-Standalone",
        str(BASE_DIR / "whatsapp_gui.py"),
    ]
    print(f"      Running PyInstaller (onefile)...")
    res_one = subprocess.run(cmd_onefile, cwd=BASE_DIR)
    if res_one.returncode != 0:
        print("ERROR: PyInstaller onefile build failed!")
        sys.exit(1)

    print("      PyInstaller build completed.")


def make_portable_zip():
    print("[3/5] Creating Portable ZIP Package...")
    portable_zip_path = RELEASE_DIR / f"{APP_NAME}-v{VERSION}-Portable.zip"
    onedir_path = DIST_DIR / APP_NAME

    if not onedir_path.exists():
        print(f"ERROR: {onedir_path} does not exist!")
        sys.exit(1)

    with zipfile.ZipFile(portable_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(onedir_path):
            for file in files:
                abs_file = Path(root) / file
                rel_path = abs_file.relative_to(DIST_DIR)
                zf.write(abs_file, rel_path)

    print(f"      Created Portable ZIP: {portable_zip_path.name}")


def copy_standalone():
    print("[4/5] Copying Standalone Executable to release folder...")
    standalone_src = DIST_DIR / "WhatsMation-Standalone.exe"
    standalone_dst = RELEASE_DIR / f"{APP_NAME}-v{VERSION}-Standalone.exe"
    if standalone_src.exists():
        shutil.copy(standalone_src, standalone_dst)
        print(f"      Copied Standalone EXE: {standalone_dst.name}")


def build_inno_setup():
    print("[5/5] Checking for Inno Setup Compiler (ISCC)...")

    possible_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
    ]

    iscc_path = None
    # Check if iscc is in PATH
    which_iscc = shutil.which("iscc")
    if which_iscc:
        iscc_path = which_iscc
    else:
        for p in possible_paths:
            if os.path.exists(p):
                iscc_path = p
                break

    if iscc_path:
        print(f"      Found Inno Setup Compiler at: {iscc_path}")
        print("      Compiling Setup Installer...")
        res = subprocess.run([iscc_path, str(ISS_FILE)], cwd=BASE_DIR)
        if res.returncode == 0:
            print(f"      Successfully built Setup Installer in 'dist_release/'!")
        else:
            print("      Inno Setup compilation returned non-zero code.")
    else:
        print("      [NOTE] Inno Setup Compiler (ISCC.exe) not found on system.")
        print("             To generate 'WhatsMation-v1.0.0-Setup.exe':")
        print("             1. Download Inno Setup from https://jrsoftware.org/isdl.php")
        print(f"             2. Open and compile '{ISS_FILE.name}' in Inno Setup.")


def main():
    print(f"=== {APP_NAME} v{VERSION} Build & Release Manager ===")
    clean()
    build_pyinstaller()
    make_portable_zip()
    copy_standalone()
    build_inno_setup()

    print("\n==========================================")
    print(" BUILD SUMMARY")
    print("==========================================")
    if RELEASE_DIR.exists():
        for item in RELEASE_DIR.iterdir():
            size_mb = item.stat().st_size / (1024 * 1024)
            print(f" - {item.name:<35} ({size_mb:.2f} MB)")
    print("==========================================\n")


if __name__ == "__main__":
    main()
