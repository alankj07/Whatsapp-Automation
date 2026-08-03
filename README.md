# WhatsMation — WhatsApp Message Sender

Desktop app for **Windows** that composes WhatsApp messages, schedules delivery, and sends them through **WhatsApp Desktop** (Microsoft Store) using deep links and UI automation.

![Platform](https://img.shields.io/badge/platform-Windows-blue)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Modern Premium Theme**: Styled with a customized dark green/deep dark slate color scheme inspired by WhatsApp Desktop.
- **Graphical Interface**: Fully-featured desktop UI (with responsive grids, smooth canvas ease-out scroll motions, and animated hover button state transitions).
- **Send to Any Number**: Select country code and input 10-digit local number (dynamically expands for multiple numbers).
- **Scheduled Sending**: Send immediately or schedule for a future date and time.
- **High-Visibility Selection**: Highlight selected historical messages in prominent Neon Green (`#00e676`) with dark text for easy visual checks.
- **Open Chat Only**: Pre-fill the message in WhatsApp without triggering the final send keystroke.
- **Reliable Automation**: Connects directly to the official WhatsApp Desktop app via native Windows APIs (`pywinauto`).

---

## Requirements

- **Windows 10/11**
- **Python 3.10+** ([python.org](https://www.python.org/downloads/))
- **WhatsApp Desktop** from the Microsoft Store, logged in
- Python dependencies listed in `requirements.txt`

---

## Installation & Running Locally

1. Clone this repository:

   ```bash
   git clone https://github.com/alankj07/whatsapp-message-sender.git
   cd whatsapp-message-sender
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Launch Graphical Application:

   ```bash
   .venv\Scripts\python.exe whatsapp_gui.py
   ```

---

## Building Production Release Packages (.exe / Setup / Zip)

To generate clean Windows executables without triggering Windows Defender or SmartScreen false positives:

```bash
.venv\Scripts\python.exe build_release.py
```

This automated build process performs:
1. **Windows Version Metadata Injection**: Embeds binary version details (`FileVersion`, `ProductName`, `CompanyName`) into the `.exe` via `file_version_info.txt`.
2. **UPX Compression Removal**: Disables UPX packing (`upx=False`) to avoid heuristic false positives in antivirus engines.
3. **Inno Setup Installer Generation**: Compiles `WhatsMation-v1.0.0-Setup.exe` with standard Windows installation, start menu shortcuts, and uninstaller.
4. **Portable ZIP Creation**: Generates `WhatsMation-v1.0.0-Portable.zip` ready for GitHub Releases.

All compiled artifacts are saved into the **`dist_release/`** directory.

> [!NOTE]
> For a comprehensive guide on resolving Windows Security SmartScreen warnings, submitting false positives to Microsoft Security Intelligence (WDSI), and native C compilation using Nuitka, see **[DISTRIBUTION_GUIDE.md](DISTRIBUTION_GUIDE.md)**.

---

## Project Files

| File / Folder | Purpose |
|---------------|---------|
| `whatsapp_gui.py` | Premium dark themed user interface and workflow manager |
| `whatsapp_sender.py` | Core sending logic, clipboard APIs, and scheduler |
| `build_release.py` | Automated build pipeline script |
| `WhatsMation.spec` | PyInstaller build specification file |
| `file_version_info.txt` | Windows binary version resource specification |
| `WhatsMation_Setup.iss` | Inno Setup installer script |
| `sign_app.ps1` | PowerShell script for local code signing |
| `DISTRIBUTION_GUIDE.md` | Security, distribution, and Microsoft whitelisting guide |
| `app_icon.ico` | Application branding icon file |
| `requirements.txt` | Python package dependencies |
| `sent_history.json` | Log file containing successfully sent / failed history data |
| `LICENSE` | MIT Open-source license agreement |

---

## Disclaimer

This tool automates the official WhatsApp Desktop app on your own PC. Use it responsibly and in line with [WhatsApp’s terms of service](https://www.whatsapp.com/legal/terms-of-service). The authors are not affiliated with WhatsApp/Meta.

---

## Developer

**ALAN KJ**  

- GitHub: [@alankj07](https://github.com/alankj07)
- Instagram: [@_storiesof.kj_](https://www.instagram.com/_storiesof.kj_)
- WhatsApp: [WhatsApp: +91 8921084834](https://wa.me/918921084834)

---

## License

MIT License — see [LICENSE](LICENSE).
