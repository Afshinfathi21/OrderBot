import logging
import re
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
import secrets
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

DB_FILE = "database.db"

def db_connect():
    """Create a database connection and return the connection and cursor."""
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn, conn.cursor()

def setup_database():
    """Create or update database tables if they don't exist."""
    conn, c = db_connect()
    c.execute('''
        CREATE TABLE IF NOT EXISTS shops (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT NOT NULL,
            owner_telegram_id INTEGER NOT NULL UNIQUE,
            owner_username TEXT,
            registration_date TEXT NOT NULL,
            is_active INTEGER DEFAULT 1, -- 1 for active, 0 for inactive
            api_key TEXT UNIQUE NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_telegram_id INTEGER NOT NULL,
            shop_id INTEGER NOT NULL,
            file_id TEXT NOT NULL,
            file_name TEXT,
            customer_name TEXT,
            customer_phone TEXT,
            copies INTEGER,
            page_num INTEGER,
            paper_size TEXT,
            sides TEXT,
            color TEXT,
            layout TEXT,
            special_instructions TEXT,
            final_price REAL,
            order_status TEXT DEFAULT 'pending', -- Can be: pending, in_progress, completed, cancelled
            order_date TEXT NOT NULL,
            FOREIGN KEY (shop_id) REFERENCES shops (id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS shop_prices (
            shop_id INTEGER PRIMARY KEY,
            bw_less_10_s REAL, bw_less_10_d REAL,
            bw_10_100_s REAL, bw_10_100_d REAL,
            bw_100_500_s REAL, bw_100_500_d REAL,
            bw_more_500_s REAL, bw_more_500_d REAL,
            color_s REAL, color_d REAL,
            price_sim REAL,
            paper_a5_factor REAL,
            FOREIGN KEY (shop_id) REFERENCES shops (id)
        )
    ''')
  
    try:
        c.execute("SELECT is_active FROM shops LIMIT 1")
    except sqlite3.OperationalError:
        logger.info("Adding 'is_active' column to shops table...")
        c.execute("ALTER TABLE shops ADD COLUMN is_active INTEGER DEFAULT 1")

    conn.commit()
    conn.close()
    logger.info("پایگاه داده با موفقیت آماده‌سازی شد.")

DEFAULT_PRICES = {
    'bw_less_10_s': 3000, 'bw_less_10_d': 4000,
    'bw_10_100_s': 2000, 'bw_10_100_d': 2500,
    'bw_100_500_s': 1800, 'bw_100_500_d': 2000,
    'bw_more_500_s': 1500, 'bw_more_500_d': 1800,
    'color_s': 8000, 'color_d': 12000,
    'price_sim': 15000, 'paper_a5_factor': 0.5
}

