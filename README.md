# 🍎 Real Mart: Fresh Market POS
**A high-performance, intelligent retail management system for modern stores.**

Real Mart is a premium Point of Sale (POS) solution that combines clean, organic aesthetics with industrial-grade reliability. Built with Python and computer vision, it transforms your device into a professional retail station.

![Real Mart Theme](https://img.shields.io/badge/Theme-Fresh_Organic_Green-2E7D32)
![Python Version](https://img.shields.io/badge/Python-3.12%2B-blue)
![Database](https://img.shields.io/badge/Database-SQLite-003B57)

---

## ✨ Key Highlights

### 🌿 High-Performance UI
Experience a professional, glassmorphic interface designed for clarity and speed. The **Fresh Organic Green** design system is optimized for high-DPI displays, ensuring every label and button is pixel-perfect.

### 🔍 Vision-Powered Scanning
Say goodbye to manual entry. Integrated barcode detection using **OpenCV** and **PyZbar** allows you to scan products instantly using a laptop camera or high-quality smartphone feed (DroidCam support included).

### ☁️ Digital Cloud Receipts
Go paperless. Real Mart generates professional PDF bills and uploads them to the cloud. Customers can scan a unique **QR code** on the screen to download their receipt instantly.

### 🛡️ Self-Healing Core
- **Auto-Repair**: Detects and fixes environment issues (like broken Tkinter libs) automatically.
- **Zero-Config DB**: Automatically builds and seeds the database with a fresh produce catalog on first launch.
- **Financial Security**: Dynamic UPI QR payment generation and card-entry simulation.

---

## 🛠️ Components

| Component | Responsibility |
| :--- | :--- |
| **`main.py`** | The self-healing entry point and navigation hub. |
| **`employee.py`** | The front-line POS interface and checkout flow. |
| **`admin.py`** | Advanced inventory, employee, and sales management. |
| **`scanner_util.py`** | Computer vision engine for barcode processing. |
| **`theme.py`** | The "CSS" of the app; manages the organic green palette. |

---

## 🚀 Quick Start
1.  **Clone** the repository.
2.  **Install dependencies**: `pip install opencv-python pyzbar pillow requests qrcode`.
3.  **Run**: `python main.py`

---

## 💡 Why Real Mart?
Real Mart isn't just a database; it's a vision for small-to-medium retail. It bridges the gap between traditional retail and digital convenience, providing a premium experience for both store owners and their customers.

---

> [!NOTE]
> For a detailed technical walkthrough and architecture guide, please refer to the [**PROJECT_GUIDE.md**](./PROJECT_GUIDE.md).
