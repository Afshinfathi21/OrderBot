# -*- coding: utf-8 -*-

import logging
import re
from datetime import datetime
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    CallbackContext,
    CallbackQueryHandler,
    ContextTypes,
    filters,
    PicklePersistence,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Constants ---
MSG_START = "سلام! برای ثبت سفارش چاپ یا کپی، فایل خود را ارسال کنید."
MSG_ASK_FILE = "لطفاً فایل داکیومنت (PDF، Word، ...) خود را ارسال کنید."
MSG_FILE_RECEIVED_WAIT = "فایل دریافت شد. لطفاً کمی صبر کنید..."
MSG_FILE_ERROR = "متاسفانه در دریافت فایل خطایی رخ داد. لطفاً دوباره تلاش کنید یا /start را بزنید."
MSG_NOT_DOCUMENT = "لطفاً یک فایل داکیومنت ارسال کنید (مانند PDF، DOCX)."
MSG_ASK_NAME = "بسیار خب. لطفاً نام کامل خود را وارد کنید:"
MSG_ASK_PHONE = "متشکرم. حالا لطفاً شماره تلفن خود را با دکمه زیر به اشتراک بگذارید یا آن را وارد کنید:"
MSG_INVALID_PHONE = "شماره تلفن وارد شده معتبر به نظر نمی رسد. لطفاً دوباره تلاش کنید."
MSG_ASK_COPIES = "چه تعداد کپی نیاز دارید؟"
MSG_ASK_COPIES_OTHER = "لطفاً تعداد کپی مورد نظر خود را به عدد وارد کنید:"
MSG_ASK_PAPER_SIZE = "اندازه کاغذ مورد نظر (A4 یا A5) را وارد کنید؟"
MSG_ASK_PAPER_SIZE_OTHER = "لطفاً اندازه کاغذ دلخواه خود را وارد کنید (مثلاً A5، B5 حروف بزرگ):"
MSG_ASK_SIDES = "چاپ یک رو باشد یا دو رو؟"
MSG_ASK_COLOR = "چاپ سیاه و سفید باشد یا رنگی؟"
MSG_ASK_PAGE_NUM = "لطفا تعداد صفحات فایلی که فرستادید را وارد کنید:"
MSG_ASK_LAYOUT = "عمودی یا افقی؟"
MSG_ASK_SPECIAL_INSTRUCTIONS = "آیا توضیحات خاصی برای چاپ دارید؟ (مثلاً منگنه شود، سیمی شود)"
MSG_ASK_SPECIAL_INSTRUCTIONS_YES = "لطفاً توضیحات خود را وارد کنید:"
MSG_ORDER_SUMMARY_TITLE = "خلاصه سفارش شما:"
MSG_CONFIRM_ORDER = "✅ سفارش شما تایید و برای چاپ ارسال شد. متشکریم!"
MSG_CANCEL_ORDER = "❌ سفارش شما لغو شد."
MSG_CONFIRMATION_PROMPT = "لطفاً سفارش خود را بررسی و تایید یا لغو کنید."
MSG_ERROR_GENERAL = "خطایی رخ داد. لطفاً دوباره تلاش کنید."
MSG_INVALID_NUMBER = "لطفاً یک عدد معتبر وارد کنید."
MSG_ORDER_DETAILS_HEADER = "--- سفارش جدید ---"
MSG_USER = "کاربر تلگرام"
LBL_NAME = "نام مشتری"
LBL_PHONE = "تلفن"
MSG_FILE_NAME = "نام فایل"
MSG_COPIES = "تعداد کپی"
MSG_PAPER_SIZE = "اندازه کاغذ"
MSG_COLOR = "رنگ چاپ"
MSG_SIDES = "نوع چاپ"
MSG_SPECIAL_INSTRUCTIONS = "توضیحات خاص"
MSG_ORDER_TIME = "Order Time"
MSG_NO_SPECIAL_INSTRUCTIONS = "ندارد"
MSG_PAGE_NUM = "تعداد صفحات"
MSG_LAYOUT_TYPE = "جهت چاپ"

