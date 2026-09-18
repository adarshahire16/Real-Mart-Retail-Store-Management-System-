# 🛒 Real Mart: Project Guide & Walkthrough

Welcome to the **Real Mart Point of Sale (POS)** system. This document serves as a step-by-step guide to help you understand the architecture, logic, and features of this project so you can easily explain it to others.

---

## 🏛️ Project Architecture
The application is built using a **Modular Python + Tkinter** architecture with a local **SQLite** database and advanced computer vision for scanning.

- **Frontend**: Custom Tkinter UI with a modern "Organic Fresh Market" theme.
- **Vision Engine**: Barcode detection using OpenCV and PyZbar for rapid checkout.
- **Backend Logic**: Python-driven state management and dynamic PDF generation.
- **Database**: SQLite for persistent storage of inventory, employees, and bills.
- **Cloud Integration**: Catbox API for hosting digital receipts accessible via QR codes.

---

## 🚀 Step 1: The Launchpad (`main.py`)
Everything starts here. `main.py` is the entry point of the application.

### Key Logic:
1.  **Self-Repair (Tkinter Relay)**: On Windows, modern Python versions (like 3.14) may have broken GUI libraries. `main.py` detects this and automatically relaunches itself using a stable Python version (3.12/3.13) if found.
2.  **Navigation Hub**: It presents the primary choice: **Staff POS** or **Admin Hub**, using a glassmorphic menu system.
3.  **High-DPI Scaling**: Automatically detects Windows display scale factors to ensure the UI looks crisp on 4K and Retina displays.

---

## 🔐 Step 2: Authentication & Roles
The project uses an `employee` table to manage access. Depending on the **designation** field:
- **Admin**: Grants access to the full control center (Inventory, Reports, Sales).
- **Staff**: Grants access only to the Billing and Checkout interface.

> [!TIP]
> **First-Time Setup**: If the database is empty, the system automatically creates a "Master Admin" account (`admin` / `admin`) to get you started.

---

## 🏢 Step 3: Admin Hub (`admin.py`)
The "Brain" of the operation. Admins can manage the entire store:
- **Inventory Management**: Add products with custom **Barcodes**, Categories, and Stock levels.
- **Bulk Import**: Supports CSV imports for updating thousands of items at once.
- **Sales Analytics**: Visual representation of sales trends and payment methods.
- **Employee Management**: Manage staff credentials and access levels.

---

## 🛒 Step 4: Staff POS & Camera Scanner (`employee.py` & `scanner_util.py`)
This is where the retail magic happens.

### The Barcode Workflow:
1.  **Scanner Initialization**: Connects to the device camera (including **DroidCam** support for phone-as-scanner).
2.  **Real-Time Detection**: Uses grayscale processing to identify barcodes instantly.
3.  **Cart Logic**: Scanned items populate a dynamic cart that calculates Totals, Tax (GST), and Savings.
4.  **Checkout**:
    - **Cash**: Calculates change to return.
    - **UPI/QR**: Generates a dynamic scan-and-pay QR code for the customer.

---

## 🎨 Step 5: Design & Theme (`theme.py`)
This file is the "CSS" of the project. It defines:
- **Organic Green Palette**: A curated set of forest greens (#2E7D32) and soft whites for a premium, healthy retail feel.
- **Glassmorphism**: Semi-transparent panels and interactive pill-shaped buttons.
- **Performance Caching**: Aggressively caches images in memory to prevent "flickering" or lag during navigation.

---

## 📂 Step 6: Data Integrity (`db_init.py`)
This project is **self-healing**. When the app starts:
1.  It ensures the `Database/store.db` schema is up-to-date with the latest columns (Barcode, Expiry, etc.).
2.  **Seeding**: If the inventory is empty, it populates a "Fresh Produce" demo catalog (Apples, Mangoes, Milk) so you can demo the POS immediately.

---

## 💡 Summary for Presentation
"Real Mart is a modern retail solution that bridges the gap between traditional shops and digital-first outlets. By combining local SQLite reliability with cloud-based digital receipts and AI-powered camera scanning, it offers a premium experience for both staff and customers."
