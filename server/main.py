from flask import Flask, jsonify, request
from auth import get_shop_by_token
from models import get_db


app = Flask(__name__)

@app.route("/shop/me", methods=["GET"])
def shop_me():

    shop = get_shop_by_token()
    return jsonify({
        "id": shop["id"],
        "shop_name": shop["shop_name"],
        "owner_username": shop["owner_username"]
    })

@app.route("/orders", methods=["GET"])
def get_orders():

    shop = get_shop_by_token()
    db = get_db()

    orders_cursor = db.execute(
        "SELECT * FROM orders WHERE shop_id = ? AND order_status = 'pending' ORDER BY id ASC",
        (shop["id"],)
    )
    orders = [dict(row) for row in orders_cursor.fetchall()]

    return jsonify(orders)

@app.route("/orders/<int:order_id>/printed", methods=["POST"])
def mark_order_as_printed(order_id):

    shop = get_shop_by_token()
    db = get_db()

    order = db.execute(
        "SELECT id FROM orders WHERE id = ? AND shop_id = ?",
        (order_id, shop["id"])
    ).fetchone()

    if order is None:
        return jsonify({"error": "سفارش یافت نشد یا متعلق به شما نیست."}), 404

    db.execute("UPDATE orders SET order_status = 'completed' WHERE id = ?", (order_id,))
    db.commit()

    return jsonify({"status": "success", "message": f"سفارش شماره {order_id} به عنوان تکمیل شده علامت‌گذاری شد."})

@app.errorhandler(401)
def unauthorized(error):
    return jsonify({"error": "Unauthorized", "message": error.description}), 401

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found", "message": "منبع درخواستی یافت نشد."}), 404