BTN_SHARE_PHONE = "اشتراک شماره تلفن"
BTN_COPIES_OTHER = "تعداد دیگر"
BTN_PAPER_SIZE_A4 = "A4"
BTN_PAPER_SIZE_A5 = "A5"
# BTN_PAPER_SIZE_OTHER = "اندازه دیگر"
BTN_SIDES_SINGLE = "یک رو"
BTN_SIDES_DOUBLE = "دو رو"
BTN_LAYOUT_LANDSCAPE = "افقی"
BTN_LAYOUT_PORTRAIT = "عمودی"
BTN_COLOR_BW = "سیاه و سفید"
BTN_COLOR_COLORFUL = "رنگی"
BTN_INSTR_YES = "بله"
BTN_INSTR_NO = "خیر"
BTN_CONFIRM = "✅ تایید سفارش"
BTN_CANCEL = "❌ لغو"
BTN_NEW_ORDER = "سفارش جدید"
TOTAL_PRICE_MSG="قیمت کل"
PRICE_UNIT="تومان"
EXTRA_PRICE='هزینه سیمی کردن'
# Define conversation states
(
    STATE_WAITING_FILE,
    STATE_WAITING_NAME,
    STATE_WAITING_PHONE,
    STATE_WAITING_COPIES,
    STATE_WAITING_PAGE_NUM,
    STATE_WAITING_PAPER_SIZE,
    STATE_WAITING_PAPER_SIZE_INPUT,
    STATE_WAITING_SIDES,
    STATE_WAITING_COLOR,
    STATE_WAITING_LAYOUT,
    STATE_WAITING_INSTRUCTIONS,
    STATE_WAITING_INSTRUCTIONS_INPUT,
    STATE_CONFIRMATION,
) = range(13)

# --- Options ---
PAPER_SIZES = {"A4": BTN_PAPER_SIZE_A4, "A5": BTN_PAPER_SIZE_A5}
COLORS = {"Black and White": BTN_COLOR_BW, "ColorFull": BTN_COLOR_COLORFUL}
SIDES = {"Single-sided": BTN_SIDES_SINGLE, "Double-sided": BTN_SIDES_DOUBLE}
LAYOUT = {"Portrait": BTN_LAYOUT_PORTRAIT, "Landscape": BTN_LAYOUT_LANDSCAPE}
COPIES_OPTIONS_NUM = [1, 2, 3, 5, 10]
INSTRUCTION_OPTIONS = {"Yes": BTN_INSTR_YES, "No": BTN_INSTR_NO}

# --- Pricing Constants ---
# Assuming prices are PER PAGE in Toman

PRICE_BW = {
    'LESS_TEN': {'Single-sided': 3000, 'Double-sided': 4000},
    'TEN_TO_HUN': {'Single-sided': 2000, 'Double-sided': 2500},
    'HUN_TO_FIVE_HUN': {'Single-sided': 1800, 'Double-sided': 2000},
    'MORE_FIVE_HUN': {'Single-sided': 1500, 'Double-sided': 1800}
}

PRICE_COLOR = {'Single-sided': 8000, 'Double-sided': 12000}

PAPER_SIZE_FACTOR = {'A4': 1.0, 'A5': 0.5} 
DEFAULT_SIZE_FACTOR = 1.0


PRICE_MANGANE = 0
PRICE_SIM = 15000


BOT_TOKEN = "YOUR-TELEGRAM-TOKEN"
#Sending orders to this channel
ORDER_CHANNEL_ID = "CHANNEL-ID"
PHONE_REGEX = re.compile(r"^\+?[\d\s-]{7,15}$")

def get_user_info(update: Update) -> str:
    user = update.effective_user
    return f"@{user.username}" if user.username else f"{user.first_name}"

def build_new_order_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_NEW_ORDER, callback_data="action_start_new")]])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logger.info(f"/start command received from {get_user_info(update)}")
    context.user_data.clear()
    await update.message.reply_text(MSG_START)
    await update.message.reply_text(MSG_ASK_FILE)
    return STATE_WAITING_FILE

