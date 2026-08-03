# Publishing WhatsMation to the Microsoft Store

This guide outlines the exact steps to publish **WhatsMation** to the official **Microsoft Store** so Windows users can search for and install it directly from the Store app.

---

## 1. Prerequisites

1. **Microsoft Partner Center Account**:
   - Sign up at [https://partner.microsoft.com/dashboard](https://partner.microsoft.com/dashboard).
   - One-time registration fee: **~$19 USD** (Individual) or **~$99 USD** (Company).
2. **App Assets**:
   - App Icon (`app_icon.ico` / PNG 512x512)
   - 2-4 Application Screenshots
   - Privacy Policy URL (e.g., your GitHub README or a simple GitHub page link)
3. **Installer File**:
   - Either your hosted Setup Installer URL (`WhatsMation-v1.0.0-Setup.exe` hosted on GitHub Releases) OR an `.msix` package.

---

## 2. Recommended Publishing Method: Win32 App Submission (Easiest)

Microsoft Store supports submitting traditional Windows Desktop (`.exe`) installers directly without needing complex app re-tooling.

### Steps:

1. **Log in to Partner Center**:
   - Go to [Microsoft Partner Center](https://partner.microsoft.com/dashboard/apps/overview).
   - Click **Create a new app** and reserve the name **`WhatsMation`**.

2. **Enter App Properties**:
   - **Category**: *Utilities & Tools* or *Productivity*.
   - **Pricing**: *Free*.

3. **Configure Package / Installer Details**:
   - Select **Win32 App**.
   - Provide your **Installer URL** from your GitHub Releases:
     `https://github.com/alankj07/whatsapp-message-sender/releases/download/v1.0.0/WhatsMation-v1.0.0-Setup.exe`
   - Silent Install Command: `/VERYSILENT /NORESTART` (Inno Setup standard silent flags).

4. **Fill in Store Listing**:
   - **Title**: `WhatsMation - WhatsApp Desktop Automation Tool`
   - **Description**: Add features list, WhatsApp Desktop requirements, and usage.
   - **Screenshots**: Upload 2-3 screenshots of the WhatsMation dark GUI.
   - **Icon**: Upload 512x512 icon PNG.
   - **Privacy Policy**: Link to `https://github.com/alankj07/whatsapp-message-sender/blob/main/README.md`.

5. **Submit for Certification**:
   - Click **Submit to the Store**.
   - Microsoft tests and certifies the app within **24 to 48 hours**. Once approved, WhatsMation is live on the Microsoft Store!

---

## 3. Alternative Method: MSIX Package Generation

If you prefer uploading an `.msix` file directly to Microsoft Partner Center instead of linking a URL:

1. Download **MSIX Packaging Tool** from Microsoft Store:
   [https://apps.microsoft.com/detail/9N5LW3JBCXKF](https://apps.microsoft.com/detail/9N5LW3JBCXKF)
2. Open MSIX Packaging Tool -> Select **Application package**.
3. Point to `dist_release/WhatsMation-v1.0.0-Standalone.exe`.
4. The tool will convert it into `WhatsMation.msix`.
5. Upload `WhatsMation.msix` directly in Partner Center.
