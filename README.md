# 🍎 Real Mart: Fresh Market POS & Retail Management System

<p align="center">
  <img src="images/logo.png" alt="Real Mart Logo" width="220"/>
</p>

<p align="center">
  <b>A high-performance, intelligent retail management system for modern organic stores and supermarkets.</b>
</p>

<p align="center">
  <a href="https://vscode.dev/github/adarshahire16/Real-Mart-Retail-Store-Management-System-"><img src="https://img.shields.io/badge/Open%20in-vscode.dev-007ACC?style=for-the-badge&logo=visualstudiocode" alt="Open in vscode.dev"/></a>
  <img src="https://img.shields.io/badge/Python-3.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+"/>
  <img src="https://img.shields.io/badge/Database-SQLite%20%7C%20MySQL-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="Database"/>
  <img src="https://img.shields.io/badge/Theme-Fresh%20Organic%20Green-2E7D32?style=for-the-badge" alt="Theme"/>
</p>

---

## 🌟 Overview

**Real Mart** is an industrial-grade Point of Sale (POS) and inventory management platform that combines clean, organic aesthetics with real-time computer vision. It transforms any computer or laptop into a full retail station with instant barcode scanning, cloud-hosted digital receipts, dynamic UPI QR payments, and role-based staff authentication.

---

## 📸 Interface Preview

<p align="center">
  <img src="images/inventory_banner_user.png" alt="Inventory Management" width="48%"/>
  <img src="images/sales_analytics_banner_user.png" alt="Sales Analytics" width="48%"/>
</p>
<p align="center">
  <img src="images/employee_banner_user_v2.png" alt="Employee Management" width="48%"/>
  <img src="images/invoice_banner_user.png" alt="Billing & Checkout" width="48%"/>
</p>

---

## ✨ Key Features

- 🌿 **Fresh Organic Green UI**: Modern glassmorphic interface with responsive high-DPI scaling for crisp text on FHD and 4K displays.
- 🔍 **Vision-Powered Barcode Scanning**: Integrated barcode detection using **OpenCV** and **PyZbar** via laptop webcam, external USB scanner, or DroidCam smartphone camera.
- ☁️ **Paperless Cloud Receipts**: Instant PDF bill generation uploaded securely to the cloud; customers can scan a dynamic QR code directly from the screen to download their receipt.
- 💳 **Smart Checkout & Payments**: Dynamic UPI QR payment code generation, cash-tender calculation with change assist, and discount/coupon code application.
- 📊 **Executive Analytics**: Interactive sales trends, revenue monitoring, top-selling items, and payment breakdown.
- 🛡️ **Self-Healing Core & Dual DB**: 
  - Automatically heals environment and Tkinter dependencies.
  - Zero-config auto-seeding with sample grocery catalog on first run.
  - Supports both local **SQLite** (single station) and multi-terminal networked **MySQL** (store server + counter stations).

---

## 💻 Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Language** | Python 3.12+ |
| **GUI Framework** | Tkinter with Custom Glassmorphism Engine (`theme.py`) |
| **Computer Vision** | OpenCV (`cv2`) & PyZbar |
| **Databases** | SQLite (embedded) & MySQL (`pymysql`) |
| **Digital Receipts** | PDF / HTML Generation + QR Code (`qrcode`, `PIL`) |
| **Cloud Service** | Catbox API for paperless receipts |
| **Packaging** | PyInstaller + Inno Setup |

---

## 🛠️ Project Structure

| File | Purpose |
| :--- | :--- |
| **`main.py`** | Application bootstrapper, self-repair environment check, and navigation portal |
| **`employee.py`** | Frontline POS station, item cart, barcode listener, and customer checkout |
| **`admin.py`** | Store administrator hub: inventory, staff, coupons, analytics, and backup controls |
| **`scanner_util.py`** | Computer vision engine capturing video feeds and decoding 1D/2D barcodes |
| **`theme.py`** | Design system containing organic color palettes, glassmorphism, and font caching |
| **`db_manager.py`** | Database abstraction layer routing queries seamlessly between SQLite and MySQL |
| **`db_init.py`** | Schema migration, password encryption, and fresh produce catalog seed engine |
| **`PROJECT_GUIDE.md`** | Comprehensive architectural walkthrough and demonstration guide |

---

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/adarshahire16/Real-Mart-Retail-Store-Management-System-.git
cd Real-Mart-Retail-Store-Management-System-
```

### 2. Install Dependencies
```bash
pip install opencv-python pyzbar pillow requests qrcode
```

> *Note for Windows*: `pyzbar` uses `libzbar-64.dll` which is included with this project or bundled automatically.

### 3. Launch the Application
```bash
python main.py
```

---

## 🔑 Default Credentials

When launching for the first time, the self-healing engine populates the database with default credentials:

| Role | Username | Password |
| :--- | :--- | :--- |
| **Master Admin** | `admin` | `admin` |

---

## 📖 In-Depth Guide

For step-by-step code walkthroughs, architecture diagrams, and presentation tips, refer to [**PROJECT_GUIDE.md**](./PROJECT_GUIDE.md).