def add_shop_to_db(shop_name, owner_id, owner_username, api_key):
    conn, c = db_connect()
    try:
        c.execute(
            "INSERT INTO shops (shop_name, owner_telegram_id, owner_username, api_key, registration_date) VALUES (?, ?, ?, ?, ?)",
            (shop_name, owner_id, owner_username, api_key, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        shop_id = c.lastrowid
        conn.commit()
        return shop_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def save_shop_prices(shop_id, prices):
    conn, c = db_connect()
    c.execute('''
        INSERT OR REPLACE INTO shop_prices (
            shop_id, bw_less_10_s, bw_less_10_d, bw_10_100_s, bw_10_100_d,
            bw_100_500_s, bw_100_500_d, bw_more_500_s, bw_more_500_d,
            color_s, color_d, price_sim, paper_a5_factor
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        shop_id,
        prices['bw_less_10_s'], prices['bw_less_10_d'],
        prices['bw_10_100_s'], prices['bw_10_100_d'],
        prices['bw_100_500_s'], prices['bw_100_500_d'],
        prices['bw_more_500_s'], prices['bw_more_500_d'],
        prices['color_s'], prices['color_d'],
        prices['price_sim'], prices['paper_a5_factor']
    ))
    conn.commit()
    conn.close()

def get_shop_prices(shop_id):
    conn, c = db_connect()
    c.execute("SELECT * FROM shop_prices WHERE shop_id = ?", (shop_id,))
    prices_row = c.fetchone()
    conn.close()
    return dict(prices_row) if prices_row else DEFAULT_PRICES

def get_all_shops():
    conn, c = db_connect()
    c.execute("SELECT id, shop_name FROM shops WHERE is_active = 1 ORDER BY shop_name")
    shops = c.fetchall()
    conn.close()
    return shops

def get_shop_owner_id(shop_id):
    conn, c = db_connect()
    c.execute("SELECT owner_telegram_id FROM shops WHERE id = ?", (shop_id,))
    result = c.fetchone()
    conn.close()
    return result['owner_telegram_id'] if result else None

def get_order_details(order_id):
    """Fetches full details for a single order."""
    conn, c = db_connect()
    c.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = c.fetchone()
    conn.close()
    return dict(order) if order else None


def save_order_to_db(ud, customer_telegram_id):
    conn, c = db_connect()
    c.execute('''
        INSERT INTO orders (
            customer_telegram_id, shop_id, file_id, file_name, customer_name, customer_phone,
            copies, page_num, paper_size, sides, color, layout, special_instructions,
            final_price, order_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        customer_telegram_id, ud.get('selected_shop_id'), ud.get('file_id'),
        ud.get('file_name'), ud.get('customer_name'), ud.get('customer_phone'),
        ud.get('copies'), ud.get('page_num'), ud.get('paper_size'), ud.get('sides'),
        ud.get('color'), ud.get('layout'), ud.get('special_instructions'),
        ud.get('final_price'), datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    order_id = c.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_orders_by_customer_id(customer_id):
    conn, c = db_connect()
    c.execute('''
        SELECT o.id, o.order_date, o.final_price, o.order_status, s.shop_name
        FROM orders o
        JOIN shops s ON o.shop_id = s.id
        WHERE o.customer_telegram_id = ?
        ORDER BY o.id DESC
    ''', (customer_id,))
    orders = c.fetchall()
    conn.close()
    return orders

def get_shop_id_by_owner(owner_id):
    conn, c = db_connect()
    c.execute("SELECT id FROM shops WHERE owner_telegram_id = ?", (owner_id,))
    result = c.fetchone()
    conn.close()
    return result['id'] if result else None

def get_orders_by_shop_id(shop_id, status_filter='pending'):
    conn, c = db_connect()
    c.execute(
        "SELECT id, order_date, customer_name, final_price FROM orders WHERE shop_id = ? AND order_status = ? ORDER BY id ASC",
        (shop_id, status_filter)
    )
    orders = c.fetchall()
    conn.close()
    return orders

def update_order_status_in_db(order_id, new_status):
    conn, c = db_connect()
    c.execute("UPDATE orders SET order_status = ? WHERE id = ?", (new_status, order_id))
    conn.commit()
    c.execute("SELECT customer_telegram_id FROM orders WHERE id = ?", (order_id,))
    result = c.fetchone()
    conn.close()
    return result['customer_telegram_id'] if result else None

def toggle_shop_status_in_db(shop_id):
    conn, c = db_connect()
    c.execute("SELECT is_active FROM shops WHERE id = ?", (shop_id,))
    current_status = c.fetchone()['is_active']
    new_status = 0 if current_status == 1 else 1
    c.execute("UPDATE shops SET is_active = ? WHERE id = ?", (new_status, shop_id))
    conn.commit()
    conn.close()
    return new_status


(
    STATE_WAITING_FILE, STATE_WAITING_NAME, STATE_WAITING_PHONE,
    STATE_WAITING_SHOP_SELECTION, STATE_WAITING_COPIES, STATE_WAITING_PAGE_NUM,
    STATE_WAITING_PAPER_SIZE, STATE_WAITING_SIDES, STATE_WAITING_COLOR,
    STATE_WAITING_LAYOUT, STATE_WAITING_INSTRUCTIONS,
    STATE_WAITING_INSTRUCTIONS_INPUT, STATE_CONFIRMATION,
    STATE_REGISTER_SHOP_NAME, STATE_ASK_CUSTOM_PRICE, STATE_SET_PRICE,

    PANEL_MAIN, PANEL_VIEW_ORDERS, PANEL_ORDER_DETAILS
) = range(19)

import os
BOT_TOKEN = os.getenv('BOT_TOKEN')
# General Messages
MSG_START = (
    "🖨 *به پلتفرم چاپ آنلاین خوش آمدید\\!*\n\n"
    "شما می‌توانید به راحتی سفارش چاپ خود را ثبت کرده و آن را به یکی از فروشگاه‌های عضو ما بسپارید\\.\n\n"
    "🔹 برای *ثبت سفارش*، از دستور /start استفاده کنید\\.\n"
    "🔸 اگر *صاحب فروشگاه* هستید، با /register\\_shop فروشگاه خود را ثبت کنید\\.\n"
    "ℹ️ برای راهنمایی بیشتر، دستور /help را ارسال کنید\\."
)
MSG_ASK_FILE = "✅ بسیار خب\\! برای شروع، لطفاً فایل خود را \\(PDF, Word و\\.\\.\\.\\) ارسال کنید\\."
MSG_FILE_RECEIVED = "📁 فایل شما دریافت شد\\. لطفاً نام و نام خانوادگی خود را وارد کنید:"
MSG_ASK_PHONE = "🙏 متشکرم\\. لطفاً شماره تماس خود را وارد کنید یا با دکمه زیر به اشتراک بگذارید:"
MSG_SELECT_SHOP = "🏢 عالی\\! حالا لطفاً فروشگاهی که می‌خواهید سفارش شما را انجام دهد انتخاب کنید:"
MSG_ASK_COPIES = "🔢 چه تعداد کپی از این فایل نیاز دارید؟"
MSG_ASK_COPIES_OTHER = "لطفاً تعداد کپی مورد نظر را به عدد وارد کنید:"
MSG_ASK_PAGE_NUM = "📄 لطفاً تعداد کل صفحات فایل خود را وارد کنید:"
MSG_ASK_PAPER_SIZE = "📏 اندازه کاغذ مورد نظر را انتخاب کنید:"
MSG_ASK_SIDES = "↔️ چاپ *یک رو* باشد یا *دورو*؟"
MSG_ASK_COLOR = "🎨 نوع چاپ *سیاه‌وسفید* باشد یا *رنگی*؟"
MSG_ASK_LAYOUT = "📐 جهت چاپ صفحات، *عمودی* باشد یا *افقی*؟"
MSG_ASK_SPECIAL_INSTRUCTIONS = "📝 آیا توضیحات خاصی برای سفارش خود دارید؟ \\(مثلاً سیمی یا منگنه کردن\\)"
MSG_ASK_SPECIAL_INSTRUCTIONS_YES = "لطفاً توضیحات کامل خود را بنویسید:"
MSG_CONFIRMATION_PROMPT = "\n\nلطفاً اطلاعات بالا را به دقت بررسی کرده و سفارش خود را تایید یا لغو کنید\\."
MSG_CONFIRM_ORDER = "✅ سفارش شما با موفقیت ثبت و برای فروشگاه ارسال شد\\. متشکریم\\! برای پیگیری از دستور /myorders استفاده کنید\\."
MSG_CANCEL_ORDER = "❌ سفارش شما لغو شد\\. برای شروع مجدد /start را بزنید\\."
MSG_NO_SHOPS = "متاسفانه هنوز هیچ فروشگاه فعالی در سیستم ثبت نشده است\\. لطفاً بعداً تلاش کنید\\."
MSG_INVALID_NUMBER = "خطا: لطفاً یک عدد معتبر وارد کنید\\."
MSG_ERROR_GENERAL = "🚫 خطایی رخ داد\\. لطفاً دوباره تلاش کنید یا با /cancel از ابتدا شروع کنید\\."

# Shop Registration UI
MSG_SHOP_REGISTER_START = "✍️ به بخش ثبت‌نام فروشگاه خوش آمدید\\. لطفاً نام کامل و رسمی فروشگاه خود را وارد کنید:"
MSG_SHOP_REGISTER_SUCCESS = "✅ تبریک\\! فروشگاه شما با موفقیت ثبت شد\\."
MSG_SHOP_REGISTER_FAIL = "شما قبلاً یک فروشگاه با این حساب تلگرام ثبت کرده‌اید\\."
MSG_ASK_PRICE_CHOICE = "💵 حالا نوبت تنظیم قیمت‌هاست\\! آیا می‌خواهید از تعرفه‌های پیش‌فرض سیستم استفاده کنید یا قیمت‌های سفارشی خود را وارد نمایید؟"
MSG_PRICE_SET_DEFAULT = "👍 بسیار خب\\. قیمت‌های پیش‌فرض برای فروشگاه شما تنظیم شد\\. شما بعداً از طریق پنل مدیریت می‌توانید آن‌ها را ویرایش کنید\\."
MSG_PRICE_SET_START = "عالی\\! لطفاً قیمت‌ها را به *تومان* و به *عدد* وارد کنید\\. بیایید مرحله به مرحله پیش برویم\\."
MSG_PRICE_SET_SUCCESS = "🎉 تمام قیمت‌ها با موفقیت برای فروشگاه شما ثبت شد\\!"

# Buttons
BTN_SHARE_PHONE = "📱 اشتراک شماره تلفن"
BTN_CONFIRM = "✅ تایید و ارسال"
BTN_CANCEL = "❌ لغو سفارش"
BTN_NEW_ORDER = "➕ ثبت سفارش جدید"
BTN_SET_CUSTOM_PRICES = "⚙️ تنظیم قیمت سفارشی"
BTN_USE_DEFAULT_PRICES = "استفاده از قیمت پیش‌فرض"
BTN_COPIES_OTHER = "تعداد دیگر"

# Price Setting 
PRICE_SETTING_FLOW = [
    {'key': 'bw_less_10_s', 'prompt': '1️⃣ قیمت چاپ *سیاه‌وسفید یک‌رو* \\(کمتر از ۱۰ صفحه\\):'},
    {'key': 'bw_less_10_d', 'prompt': '2️⃣ قیمت چاپ *سیاه‌وسفید دورو* \\(کمتر از ۱۰ صفحه\\):'},
    {'key': 'bw_10_100_s', 'prompt': '3️⃣ قیمت چاپ *سیاه‌وسفید یک‌رو* \\(۱۰ تا ۱۰۰ صفحه\\):'},
    {'key': 'bw_10_100_d', 'prompt': '4️⃣ قیمت چاپ *سیاه‌وسفید دورو* \\(۱۰ تا ۱۰۰ صفحه\\):'},
    {'key': 'bw_100_500_s', 'prompt': '5️⃣ قیمت چاپ *سیاه‌وسفید یک‌رو* \\(۱۰۰ تا ۵۰۰ صفحه\\):'},
    {'key': 'bw_100_500_d', 'prompt': '6️⃣ قیمت چاپ *سیاه‌وسفید دورو* \\(۱۰۰ تا ۵۰۰ صفحه\\):'},
    {'key': 'bw_more_500_s', 'prompt': '7️⃣ قیمت چاپ *سیاه‌وسفید یک‌رو* \\(بیش از ۵۰۰ صفحه\\):'},
    {'key': 'bw_more_500_d', 'prompt': '8️⃣ قیمت چاپ *سیاه‌وسفید دورو* \\(بیش از ۵۰۰ صفحه\\):'},
    {'key': 'color_s', 'prompt': '9️⃣ قیمت چاپ *رنگی یک‌رو*:'},
    {'key': 'color_d', 'prompt': '🔟 قیمت چاپ *رنگی دورو*:'},
    {'key': 'price_sim', 'prompt': '1️⃣1️⃣ هزینه اضافی برای *سیمی کردن*:'},
    {'key': 'paper_a5_factor', 'prompt': '2️⃣1️⃣ ضریب قیمت برای کاغذ A5 \\(مثلاً 0\\.5 برای نصف قیمت A4\\):'},
]


def _build_order_summary_text(ud: dict, title: str, for_owner: bool = False) -> str:
    customer_name = escape_markdown(ud.get('customer_name', 'ثبت نشده'), version=2)
    customer_phone = escape_markdown(ud.get('customer_phone', 'ثبت نشده'), version=2)
    user_info = escape_markdown(ud.get('user_info', 'N/A'), version=2)
    file_name = escape_markdown(ud.get('file_name', 'N/A'), version=2)
    special_instructions = escape_markdown(ud.get('special_instructions', 'ندارد'), version=2)

    paper_size_display = ud.get('paper_size', 'N/A')
    sides_display = "دورو" if ud.get('sides') == 'Double-sided' else "یک رو"
    color_display = "رنگی" if ud.get('color') == 'ColorFull' else "سیاه‌وسفید"
    layout_display = "افقی" if ud.get('layout') == 'Landscape' else "عمودی"
    final_price = ud.get('final_price', 0)
    price_display = f"{final_price:,.0f} تومان"

    status_map = {
            'pending': 'در انتظار تایید',
            'in_progress': 'در حال انجام',
            'completed': 'تکمیل شده',
            'cancelled': 'لغو شده'
        }
    status_fa = status_map.get(ud.get('order_status', 'pending'), ud.get('order_status', 'pending'))

    summary = f"*{title}*\n\n"
    if 'id' in ud: 
        summary += f"🏷️ *شماره سفارش:* `{ud['id']}`\n"
        summary += f"🚦 *وضعیت فعلی:* *{status_fa}*\n"

    summary += f"👤 *نام مشتری:* {customer_name}\n"
    summary += f"📞 *شماره تماس:* {customer_phone}\n"
    if for_owner:
        summary += f"🆔 *کاربر تلگرام:* {user_info}\n"
    summary += "-----------------------------------\n".replace("-", "\\-")
    summary += f"📄 *نام فایل:* `{file_name}`\n"
    summary += f"📑 *تعداد صفحات فایل:* {ud.get('page_num', 'N/A')}\n"
    summary += f"🔢 *تعداد کپی:* {ud.get('copies', 'N/A')}\n"
    summary += "-----------------------------------\n".replace("-", "\\-")
    summary += f" *جزئیات چاپ:*\n"
    summary += f"  \\- *نوع:* {color_display} / {sides_display}\n"
    summary += f"  \\- *کاغذ:* {paper_size_display} / {layout_display}\n"
    summary += f"📝 *توضیحات خاص:* {special_instructions}\n\n"
    summary += f"💰 *هزینه نهایی:* *{price_display}*\n"
    return summary

# --- Conversation Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text(MSG_START, parse_mode=ParseMode.MARKDOWN_V2)
    await update.message.reply_text(MSG_ASK_FILE, parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_WAITING_FILE

async def request_new_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.message.reply_text(MSG_ASK_FILE, parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_WAITING_FILE

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    doc = update.message.document
    context.user_data['file_id'] = doc.file_id
    context.user_data['file_name'] = doc.file_name or "Unknown File"
    user = update.effective_user
    context.user_data['user_info'] = f"@{user.username}" if user.username else f"{user.first_name}"
    await update.message.reply_text(MSG_FILE_RECEIVED)
    return STATE_WAITING_NAME

async def handle_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['customer_name'] = update.message.text.strip()
    contact_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_SHARE_PHONE, request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )
    await update.message.reply_text(MSG_ASK_PHONE, reply_markup=contact_keyboard)
    return STATE_WAITING_PHONE

async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    phone_number = ""
    if update.message and update.message.contact:
        phone_number = update.message.contact.phone_number
    elif update.message and update.message.text and re.match(r"^\+?[\d\s-]{7,15}$", update.message.text.strip()):
        phone_number = update.message.text.strip()

    if not phone_number:
        await update.message.reply_text("شماره تلفن نامعتبر است\\. لطفاً دوباره تلاش کنید\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return STATE_WAITING_PHONE

    context.user_data['customer_phone'] = phone_number
    await update.message.reply_text("✅ اطلاعات تماس شما ثبت شد\\.", reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN_V2)

    shops = get_all_shops()
    if not shops:
        await update.message.reply_text(MSG_NO_SHOPS, parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(shop['shop_name'], callback_data=f"shop_{shop['id']}")] for shop in shops]
    await update.message.reply_text(MSG_SELECT_SHOP, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_WAITING_SHOP_SELECTION

async def handle_shop_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['selected_shop_id'] = int(query.data.split("_")[1])

    keyboard = [
        [InlineKeyboardButton(str(i), callback_data=f"copies_{i}") for i in [1, 2, 3, 5, 10]],
        [InlineKeyboardButton(BTN_COPIES_OTHER, callback_data="copies_Other")]
    ]
    await query.edit_message_text(MSG_ASK_COPIES, reply_markup=InlineKeyboardMarkup(keyboard))
    return STATE_WAITING_COPIES

async def handle_copies_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    target_message = None
    num_copies = 0

    if query:
        await query.answer()
        target_message = query.message
        if query.data == "copies_Other":
            await target_message.edit_text(MSG_ASK_COPIES_OTHER)
            return STATE_WAITING_COPIES
        num_copies = int(query.data.split("_")[1])
    elif update.message and update.message.text:
        target_message = update.message
        try:
            num_copies = int(update.message.text)
        except (ValueError, TypeError):
            await target_message.reply_text(MSG_INVALID_NUMBER, parse_mode=ParseMode.MARKDOWN_V2)
            return STATE_WAITING_COPIES

    if num_copies > 0:
        context.user_data["copies"] = num_copies
        if query:
            await target_message.edit_text(MSG_ASK_PAGE_NUM)
        else:
            await target_message.reply_text(MSG_ASK_PAGE_NUM)
        return STATE_WAITING_PAGE_NUM
    else:
        await target_message.reply_text(MSG_INVALID_NUMBER, parse_mode=ParseMode.MARKDOWN_V2)
        return STATE_WAITING_COPIES

async def handle_page_num_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        page_num = int(update.message.text)
        if page_num <= 0: raise ValueError
        context.user_data["page_num"] = page_num
        keyboard = [[
            InlineKeyboardButton("A4", callback_data="size_A4"),
            InlineKeyboardButton("A5", callback_data="size_A5")
        ]]
        await update.message.reply_text(MSG_ASK_PAPER_SIZE, reply_markup=InlineKeyboardMarkup(keyboard))
        return STATE_WAITING_PAPER_SIZE
    except (ValueError, TypeError):
        await update.message.reply_text(MSG_INVALID_NUMBER, parse_mode=ParseMode.MARKDOWN_V2)
        return STATE_WAITING_PAGE_NUM

async def handle_paper_size_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["paper_size"] = query.data.split("_", 1)[1]
    keyboard = [[
        InlineKeyboardButton("یک رو", callback_data="sides_Single-sided"),
        InlineKeyboardButton("دورو", callback_data="sides_Double-sided")
    ]]
    await query.edit_message_text(MSG_ASK_SIDES, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_WAITING_SIDES

async def handle_sides_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["sides"] = query.data.split("_", 1)[1]
    keyboard = [[
        InlineKeyboardButton("سیاه‌وسفید", callback_data="color_Black and White"),
        InlineKeyboardButton("رنگی", callback_data="color_ColorFull")
    ]]
    await query.edit_message_text(MSG_ASK_COLOR, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_WAITING_COLOR

async def handle_color_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["color"] = query.data.split("_", 1)[1]
    keyboard = [[
        InlineKeyboardButton("عمودی", callback_data="layout_Portrait"),
        InlineKeyboardButton("افقی", callback_data="layout_Landscape")
    ]]
    await query.edit_message_text(MSG_ASK_LAYOUT, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_WAITING_LAYOUT

async def handle_layout_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["layout"] = query.data.split("_", 1)[1]
    keyboard = [[
        InlineKeyboardButton("بله", callback_data="instr_Yes"),
        InlineKeyboardButton("خیر", callback_data="instr_No")
    ]]
    await query.edit_message_text(MSG_ASK_SPECIAL_INSTRUCTIONS, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_WAITING_INSTRUCTIONS

async def handle_instructions_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "instr_Yes":
        await query.edit_message_text(MSG_ASK_SPECIAL_INSTRUCTIONS_YES)
        return STATE_WAITING_INSTRUCTIONS_INPUT
    else: 
        context.user_data["special_instructions"] = "ندارد"
        return await show_confirmation(update, context, query=query)

async def handle_instructions_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["special_instructions"] = update.message.text.strip()
    return await show_confirmation(update, context, message=update.message)

async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None, message=None) -> int:
    ud = context.user_data
    shop_id = ud.get('selected_shop_id')
    shop_prices = get_shop_prices(shop_id)
    price_numeric = 0

    try:
        num_of_copy = int(ud.get('copies', 0))
        page_num = int(ud.get('page_num', 1))
        side_key = ud.get('sides', 'Single-sided')
        color_key = ud.get('color', 'Black and White')
        paper_size_key = ud.get('paper_size', 'A4')
        special_instructions = str(ud.get('special_instructions', ''))

        total_pages = page_num * num_of_copy
        price_per_page = 0
        if color_key == 'ColorFull':
            price_per_page = shop_prices['color_s'] if side_key == 'Single-sided' else shop_prices['color_d']
        else: # Black and White
            if total_pages < 10: price_per_page = shop_prices['bw_less_10_s'] if side_key == 'Single-sided' else shop_prices['bw_less_10_d']
            elif 10 <= total_pages < 100: price_per_page = shop_prices['bw_10_100_s'] if side_key == 'Single-sided' else shop_prices['bw_10_100_d']
            elif 100 <= total_pages < 500: price_per_page = shop_prices['bw_100_500_s'] if side_key == 'Single-sided' else shop_prices['bw_100_500_d']
            else: price_per_page = shop_prices['bw_more_500_s'] if side_key == 'Single-sided' else shop_prices['bw_more_500_d']

        size_factor = shop_prices.get('paper_a5_factor', 0.5) if paper_size_key == 'A5' else 1.0

        physical_pages = total_pages
        if side_key == 'Double-sided':
           physical_pages = ( (page_num + 1) // 2) * num_of_copy

        price_numeric = price_per_page * physical_pages * size_factor

        if 'سیمی' in special_instructions: price_numeric += shop_prices.get('price_sim', 15000)
        ud['final_price'] = price_numeric

    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Error calculating price: {e}. Data: {ud}, Prices: {shop_prices}")
        ud['final_price'] = 0

    summary_text = _build_order_summary_text(ud, "📝 خلاصه سفارش شما")
    keyboard = [[InlineKeyboardButton(BTN_CONFIRM, callback_data="action_confirm"),
                 InlineKeyboardButton(BTN_CANCEL, callback_data="action_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    final_text = summary_text + MSG_CONFIRMATION_PROMPT

    target_message = query.message if query else message

    if query:
        await target_message.edit_text(final_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)
    else: 
        await target_message.reply_text(final_text, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN_V2)

    return STATE_CONFIRMATION

async def process_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    ud = context.user_data

    if query.data == "action_confirm":
        order_id = save_order_to_db(ud, update.effective_user.id)
        shop_owner_id = get_shop_owner_id(ud.get('selected_shop_id'))
        if shop_owner_id:
            try:

                ud['id'] = order_id
                owner_message = _build_order_summary_text(ud, "📦 سفارش جدید", for_owner=True)
                await context.bot.send_message(chat_id=shop_owner_id, text=owner_message, parse_mode=ParseMode.MARKDOWN_V2)
                await context.bot.send_document(chat_id=shop_owner_id, document=ud['file_id'], filename=ud.get('file_name'))
                await query.edit_message_text(MSG_CONFIRM_ORDER, parse_mode=ParseMode.MARKDOWN_V2)
            except Exception as e:
                logger.error(f"Failed to send order to owner {shop_owner_id}: {e}")
                await query.edit_message_text(MSG_ERROR_GENERAL, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await query.edit_message_text("خطا: فروشگاه یافت نشد\\.", parse_mode=ParseMode.MARKDOWN_V2)
    else: 
        await query.edit_message_text(MSG_CANCEL_ORDER, parse_mode=ParseMode.MARKDOWN_V2)

    context.user_data.clear()
    return ConversationHandler.END

async def register_shop_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(MSG_SHOP_REGISTER_START, parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_REGISTER_SHOP_NAME

async def register_shop_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    shop_name = update.message.text.strip()
    user = update.effective_user

    api_key = secrets.token_urlsafe(32)
    shop_id = add_shop_to_db(shop_name, user.id, user.username, api_key)

    if not shop_id:
        await update.message.reply_text(MSG_SHOP_REGISTER_FAIL, parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    context.user_data['new_shop_id'] = shop_id
    context.user_data['new_api_key'] = api_key
    await update.message.reply_text(MSG_SHOP_REGISTER_SUCCESS, parse_mode=ParseMode.MARKDOWN_V2)

    keyboard = [
        [InlineKeyboardButton(BTN_SET_CUSTOM_PRICES, callback_data="price_custom")],
        [InlineKeyboardButton(BTN_USE_DEFAULT_PRICES, callback_data="price_default")]
    ]
    await update.message.reply_text(MSG_ASK_PRICE_CHOICE, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_ASK_CUSTOM_PRICE

async def display_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):

    api_key = context.user_data.get('new_api_key')
    message = (
        "🎉 عالی\\! تمام تنظیمات با موفقیت انجام شد\\.\n\n"
        "این کلید API منحصر به فرد فروشگاه شماست\\. لطفاً آن را در جای امنی ذخیره کرده و در نرم‌افزار دسکتاپ خود وارد کنید:\\\n\\\n"
        f"`{api_key}`\n\n"
        "⚠️ \\*توجه: این کلید فقط یک بار نمایش داده می‌شود\\. آن را با دیگران به اشتراک نگذارید\\.\\*"
    )
    target_message = update.callback_query.message if update.callback_query else update.message
    await target_message.reply_text(message, parse_mode=ParseMode.MARKDOWN_V2)
    context.user_data.clear()
    return ConversationHandler.END

async def handle_price_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    shop_id = context.user_data.get('new_shop_id')

    if query.data == "price_default":
        save_shop_prices(shop_id, DEFAULT_PRICES)
        # await query.edit_message_text("قیمت های پیش فرض ثبت شدند", parse_mode=ParseMode.MARKDOWN_V2)
        return await display_api_key(update, context)
    elif query.data == "price_custom":
        context.user_data['pending_prices'] = {}
        context.user_data['price_step'] = 0
        await query.edit_message_text(MSG_PRICE_SET_START, parse_mode=ParseMode.MARKDOWN_V2)

        return await ask_next_price(query.message, context)

async def ask_next_price(message, context: ContextTypes.DEFAULT_TYPE) -> int:
    price_step = context.user_data.get('price_step', 0)

    if price_step >= len(PRICE_SETTING_FLOW):
        shop_id = context.user_data.get('new_shop_id')
        prices_to_save = context.user_data.get('pending_prices')
        save_shop_prices(shop_id, prices_to_save)

        class MockUpdate:
            def __init__(self, msg):
                self.message = msg
                self.callback_query = None

        await message.reply_text(MSG_PRICE_SET_SUCCESS, parse_mode=ParseMode.MARKDOWN_V2)
        return await display_api_key(MockUpdate(message), context)

    prompt = PRICE_SETTING_FLOW[price_step]['prompt']
    await message.reply_text(prompt, parse_mode=ParseMode.MARKDOWN_V2)
    return STATE_SET_PRICE

async def handle_price_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    price_step = context.user_data.get('price_step', 0)
    try:
        price_value = float(update.message.text.strip())
        if price_value < 0: raise ValueError
    except (ValueError, TypeError):
        await update.message.reply_text(MSG_INVALID_NUMBER, parse_mode=ParseMode.MARKDOWN_V2)

        await update.message.reply_text(PRICE_SETTING_FLOW[price_step]['prompt'], parse_mode=ParseMode.MARKDOWN_V2)
        return STATE_SET_PRICE

    current_price_key = PRICE_SETTING_FLOW[price_step]['key']
    context.user_data['pending_prices'][current_price_key] = price_value
    context.user_data['price_step'] += 1

    return await ask_next_price(update.message, context)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    await update.message.reply_text(MSG_CANCEL_ORDER, reply_markup=ReplyKeyboardRemove(), parse_mode=ParseMode.MARKDOWN_V2)
    context.user_data.clear()
    return ConversationHandler.END

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    help_text = (
        "راهنمای استفاده از ربات چاپ آنلاین:\n\n"
        "🙋‍♂️ *برای مشتریان:*\n"
        "  ▫️ /start \\- شروع فرآیند ثبت سفارش جدید\n"
        "  ▫️ /myorders \\- مشاهده تاریخچه و وضعیت سفارشات\n"
        "  ▫️ /cancel \\- لغو عملیات فعلی در هر مرحله\n\n"
        "🏪 *برای صاحبان فروشگاه:*\n"
        "  ▫️ /register\\_shop \\- ثبت یک فروشگاه جدید در سیستم\n"
        "  ▫️ /panel \\- ورود به پنل مدیریت فروشگاه\n\n"
        "برای هرگونه مشکل یا سوال، با پشتیبانی در تماس باشید\\."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN_V2)

async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    user_id = update.effective_user.id
    orders = get_orders_by_customer_id(user_id)

    if not orders:
        await update.message.reply_text("شما تاکنون هیچ سفارشی ثبت نکرده‌اید\\. برای شروع از /start استفاده کنید\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return

    response_text = "*تاریخچه سفارشات شما:*\n\n"
    for order in orders:
        order_date = datetime.strptime(order['order_date'], '%Y-%m-%d %H:%M:%S').strftime('%Y/%m/%d')
        status_map = {
            'pending': 'در انتظار تایید',
            'in_progress': 'در حال انجام',
            'completed': 'تکمیل شده',
            'cancelled': 'لغو شده'
        }
        status_fa = status_map.get(order['order_status'], order['order_status'])
        price_fa = f"{order['final_price']:,.0f} تومان"

        response_text += (
            f"📦 *سفارش شماره:* `{order['id']}`\n"
            f"  🏪 *فروشگاه:* {escape_markdown(order['shop_name'], version=2)}\n"
            f"  📅 *تاریخ:* {order_date}\n"
            f"  💰 *مبلغ:* {price_fa}\n"
            f"  🚦 *وضعیت:* *{status_fa}*\n"
            f"\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\\-\n"
        )

    await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN_V2)

async def shop_panel_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    owner_id = update.effective_user.id
    shop_id = get_shop_id_by_owner(owner_id)

    if not shop_id:
        await update.message.reply_text("شما صاحب هیچ فروشگاهی نیستید\\. برای ثبت‌نام از /register\\_shop استفاده کنید\\.", parse_mode=ParseMode.MARKDOWN_V2)
        return ConversationHandler.END

    context.user_data['panel_shop_id'] = shop_id

    keyboard = [
        [InlineKeyboardButton("👀 مشاهده سفارشات جدید", callback_data="panel_view_pending")],
        [InlineKeyboardButton("🗂️ مشاهده سایر سفارشات", callback_data="panel_view_other")],
        [InlineKeyboardButton("🚦 فعال/غیرفعال کردن فروشگاه", callback_data="panel_toggle_active")],
        [InlineKeyboardButton("❌ خروج از پنل", callback_data="panel_exit")]
    ]

    if update.callback_query:
        await update.callback_query.edit_message_text(
            "*به پنل مدیریت فروشگاه خوش آمدید*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    else:
        await update.message.reply_text(
            "*به پنل مدیریت فروشگاه خوش آمدید*",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=ParseMode.MARKDOWN_V2
        )
    return PANEL_MAIN

async def panel_main_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    query = update.callback_query
    await query.answer()
    choice = query.data

    if choice == "panel_exit":
        await query.edit_message_text("شما از پنل خارج شدید\\.")
        return ConversationHandler.END

    if choice == "panel_toggle_active":
        shop_id = context.user_data['panel_shop_id']
        new_status = toggle_shop_status_in_db(shop_id)
        status_text = "فعال" if new_status == 1 else "غیرفعال"
        await query.message.reply_text(f"وضعیت فروشگاه شما به *{status_text}* تغییر یافت\\.", parse_mode=ParseMode.MARKDOWN_V2)

        return await shop_panel_start(update, context)

    status_map = {'panel_view_pending': 'pending', 'panel_view_other': 'in_progress'}
    status_filter = status_map.get(choice)
    title_map = {'pending': "سفارشات در انتظار تایید", 'in_progress': "سفارشات در حال انجام"}

    if status_filter:
        shop_id = context.user_data['panel_shop_id']
        orders = get_orders_by_shop_id(shop_id, status_filter)
        if not orders:
            await query.edit_message_text(f"هیچ سفارشی با وضعیت '{title_map[status_filter]}' یافت نشد\\.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="panel_back_main")]]))
        else:
            keyboard = []
            for order in orders:
                btn_text = f"سفارش #{order['id']} - {order['customer_name']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"panel_detail_{order['id']}")])
            keyboard.append([InlineKeyboardButton(" بازگشت به منوی اصلی", callback_data="panel_back_main")])
            await query.edit_message_text(f"*{title_map[status_filter]}:*", reply_markup=InlineKeyboardMarkup(keyboard))
        return PANEL_VIEW_ORDERS

    return PANEL_MAIN

async def panel_view_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    query = update.callback_query
    await query.answer()

    if query.data == "panel_back_main":
        return await shop_panel_start(update, context)

    order_id = int(query.data.split('_')[2])
    order_data = get_order_details(order_id)
    if not order_data:
        await query.edit_message_text("خطا: سفارش یافت نشد\\.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت", callback_data="panel_back_main")]]))
        return PANEL_VIEW_ORDERS

    summary = _build_order_summary_text(order_data, "جزئیات سفارش", for_owner=True)

    keyboard = [
        [
            InlineKeyboardButton("✅ تکمیل شد", callback_data=f"panel_action_completed_{order_id}"),
            InlineKeyboardButton("⏳ در حال انجام", callback_data=f"panel_action_in_progress_{order_id}")
        ],
        [
            InlineKeyboardButton("❌ لغو سفارش", callback_data=f"panel_action_cancelled_{order_id}")
        ],
        [
            InlineKeyboardButton(" بازگشت به لیست سفارشات", callback_data="panel_view_pending")
        ]
    ]

    await query.edit_message_text(summary, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN_V2)
    return PANEL_ORDER_DETAILS


async def panel_order_action_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:

    query = update.callback_query
    await query.answer()

    parts = query.data.split('_')
    action = parts[2]
    order_id = int(parts[3])

    customer_id = update_order_status_in_db(order_id, action)

    status_map = {
        'in_progress': 'در حال انجام',
        'completed': 'تکمیل شده',
        'cancelled': 'لغو شده'
    }
    status_fa = status_map.get(action, action)

    await query.edit_message_text(f"✅ وضعیت سفارش شماره `{order_id}` با موفقیت به *{status_fa}* تغییر کرد\\.", parse_mode=ParseMode.MARKDOWN_V2)


    if customer_id:
        try:
            await context.bot.send_message(
                chat_id=customer_id,
                text=f" Farsi: به‌روزرسانی وضعیت:\nسفارش شماره `{order_id}` شما به وضعیت *{status_fa}* تغییر یافت\\.",
                parse_mode=ParseMode.MARKDOWN_V2
            )
        except Exception as e:
            logger.error(f"Failed to send status update to customer {customer_id} for order {order_id}: {e}")

    return await shop_panel_start(update, context)

def main() -> None:

    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN":
        logger.critical("توکن ربات تلگرام (BOT_TOKEN) تنظیم نشده است!")
        return

    setup_database()
    application = Application.builder().token(BOT_TOKEN).build()

    order_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(request_new_order, pattern="^action_start_new$")
        ],
        states={
            STATE_WAITING_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            STATE_WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name_input)],
            STATE_WAITING_PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), handle_phone_input)],
            STATE_WAITING_SHOP_SELECTION: [CallbackQueryHandler(handle_shop_selection, pattern="^shop_")],
            STATE_WAITING_COPIES: [
                CallbackQueryHandler(handle_copies_input, pattern="^copies_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_copies_input)
            ],
            STATE_WAITING_PAGE_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_page_num_input)],
            STATE_WAITING_PAPER_SIZE: [CallbackQueryHandler(handle_paper_size_input, pattern="^size_")],
            STATE_WAITING_SIDES: [CallbackQueryHandler(handle_sides_input, pattern="^sides_")],
            STATE_WAITING_COLOR: [CallbackQueryHandler(handle_color_input, pattern="^color_")],
            STATE_WAITING_LAYOUT: [CallbackQueryHandler(handle_layout_input, pattern="^layout_")],
            STATE_WAITING_INSTRUCTIONS: [CallbackQueryHandler(handle_instructions_prompt, pattern="^instr_")],
            STATE_WAITING_INSTRUCTIONS_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instructions_text)],
            STATE_CONFIRMATION: [CallbackQueryHandler(process_confirmation, pattern="^action_")],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        per_user=True, per_chat=True,
    )

    register_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("register_shop", register_shop_start)],
        states={
            STATE_REGISTER_SHOP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_shop_name)],
            STATE_ASK_CUSTOM_PRICE: [CallbackQueryHandler(handle_price_choice, pattern="^price_")],
            STATE_SET_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_price_input)]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        per_user=True, per_chat=True,
    )


    shop_panel_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("panel", shop_panel_start)],
        states={
            PANEL_MAIN: [CallbackQueryHandler(panel_main_handler, pattern="^panel_")],
            PANEL_VIEW_ORDERS: [
                CallbackQueryHandler(panel_view_order_details, pattern="^panel_detail_"),
                CallbackQueryHandler(shop_panel_start, pattern="^panel_back_main$")
            ],
            PANEL_ORDER_DETAILS: [
                CallbackQueryHandler(panel_order_action_handler, pattern="^panel_action_"),
                CallbackQueryHandler(panel_main_handler, pattern="^panel_view_pending$") 
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_command)],
        per_user=True, per_chat=True,
    )

    application.add_handler(order_conv_handler)
    application.add_handler(register_conv_handler)
    application.add_handler(shop_panel_conv_handler) 

    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myorders", my_orders))


    logger.info("ربات با تمام قابلیت‌های جدید در حال اجراست...")
    application.run_polling()

if __name__ == "__main__":
    main()