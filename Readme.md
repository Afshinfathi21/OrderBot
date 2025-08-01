# 🖨️ Telegram Printing Platform

A complete solution for managing print and copy orders through Telegram.  
Customers can easily submit files for printing, choose a nearby shop, and have their orders processed automatically by the shop’s desktop app.

---

## 📌 Features

✅ **Telegram Bot** — Customers upload files and place orders directly in Telegram.  
✅ **Central API Server** — Flask server handles shops, orders, and authentication.  
✅ **Shop Desktop App** — PyQt app for shop owners to:
  - Authenticate with an API key
  - Retrieve pending orders
  - Download files directly from Telegram
  - Mark orders as printed


---


---

## 🚀 How It Works

1. **Customers** send files to the Telegram bot and choose a print shop.
2. **Orders** are stored in the central database with file info (`file_id`).
3. **Shop owner’s app** connects to the Flask API, authenticates with their API key, and fetches their pending orders.
4. The app uses the **Telegram Bot API** to download the file
5. Shop marks the order as `completed` in the API so it doesn’t reprint.

(assets/app.png)


---

## 🔑 Authentication

- Shops are identified by a unique **API key**.
- The API key must be included as a `Bearer` token in request headers

---

## ⚙️ Deployment

- **Bot + Flask API**: Runs on same server [PythonAnywhere](https://www.pythonanywhere.com/).
- **Database**: SQLite (shared by the bot and API server).
- **Desktop app**: PyQt5 — runs on shop owner’s Windows PC and communicates with the Flask API.

---

## 🛠️ Tech Stack

- **Python 3**
- **Flask** — for the REST API
- **PyQt5** — for the desktop app GUI
- **Telegram Bot API** — to handle file uploads and downloads
- **SQLite** — lightweight database for shops and orders

---


## 🤝 Contributing

Contributions, ideas, or pull requests are welcome!  
Feel free to open an issue to suggest improvements.


