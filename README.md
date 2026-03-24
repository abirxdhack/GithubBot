<div align="center">

<img src="https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png" width="120" height="120"/>

# GithubBot — Telegram GitHub Automation Bot

**A powerful GitHub integration bot for Telegram with real-time webhooks, secure token vault, and automation system.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://python.org)
[![Telethon](https://img.shields.io/badge/Telethon-Latest-blue)](https://github.com/LonamiWebs/Telethon)
[![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![MongoDB](https://img.shields.io/badge/MongoDB-Database-green?logo=mongodb)](https://mongodb.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Channel](https://img.shields.io/badge/Updates-@abirxdhackz-blue?logo=telegram)](https://t.me/abirxdhackz)

</div>

---

## 🚀 Features

- 🔗 Connect multiple GitHub accounts securely
- 🔐 AES-encrypted **token vault system**
- ⚡ Real-time GitHub webhook integration
- 📦 Repository linking and management
- 📡 Live notifications for:
  - Push events
  - Pull requests
  - Issues
  - Releases
- 🧩 Modular plugin-based architecture
- ⚙️ FastAPI-powered webhook server
- 🧠 MongoDB async database (Motor)
- 🎛 Clean inline button UI system
- 🔄 Dynamic module auto-loader
- 🛡 Secure storage for sensitive credentials

---

## 🧠 Core Concept

GithubBot transforms Telegram into a **GitHub control center**:

- Manage repositories
- Receive live updates
- Automate workflows
- Securely store credentials

👉 Built for developers, teams, and automation enthusiasts.

---

## 📦 Requirements

- Python **3.10+**
- MongoDB database
- Telegram API credentials from https://my.telegram.org
- GitHub Personal Access Token

Install dependencies:

```bash
pip install telethon fastapi uvicorn motor cryptography python-dotenv


---

⚙️ Configuration

Create a .env file:

API_ID=123456
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token

MONGO_URI=mongodb://localhost:27017
DB_NAME=GithubBot

OWNER_ID=123456789

GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_client_secret

WEBHOOK_SECRET=your_webhook_secret
BASE_WEBHOOK_URL=https://yourdomain.com

⚠️ Important: Never expose secrets in public repositories.


---

▶️ Running

Start the bot:

python3 main.py

Start webhook server:

uvicorn server:app --host 0.0.0.0 --port 8000


---

📜 Commands

Command	Description

/start	Start the bot
/help	Show help menu
/login	Connect GitHub account
/logout	Remove GitHub account
/repos	List linked repositories
/link	Link a repository
/unlink	Unlink repository
/vault	Manage secure tokens
/events	Toggle webhook events



---

🧩 Project Structure

GithubBot/
├── main.py                 # Entry point & module loader
├── config.py              # Config (use .env in production)
├── bot.py                 # Telegram client setup
├── server.py              # FastAPI webhook server
├── database/
│   ├── mongo.py           # MongoDB connection
│   └── models.py          # Collections schema
├── crypto/
│   └── vault.py           # AES encryption system
├── core/
│   ├── start.py           # Start & help handlers
│   └── loader.py          # Dynamic module loader
├── modules/
│   ├── auth.py            # GitHub authentication
│   ├── repos.py           # Repo management
│   ├── events.py          # Webhook handling
│   └── callbacks.py       # Button interactions
├── helpers/
│   ├── buttons.py         # Inline keyboard builder
│   ├── utils.py           # Utility functions
│   ├── logger.py          # Logging system
│   └── notifier.py        # Error notifications
└── webhooks/
    └── github.py          # GitHub event parser


---

🔥 Advanced Highlights

🔐 Secure Vault System

AES-GCM encryption

Tokens never stored in plain text


⚡ Webhook Engine

Real-time GitHub event handling

Extendable automation system


🧩 Plugin Loader

Auto-load modules dynamically

Easily scalable to 100+ features



---

🛠 Future Improvements

🤖 AI-powered commit summaries

📊 Web dashboard panel

💰 Premium & monetization system

🔄 Auto deployment workflows

📈 Usage analytics & logs



---

👑 Credits

Telethon — Telegram client library

FastAPI — Web framework

MongoDB — Database

GitHub API — Core integration



---

👨‍💻 Author

Abir Arafat (AbirXD Hackz)
Telegram: https://t.me/ISmartCoder
Channel: https://t.me/abirxdhackz


---

<div align="center">Made with ❤️ by AbirXD Hackz

</div>
