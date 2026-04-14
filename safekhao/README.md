# SafeKhao — Food Safety Companion
India's AI-powered packaged food safety app

## Quick Start

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Get your FREE Groq API key
1. Go to **https://console.groq.com**
2. Sign up for free
3. Click **API Keys → Create API Key**
4. Copy the key (starts with `gsk_...`)

### 3. Set your Groq API key
**Windows:**
```cmd
set GROQ_API_KEY=gsk_your_key_here
```
**Mac/Linux:**
```bash
export GROQ_API_KEY=gsk_your_key_here
```

### 4. Run the server
```bash
python server.py
```

### 5. Open the app
Visit **http://localhost:5000** in your browser.

Works on desktop Chrome, Firefox, Edge, Safari.
On mobile: open the same URL on your phone while on the same WiFi.

---

## AI Model
Uses **Llama 3.3 70B** via Groq — completely free tier, very fast (usually under 3 seconds).

## Features

| Feature | Description |
|---|---|
| 📷 Camera Scanner | Real barcode scanning using device camera |
| 🔍 Instant Lookup | 50+ pre-loaded Indian packaged food products |
| 🤖 AI Analysis | Groq/Llama 3.3 analyses unknown products from ingredient text |
| 💾 Local SQLite DB | All data stored on your device — works offline after first load |
| 📊 Health Tracker | Weekly health grade + future risk prediction |
| ⚖️ Compare | Side-by-side safety comparison of any two products |
| 🗄️ Database Tab | Add, edit, delete products + export as JSON |

## AI Analysis
When you scan a product not in the database:
1. Go to **AI Analyse** tab
2. Enter the barcode + paste ingredient list from the package
3. Click **Analyse with AI** — Groq reads every ingredient and scores it
4. Result is automatically saved to your local SQLite database

## API Endpoints
```
GET  /api/products           - all products
GET  /api/products/<barcode> - single product
POST /api/products           - add/update product
DEL  /api/products/<barcode> - delete product
POST /api/ai/analyse         - AI analysis of unknown product
GET  /api/stats              - database statistics
GET  /api/scans              - scan history
POST /api/scans              - log a scan
DEL  /api/scans              - clear scan history
```
