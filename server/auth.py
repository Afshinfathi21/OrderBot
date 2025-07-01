from flask import request, abort
from models import get_db

def get_shop_by_token():
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        abort(401, description="توکن API نامعتبر است یا وجود ندارد.")

    token = auth_header.replace("Bearer ", "").strip()
    if not token:
        abort(401, description="توکن API خالی است.")

    db = get_db()

    shop = db.execute("SELECT * FROM shops WHERE api_key = ?", (token,)).fetchone()
    if shop is None:
        abort(401, description="کلید API نامعتبر است.")

    return shop