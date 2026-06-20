# Lucky Card 🃏

> Create beautiful AI-powered greeting cards. Send luck across the world.

**Lucky Card** is a full-stack web application featuring a nostalgic **Windows XP desktop UI**, where users can create, browse, and share AI-generated greeting cards.

## ✨ Features

- 🗔 **Windows XP Desktop Interface** — Full XP-style desktop, start menu, taskbar, windows
- 🃏 **AI Card Generation** — Create unique greeting cards with AI-generated art and messages
- 🖼️ **Gallery** — Browse and discover cards created by the community
- 📁 **My Cards** — Save and manage your own creations
- 🎵 **Built-in Music Player** — Listen to music while you create
- 🔐 **User Authentication** — Secure login and account management
- 🌐 **Multi-language Support** — English & 中文 中文
- 💳 **Payment Integration** — PayPal payment support

## 🖥️ Screenshot

![Lucky Card XP Desktop](https://hicard.world/static/img/logo.svg)

## 🚀 Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python, FastAPI, Uvicorn |
| **Frontend** | HTML, CSS, JavaScript (XP Desktop UI) |
| **Database** | PostgreSQL + SQLAlchemy (async) |
| **Templating** | Jinja2 |
| **Payment** | PayPal SDK |
| **AI APIs** | Configurable LLM/Image providers |
| **Infrastructure** | Nginx, Cloudflare, Ubuntu |

## 🏗️ Project Structure

```
app/
├── main.py              # FastAPI application entry point
├── config.py            # Configuration & environment variables
├── database.py          # Database setup (PostgreSQL + SQLAlchemy)
├── models.py            # Database models
├── api/                 # API route modules
│   ├── cards.py         # Card creation & management
│   ├── music.py         # Music player endpoints
│   ├── auth.py          # Authentication endpoints
│   ├── payment.py       # Payment processing
│   └── paypal.py        # PayPal integration
├── static/              # Static files (CSS, JS, images)
│   ├── css/
│   │   ├── xp.css       # Windows XP desktop styles
│   │   └── bios.css     # Boot screen / BIOS styles
│   ├── js/
│   │   ├── xp.js        # XP Shell desktop logic
│   │   └── bios.js      # Boot animation & audio
│   └── forms/           # HTML form pages (loaded in XP windows)
└── templates/
    └── home.html        # Main page template (XP Desktop)
```

## 🛠️ Local Development

```bash
# 1. Clone the repo
git clone https://github.com/ai-zhixiang/luckycard_overseas.git
cd luckycard_overseas

# 2. Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your database credentials & API keys

# 4. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 5. Open in browser
open http://localhost:8000
```

## ⚙️ Deployment

The site runs on an Ubuntu server with Nginx reverse proxy and Cloudflare CDN.

```bash
# Start with systemd (production)
sudo systemctl start luckycard

# Or manually (development)
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 📄 License

MIT License — feel free to use, modify, and share!

---

Made with ❤️ for spreading luck around the world.
