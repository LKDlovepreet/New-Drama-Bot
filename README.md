# 🤖 Dual-Bot File Sharing & Group Management System

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python)
![Aiogram](https://img.shields.io/badge/Aiogram-3.x-green?style=for-the-badge&logo=telegram)
![SQLAlchemy](https://img.shields.io/badge/Database-SQLAlchemy-orange?style=for-the-badge)
![Status](https://img.shields.io/badge/Status-Active-success?style=for-the-badge)

A powerful, modular Telegram Bot ecosystem designed for efficient file sharing and automated group management. It features a **Secure Web Dashboard** with 2FA (OTP) for real-time monitoring.

---

## 🌟 System Overview

This project consists of two distinct bots working together with a central database and a web dashboard:

### 1️⃣ Bot 1: Content & Link Manager (The Store)
* **File Storage:** Saves Photos, Videos, Documents, and Text.
* **Secure Links:** Generates unique, protected start-links for files.
* **Ad Verification:** Integrated with **GPLinks** (or others) to monetize downloads.
* **Broadcasting:** Send messages to all users with rich media support.

### 2️⃣ Bot 2: Group Manager & Indexer (The Guard)
* **Smart Indexing:** Forwards files to index them automatically (Removes tags like `480p`, `mkv`).
* **Auto-Reply:** Detects movie names in groups and replies with a deep link to Bot 1.
* **Strict Mode:** Deletes off-topic messages or spam automatically.
* **Admin Call:** Tags admins when users type "Admin" or "Help".

### 3️⃣ 🔐 Secure Web Dashboard
* **2-Factor Authentication:** OTP sent to Owner's Telegram before login.
* **Live Stats:** View Total Users, Files, and Active Channels.
* **Admin Management:** Add/Remove admins via UI.
* **Modern UI:** Dark/Light themed responsive design.

---

## 🛠️ Project Structure

The project is modularized for better scalability:

```text
├── bot1_core/          # Logic for Link Bot (User Service, Admin Service)
├── bot2_core/          # Logic for Group Bot (Manager, Indexer)
├── config/             # Configuration & Environment loading
├── dashboard/          # Web Server, HTML/CSS, OTP Service
├── database/           # Database Models & Connection
├── utils/              # Helper scripts (Shortener, States)
└── main.py             # Entry point (Runs both bots + Dashboard)