async def request_new_order(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    logger.info(f"'New Order' button pressed by {get_user_info(update)}")
    context.user_data.clear()
    try:
        await query.message.reply_text(MSG_ASK_FILE)

    except Exception as e:
        logger.warning(f"Could not edit message for new order, sending new one: {e}")
        await query.message.reply_text(MSG_ASK_FILE)

    return STATE_WAITING_FILE


async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_info = get_user_info(update)
    if not update.message or not update.message.document:
        await update.message.reply_text(MSG_NOT_DOCUMENT)
        return STATE_WAITING_FILE

    doc = update.message.document
    context.user_data['file_id'] = doc.file_id
    context.user_data['file_unique_id'] = doc.file_unique_id
    context.user_data['file_name'] = doc.file_name or "Unknown File"
    context.user_data['user_info'] = user_info

    logger.info(f"File '{context.user_data['file_name']}' received from {user_info}")
    await update.message.reply_text(MSG_FILE_RECEIVED_WAIT)

    await update.message.reply_text(MSG_ASK_NAME)
    return STATE_WAITING_NAME

async def handle_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message or not update.message.text:
        await update.message.reply_text(MSG_ASK_NAME)
        return STATE_WAITING_NAME

    user_name = update.message.text.strip()
    if not user_name:
        await update.message.reply_text(MSG_ASK_NAME)
        return STATE_WAITING_NAME

    context.user_data['customer_name'] = user_name
    logger.info(f"Name '{user_name}' received from {get_user_info(update)}")

    contact_keyboard = ReplyKeyboardMarkup(
        [[KeyboardButton(BTN_SHARE_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await update.message.reply_text(MSG_ASK_PHONE, reply_markup=contact_keyboard)
    return STATE_WAITING_PHONE


async def handle_phone_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles phone input (contact object or text), asks for copies."""
    phone_number = None
    user_info = get_user_info(update)



    if update.message and update.message.contact:

        contact = update.message.contact

        if contact.user_id == update.effective_user.id:
            phone_number = contact.phone_number
            logger.info(f"Phone number {phone_number} received via Contact object from {user_info}")
        else:
            logger.warning(f"User {user_info} shared contact of different user {contact.user_id}. Ignoring.")

            await update.message.reply_text(MSG_INVALID_PHONE)
            return STATE_WAITING_PHONE

    elif update.message and update.message.text:

        typed_number = update.message.text.strip()

        if PHONE_REGEX.match(typed_number):
            phone_number = typed_number
            logger.info(f"Phone number {phone_number} received via text from {user_info}")
        else:
            logger.warning(f"Invalid phone format received via text: {typed_number} from {user_info}")

            contact_keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton(BTN_SHARE_PHONE, request_contact=True)]],
                resize_keyboard=True,
                one_time_keyboard=True
            )
            await update.message.reply_text(MSG_INVALID_PHONE,reply_markup=contact_keyboard)
            return STATE_WAITING_PHONE
    else:

        logger.warning(f"Unexpected input type received while waiting for phone from {user_info}")

        contact_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(BTN_SHARE_PHONE, request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(MSG_INVALID_PHONE, reply_markup=contact_keyboard)
        return STATE_WAITING_PHONE


    if phone_number:
        context.user_data['customer_phone'] = phone_number

        keyboard = [
            [InlineKeyboardButton(str(i), callback_data=f"copies_{i}") for i in COPIES_OPTIONS_NUM],
            [InlineKeyboardButton(BTN_COPIES_OTHER, callback_data="copies_Other")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(MSG_ASK_COPIES, reply_markup=reply_markup)
        return STATE_WAITING_COPIES
    else:

        logger.error(f"Could not extract phone number for user {user_info}")
        await update.message.reply_text(MSG_ERROR_GENERAL)

        contact_keyboard = ReplyKeyboardMarkup(
            [[KeyboardButton(BTN_SHARE_PHONE, request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        await update.message.reply_text(MSG_INVALID_PHONE, reply_markup=contact_keyboard)
        return STATE_WAITING_PHONE



async def handle_copies_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    message = update.message
    next_state = STATE_WAITING_COPIES

    if query:
        await query.answer()
        callback_data = query.data
        logger.debug(f"Copies button pressed: {callback_data}")
        if callback_data == "copies_Other":
            await query.edit_message_text(MSG_ASK_COPIES_OTHER)
        elif callback_data.startswith("copies_"):
            try:
                num_copies = int(callback_data.split("_")[1])
                if num_copies > 0:
                    context.user_data["copies"] = num_copies
                    logger.info(f"Copies set to {num_copies} via button by {get_user_info(update)}")
                    await query.edit_message_text(MSG_ASK_PAGE_NUM)
                    next_state = STATE_WAITING_PAGE_NUM
                else: await query.message.reply_text(MSG_INVALID_NUMBER)
            except (ValueError, IndexError):
                logger.warning(f"Invalid copies callback data: {callback_data}")
                await query.message.reply_text(MSG_ERROR_GENERAL)
    elif message and message.text:
        logger.debug(f"Copies text received: {message.text}")
        try:
            num_copies = int(message.text)
            if num_copies <= 0: await message.reply_text(MSG_INVALID_NUMBER + "\n" + MSG_ASK_COPIES_OTHER)
            else:
                context.user_data["copies"] = num_copies
                logger.info(f"Copies set to {num_copies} via text by {get_user_info(update)}")
                await message.reply_text(MSG_ASK_PAGE_NUM)
                next_state = STATE_WAITING_PAGE_NUM
        except ValueError: await message.reply_text(MSG_INVALID_NUMBER + "\n" + MSG_ASK_COPIES_OTHER)
    return next_state


async def handle_page_num_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if not message or not message.text:
        await message.reply_text(MSG_ASK_PAGE_NUM)
        return STATE_WAITING_PAGE_NUM

    try:
        page_num = int(message.text)
        if page_num <= 0:
            await message.reply_text(MSG_INVALID_NUMBER + "\n" + MSG_ASK_PAGE_NUM)
            return STATE_WAITING_PAGE_NUM
        context.user_data["page_num"] = page_num
        logger.info(f"Page number set to {page_num} by {get_user_info(update)}")
        keyboard = [[InlineKeyboardButton(text, callback_data=f"size_{key}") for key, text in PAPER_SIZES.items()]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await message.reply_text(MSG_ASK_PAPER_SIZE, reply_markup=reply_markup)
        return STATE_WAITING_PAPER_SIZE
    except ValueError:
        await message.reply_text(MSG_INVALID_NUMBER + "\n" + MSG_ASK_PAGE_NUM)
        return STATE_WAITING_PAGE_NUM



async def handle_paper_size_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles paper size selection (button)."""
    query = update.callback_query
    if not query: return STATE_WAITING_PAPER_SIZE

    await query.answer()
    callback_data = query.data
    logger.debug(f"Paper size button pressed: {callback_data}")

    if callback_data == "size_Other":
        await query.edit_message_text(MSG_ASK_PAPER_SIZE_OTHER)
        return STATE_WAITING_PAPER_SIZE_INPUT
    elif callback_data.startswith("size_"):
        paper_size_key = callback_data.split("_", 1)[1]
        if paper_size_key in PAPER_SIZES:
            context.user_data["paper_size"] = paper_size_key
            logger.info(f"Paper size set to {paper_size_key} by {get_user_info(update)}")

            keyboard = [[InlineKeyboardButton(text, callback_data=f"sides_{key}") for key, text in SIDES.items()]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(MSG_ASK_SIDES, reply_markup=reply_markup)
            return STATE_WAITING_SIDES
        else:
            logger.warning(f"Invalid paper size key: {paper_size_key}")
            await query.message.reply_text(MSG_ERROR_GENERAL)
            return STATE_WAITING_PAPER_SIZE


async def handle_paper_size_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handles typed input for paper size."""
    message = update.message
    if not message or not message.text: return STATE_WAITING_PAPER_SIZE_INPUT

    paper_size_text = message.text.strip()
    if not paper_size_text:
        await message.reply_text(MSG_ASK_PAPER_SIZE_OTHER)
        return STATE_WAITING_PAPER_SIZE_INPUT

    context.user_data["paper_size"] = paper_size_text
    logger.info(f"Paper size set to '{paper_size_text}' via text by {get_user_info(update)}")

    keyboard = [[InlineKeyboardButton(text, callback_data=f"sides_{key}") for key, text in SIDES.items()]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await message.reply_text(MSG_ASK_SIDES, reply_markup=reply_markup)
    return STATE_WAITING_SIDES


async def handle_sides_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query: return STATE_WAITING_SIDES
    await query.answer()
    callback_data = query.data
    logger.debug(f"Sides button pressed: {callback_data}")
    if callback_data.startswith("sides_"):
        side_key = callback_data.split("_", 1)[1]
        if side_key in SIDES:
            context.user_data["sides"] = side_key
            logger.info(f"Sides set to {side_key} by {get_user_info(update)}")
            keyboard = [[InlineKeyboardButton(text, callback_data=f"color_{key}") for key, text in COLORS.items()]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(MSG_ASK_COLOR, reply_markup=reply_markup)
            return STATE_WAITING_COLOR
        else:
            logger.warning(f"Invalid sides key: {side_key}")
            await query.message.reply_text(MSG_ERROR_GENERAL)
            return STATE_WAITING_SIDES


async def handle_color_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query: return STATE_WAITING_COLOR
    await query.answer()
    callback_data = query.data
    logger.debug(f"Color button pressed: {callback_data}")
    if callback_data.startswith("color_"):
        color_key = callback_data.split("_", 1)[1]
        if color_key in COLORS:
            context.user_data["color"] = color_key
            logger.info(f"Color set to {color_key} by {get_user_info(update)}")
            keyboard = [[InlineKeyboardButton(text, callback_data=f"layout_{key}") for key, text in LAYOUT.items()]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            try:
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo='https://www.papersizes.org/images/portrait-landscape.gif',
                    caption=MSG_ASK_LAYOUT,
                    reply_markup=reply_markup
                )
                await query.edit_message_reply_markup(reply_markup=None)
            except Exception as e:
                logger.warning(f"Could not send layout picture with buttons: {e}")
                await query.edit_message_text(MSG_ASK_LAYOUT, reply_markup=reply_markup)

            return STATE_WAITING_LAYOUT
        else:
            logger.warning(f"Invalid color key: {color_key}")
            await query.message.reply_text(MSG_ERROR_GENERAL)
            return STATE_WAITING_COLOR


async def handle_layout_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query: return STATE_WAITING_LAYOUT
    await query.answer()
    callback_data = query.data
    logger.debug(f"Layout button pressed: {callback_data}")
    if callback_data.startswith("layout_"):
        layout_key = callback_data.split("_", 1)[1]
        if layout_key in LAYOUT:
            context.user_data["layout"] = layout_key
            logger.info(f"Layout set to {layout_key} by {get_user_info(update)}")
            keyboard = [[InlineKeyboardButton(text, callback_data=f"instr_{key}") for key, text in INSTRUCTION_OPTIONS.items()]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text(MSG_ASK_SPECIAL_INSTRUCTIONS, reply_markup=reply_markup)
            return STATE_WAITING_INSTRUCTIONS
        else:
            logger.warning(f"Invalid layout key: {layout_key}")
            await query.message.reply_text(MSG_ERROR_GENERAL)
            return STATE_WAITING_LAYOUT


async def handle_instructions_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query: return STATE_WAITING_INSTRUCTIONS
    await query.answer()
    callback_data = query.data
    logger.debug(f"Instructions prompt button pressed: {callback_data}")
    if callback_data == "instr_Yes":
        await query.edit_message_text(MSG_ASK_SPECIAL_INSTRUCTIONS_YES)
        return STATE_WAITING_INSTRUCTIONS_INPUT
    elif callback_data == "instr_No":
        context.user_data["special_instructions"] = MSG_NO_SPECIAL_INSTRUCTIONS
        logger.info(f"No special instructions selected by {get_user_info(update)}")
        return await show_confirmation(update, context, query=query)
    else:
        logger.warning(f"Invalid instruction prompt callback: {callback_data}")
        await query.message.reply_text(MSG_ERROR_GENERAL)
        return STATE_WAITING_INSTRUCTIONS


async def handle_instructions_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    if not message or not message.text: return STATE_WAITING_INSTRUCTIONS_INPUT
    instructions = message.text.strip()
    context.user_data["special_instructions"] = instructions if instructions else MSG_NO_SPECIAL_INSTRUCTIONS
    logger.info(f"Instructions captured from {get_user_info(update)}: {context.user_data['special_instructions']}")
    return await show_confirmation(update, context, message=message)


async def show_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None, message=None) -> int:
    """Displays the order summary (incl name/phone and price) and confirmation buttons."""
    ud = context.user_data
    user_info = get_user_info(update)
    logger.info(f"Showing confirmation screen for {user_info}")
    price_numeric = 0
    price_display = "محاسبه نشده"

    # --- Calculate Price ---
    try:
        num_of_copy = int(ud.get('copies', 0))
        page_num = int(ud.get('page_num', 1))

        side_key = ud.get('sides', 'Single-sided')
        color_key = ud.get('color', 'Black and White')
        paper_size_key = ud.get('paper_size', 'A4')
        layout_key = ud.get('layout', 'Portrait')
        special_instructions = str(ud.get('special_instructions', ''))

        if num_of_copy <= 0 or page_num <= 0: raise ValueError("Copies or page number is zero or negative")
        if side_key == 'Double-sided': page_num = page_num / 2 + page_num % 2

        page_num=page_num * num_of_copy

        price_per_page = 0
        if color_key == 'ColorFull':
            price_per_page = PRICE_COLOR.get(side_key, PRICE_COLOR['Single-sided'])
        elif color_key == 'Black and White':
            if page_num < 10:
                price_per_page = PRICE_BW['LESS_TEN'].get(side_key, PRICE_BW['LESS_TEN']['Single-sided'])
            elif 10 <= page_num < 100:
                price_per_page = PRICE_BW['TEN_TO_HUN'].get(side_key, PRICE_BW['TEN_TO_HUN']['Single-sided'])
            elif 100 <= page_num < 500:
                price_per_page = PRICE_BW['HUN_TO_FIVE_HUN'].get(side_key, PRICE_BW['HUN_TO_FIVE_HUN']['Single-sided'])
            elif page_num >= 500:
                price_per_page = PRICE_BW['MORE_FIVE_HUN'].get(side_key, PRICE_BW['MORE_FIVE_HUN']['Single-sided'])
        else:
            logger.warning(f"Unknown color key '{color_key}' during price calc.")
            price_per_page = PRICE_BW['MORE_FIVE_HUN']['Single-sided']


        size_factor = PAPER_SIZE_FACTOR.get(paper_size_key, DEFAULT_SIZE_FACTOR)
        price_per_page_adjusted = price_per_page * size_factor


        price_numeric = price_per_page_adjusted * page_num



        extras_price = 0
        sim=False
        if 'منگنه' in special_instructions:
            extras_price += PRICE_MANGANE
        if 'سیمی' in special_instructions:
            sim=True

        price_numeric += extras_price
        if sim:
            price_display = f"{price_numeric:,} {PRICE_UNIT} + {EXTRA_PRICE}"
        else:
            price_display = f"{price_numeric:,} {PRICE_UNIT}"
        logger.info(f"Price calculated: Copies={num_of_copy}, Pages={page_num}, Color={color_key}, Side={side_key}, Size={paper_size_key}, Layout={layout_key}, SizeFactor={size_factor}, Extras={extras_price} -> TOTAL={price_numeric}")
        ud['final_price'] = price_numeric

    except (ValueError, TypeError, KeyError) as e:
        logger.error(f"Error calculating price for {user_info}: {e}. Data: {ud}")
        price_numeric = 0
        price_display = "خطا در محاسبه"
        ud['final_price'] = 0

    try:
        paper_size_display = PAPER_SIZES.get(ud.get('paper_size'), ud.get('paper_size', 'N/A'))
        color_display = COLORS.get(ud.get('color'), 'N/A')
        sides_display = SIDES.get(ud.get('sides'), 'N/A')
        layout_display = LAYOUT.get(ud.get('layout'), 'N/A')

        order_summary = f"{MSG_ORDER_SUMMARY_TITLE}\n\n"
        order_summary += f"👤 {MSG_USER}: {ud.get('user_info', user_info)}\n"
        order_summary += f"👤 {LBL_NAME}: {ud.get('customer_name', 'ثبت نشده')}\n"
        order_summary += f"📞 {LBL_PHONE}: {ud.get('customer_phone', 'ثبت نشده')}\n"
        order_summary += f"📄 {MSG_FILE_NAME}: {ud.get('file_name', 'N/A')}\n"
        order_summary += f"📑 {MSG_PAGE_NUM}: {ud.get('page_num', 'N/A')}\n"
        order_summary += f"🔢 {MSG_COPIES}: {ud.get('copies', 'N/A')}\n"
        order_summary += f"📏 {MSG_PAPER_SIZE}: {paper_size_display}\n"
        order_summary += f"🎨 {MSG_COLOR}: {color_display}\n"
        order_summary += f"↔️ {MSG_SIDES}: {sides_display}\n"
        order_summary += f"📐 {MSG_LAYOUT_TYPE}: {layout_display}\n"
        order_summary += f"📝 {MSG_SPECIAL_INSTRUCTIONS}: {ud.get('special_instructions', 'N/A')}\n"
        order_summary += f"💰 {TOTAL_PRICE_MSG}: {price_display}"

    except KeyError as e:
        logger.error(f"Missing user_data key for confirmation summary by {user_info}: {e}")
        order_summary = MSG_ERROR_GENERAL + "\n" + "برخی اطلاعات سفارش یافت نشد."
        price_display = "خطا"

    keyboard = [[InlineKeyboardButton(BTN_CONFIRM, callback_data="action_confirm"), InlineKeyboardButton(BTN_CANCEL, callback_data="action_cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    prompt_text = order_summary + "\n\n" + MSG_CONFIRMATION_PROMPT

    if query: await query.edit_message_text(prompt_text, reply_markup=reply_markup)
    elif message: await message.reply_text(prompt_text, reply_markup=reply_markup)
    else:
        logger.error("show_confirmation called without query or message context")

        try: await context.bot.send_message(chat_id=update.effective_chat.id, text=prompt_text, reply_markup=reply_markup)
        except Exception as send_err: logger.error(f"Failed to send confirmation: {send_err}")

    return STATE_CONFIRMATION


async def process_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if not query: return ConversationHandler.END
    await query.answer()
    decision = query.data
    ud = context.user_data
    user_info = get_user_info(update)
    customer_name = ud.get('customer_name', 'ثبت نشده')
    customer_phone = ud.get('customer_phone', 'ثبت نشده')

    if decision == "action_confirm":
        logger.info(f"Order CONFIRMED by {user_info} (Name: {customer_name})")
        if not ORDER_CHANNEL_ID:
            logger.error("ORDER_CHANNEL_ID is not set! Cannot send order.")
            await query.edit_message_text(MSG_ERROR_GENERAL + "\nخطا در تنظیمات ربات. امکان ارسال سفارش وجود ندارد.", reply_markup=build_new_order_button())
            context.user_data.clear()
            return ConversationHandler.END
        try:
            paper_size_display = PAPER_SIZES.get(ud.get('paper_size'), ud.get('paper_size', 'N/A'))
            color_display = COLORS.get(ud.get('color'), 'N/A')
            sides_display = SIDES.get(ud.get('sides'), 'N/A')
            layout_display = LAYOUT.get(ud.get('layout'), 'N/A')

            final_price_numeric = ud.get('final_price', 0)
            price_display_channel = f"{final_price_numeric:,}{PRICE_UNIT}" if final_price_numeric > 0 else "محاسبه نشده یا خطا"
            if 'سیمی' in ud.get("special_instructions"):
                price_display_channel = f"{final_price_numeric:,}{PRICE_UNIT} + {EXTRA_PRICE}" if final_price_numeric > 0 else "محاسبه نشده یا خطا"

            order_details_text = f"{MSG_ORDER_DETAILS_HEADER}\n"
            order_details_text += f"👤 {LBL_NAME}: {customer_name}\n"
            order_details_text += f"📞 {LBL_PHONE}: {customer_phone}\n"
            order_details_text += f"👤 {MSG_USER}: {ud.get('user_info', user_info)} ({update.effective_user.id})\n"
            order_details_text += f"📄 {MSG_FILE_NAME}: `{ud.get('file_name', 'N/A')}`\n"
            order_details_text += f"📑 {MSG_PAGE_NUM}: {ud.get('page_num', 'N/A')}\n"
            order_details_text += f"🔢 {MSG_COPIES}: {ud.get('copies', 'N/A')}\n"
            order_details_text += f"📏 {MSG_PAPER_SIZE}: {paper_size_display}\n"
            order_details_text += f"🎨 {MSG_COLOR}: {color_display}\n"
            order_details_text += f"↔️ {MSG_SIDES}: {sides_display}\n"
            order_details_text += f"📐 {MSG_LAYOUT_TYPE}: {layout_display}\n"
            order_details_text += f"📝 {MSG_SPECIAL_INSTRUCTIONS}: {ud.get('special_instructions', 'N/A')}\n"
            order_details_text += f"💰 {TOTAL_PRICE_MSG}: {price_display_channel}\n"
            order_details_text += f"⏰ {MSG_ORDER_TIME}: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

            await context.bot.send_message(chat_id=ORDER_CHANNEL_ID, text=order_details_text, parse_mode='Markdown')
            logger.info(f"Order text sent to channel {ORDER_CHANNEL_ID}")
            await context.bot.send_document(chat_id=ORDER_CHANNEL_ID, document=ud['file_id'], filename=ud.get('file_name', 'order_file'))
            logger.info(f"Order file sent to channel {ORDER_CHANNEL_ID}")


            await query.edit_message_text(MSG_CONFIRM_ORDER, reply_markup=build_new_order_button())

        except KeyError as e:
            logger.error(f"Missing user_data key during confirmation processing by {user_info}: {e}. Data: {ud}")
            await query.edit_message_text(MSG_ERROR_GENERAL + "\nخطا در ارسال اطلاعات سفارش.", reply_markup=build_new_order_button())
        except Exception as e:
            logger.error(f"Failed to send order to channel {ORDER_CHANNEL_ID} for user {user_info}: {e}")
            await query.edit_message_text(MSG_ERROR_GENERAL + f"\nخطا در ارسال سفارش به کانال ({e}). لطفاً به ادمین اطلاع دهید.", reply_markup=build_new_order_button())

        context.user_data.clear()
        return ConversationHandler.END

    elif decision == "action_cancel":
        logger.info(f"Order CANCELLED by {user_info} (Name: {customer_name})")
        await query.edit_message_text(MSG_CANCEL_ORDER, reply_markup=build_new_order_button())
        context.user_data.clear()
        return ConversationHandler.END


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_info = get_user_info(update)
    customer_name = context.user_data.get('customer_name', 'N/A')
    logger.info(f"Conversation cancelled by /cancel command from {user_info} (Name: {customer_name})")
    await update.message.reply_text(MSG_CANCEL_ORDER, reply_markup=ReplyKeyboardRemove())
    await update.message.reply_text("برای شروع مجدد:", reply_markup=build_new_order_button())
    context.user_data.clear()
    return ConversationHandler.END

def main() -> None:
    if not BOT_TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN is not set or using fallback!")
        return
    if not ORDER_CHANNEL_ID:
        logger.warning("ORDER_CHANNEL_ID environment variable not set! Orders cannot be forwarded.")

    persistence = PicklePersistence(filepath='bot_persistence')
    logger.info("Using PicklePersistence for local testing state.")
    application = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(request_new_order, pattern="^action_start_new$")
            ],
        states={
            STATE_WAITING_FILE: [MessageHandler(filters.Document.ALL, receive_file)],
            STATE_WAITING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name_input)],
            STATE_WAITING_PHONE: [MessageHandler(filters.CONTACT | (filters.TEXT & ~filters.COMMAND), handle_phone_input)],
            STATE_WAITING_COPIES: [
                CallbackQueryHandler(handle_copies_input, pattern="^copies_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_copies_input)
            ],
            STATE_WAITING_PAGE_NUM: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_page_num_input)],
            STATE_WAITING_PAPER_SIZE: [
                CallbackQueryHandler(handle_paper_size_input, pattern="^size_")
            ],
            # STATE_WAITING_PAPER_SIZE_INPUT: [ # Removed state
            #     MessageHandler(filters.TEXT & ~filters.COMMAND, handle_paper_size_text)
            # ],
            STATE_WAITING_SIDES: [CallbackQueryHandler(handle_sides_input, pattern="^sides_")],
            STATE_WAITING_COLOR: [CallbackQueryHandler(handle_color_input, pattern="^color_")],
            STATE_WAITING_LAYOUT: [CallbackQueryHandler(handle_layout_input, pattern="^layout_")],
            STATE_WAITING_INSTRUCTIONS: [
                CallbackQueryHandler(handle_instructions_prompt, pattern="^instr_")
            ],
            STATE_WAITING_INSTRUCTIONS_INPUT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_instructions_text)
            ],
            STATE_CONFIRMATION: [CallbackQueryHandler(process_confirmation, pattern="^action_(confirm|cancel)$")],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            CallbackQueryHandler(request_new_order, pattern="^action_start_new$")
            ],
        name="order_conversation",
        persistent=True,
    )
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(request_new_order, pattern="^action_start_new$"))
    logger.info("Starting bot polling for local testing...")
    application.run_polling()

if __name__ == "__main__":
    main()