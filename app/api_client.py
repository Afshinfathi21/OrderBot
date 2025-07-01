import requests
import os
from dotenv import load_dotenv
load_dotenv()


class APIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = os.getenv("server_url")
        self.BOT_TOKEN = os.getenv("BOT_TOKEN")
    def validate(self):
        try:
            res = requests.get(f"{self.base_url}/shop/me", headers=self.auth())
            return res.status_code == 200
        except:
            return False

    def auth(self):
        return {"Authorization": f"Bearer {self.api_key}"}

    def get_new_orders(self):
        try:
            res = requests.get(f"{self.base_url}/orders", headers=self.auth())
            return res.json()
        except:
            return []


    def download_telegram_file(self, file_id: str, order_id: int):
        get_file_path_url = f"https://api.telegram.org/bot{self.BOT_TOKEN}/getFile?file_id={file_id}"
        try:
            response = requests.get(get_file_path_url, timeout=10)
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"): raise Exception(data.get('description'))
            file_path_on_telegram = data["result"]["file_path"]
        except Exception as e:
            self.show_error("خطای دانلود", f"نتوانستیم اطلاعات فایل سفارش #{order_id} را از تلگرام دریافت کنیم.\nجزئیات: {e}")
            return None
        file_download_url = f"https://api.telegram.org/file/bot{self.BOT_TOKEN}/{file_path_on_telegram}"
        downloads_dir = "downloads"
        os.makedirs(downloads_dir, exist_ok=True)
        local_filename = os.path.join(downloads_dir, f"order_{order_id}_{os.path.basename(file_path_on_telegram)}")
        try:
            with requests.get(file_download_url, stream=True, timeout=30) as r:
                r.raise_for_status()
                with open(local_filename, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
            return local_filename
        except Exception as e:
            self.show_error("خطای دانلود", f"مشکلی در دانلود فایل سفارش #{order_id} پیش آمد.\nجزئیات: {e}")
            return None