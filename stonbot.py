import asyncio
import sqlite3
import re
import os
import logging
import datetime
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiohttp import web
import aiohttp

# ========== НАЛАШТУВАННЯ ==========
TOKEN = "8394512581:AAED1pOf6ZPPgXQ_pKUiq_oVY46eo1cVMgE"

# Ім'я вашого JSON-файлу
GOOGLE_CREDS_FILE = "google-creds.json"
GOOGLE_SHEET_NAME = "SportBot Data"
GOOGLE_WORKSHEET_NAME = "products"

# Групи для різних статей
GROUPS = {
    "чоловік": -1002216755275,
    "жінка": -1003933723168
}

ADMIN_ID = 7066974597
WOMAN_ADMIN_ID = 8813891468

# Знижка при онлайн-оплаті (%)
DISCOUNT_PERCENT = 5

# Категорії (без сезонів, сезони будуть окремо)
CATEGORIES_BY_GENDER = {
    "чоловік": {
        "Куртки": ["куртка", "куртки", "jacket", "пуховик", "вітрівка", "вітровка", "бомбер"],
        "Жилетки": ["жилетка", "жилет", "жилетки", "vest"],
        "Футболки": ["футболка", "футболки", "t-shirt"],
        "Поло": ["поло"],
        "Майки": ["майка", "майки", "tank top"],
        "Джинси": ["джинси", "jeans", "джинсы"],
        "Спортивки": ["спортивки", "спортивні штани", "треники"],
        "Брюки": ["штани", "брюки", "pants"],
        "Карго": ["карго", "cargo", "карго штани"],
        "Худі": ["худі", "толстовка", "hoodie"],
        "Світшоти": ["світшот", "світшоти", "sweatshirt", "светр"],
        "Шорти": ["шорти", "шорты", "shorts"],
        "Костюми": ["костюм", "костюми", "комплект", "suit"],
        "Головні убори": ["шапка", "кепка", "бейсболка", "hat", "cap"],
        "Взуття": ["взуття", "кросівки", "черевики", "sneakers", "shoes"],
        "Фліски": ["фліска", "флісова кофта", "фліс", "fleece"],
        "Кофти": ["кофта", "кофта на флісі"],
        "Для тренувань": ["для тренувань", "компресійні штани", "компресійні кофти", "термо кофта", "термо", "тайтси", "компресійний"],
        "Лонгсліви": ["лонгслів", "лонгсліви", "longsleeve", "лонг слив"],
        "Сорочки": ["сорочка", "рубашка", "рубаха"]
    },
    "жінка": {
        "Куртки": ["куртка", "куртки", "jacket", "пуховик", "вітрівка", "вітровка", "бомбер"],
        "Жилетки": ["жилетка", "жилет", "жилетки", "vest"],
        "Футболки": ["футболка", "футболки", "t-shirt"],
        "Поло": ["поло"],
        "Топи": ["топ", "топи", "top"],
        "Майки": ["майка", "майки", "tank top"],
        "Джинси": ["джинси", "jeans", "джинсы"],
        "Спортивки": ["спортивки", "спортивні штани", "треники"],
        "Велосипедки": ["велосипедки", "bike shorts"],
        "Брюки": ["штани", "брюки", "pants"],
        "Карго": ["карго", "cargo", "карго штани"],
        "Худі": ["худі", "толстовка", "hoodie"],
        "Світшоти": ["світшот", "світшоти", "sweatshirt"],
        "Лосини": ["лосини", "легінси", "leggings"],
        "Шорти": ["шорти", "шорты", "shorts"],
        "Костюми": ["костюм", "костюми", "suit"],
        "Спідниці": ["спідниця", "спідниці", "skirt"],
        "Сукні": ["сукня", "сукні", "dress"],
        "Піжами": ["піжама", "піжами", "pajamas"],
        "Купальники": ["купальник", "купальники"],
        "Головні убори": ["шапка", "кепка", "бейсболка", "hat", "cap"],
        "Взуття": ["взуття", "кросівки", "черевики", "sneakers", "shoes"]
    }
}

# Сезони (окремі категорії)
SEASONS = {
    "❄️ Зима": ["зима", "зимовий", "зимня", "зиму", "теплий", "зимова"],
    "🌞 Літо": ["літо", "літній", "літня", "summer", "спекотно", "легкий", "пляж"],
    "🍂 Демісезон": ["демісезон", "весна", "осінь", "spring", "autumn", "дощ", "вітровка", "вітрівка", "софтшел"]
}

SHOE_SIZES = {
    "чоловік": ["38", "38.5", "39", "40", "40.5", "41", "42", "42.5", "43", "44", "44.5", "45", "46", "47"],
    "жінка": ["34", "34.5", "35", "35.5", "36", "37", "37.5", "38", "38.5", "39", "40", "40.5", "41", "42", "42.5", "43"]
}

CLOTHING_SIZES = ["XS", "S", "M", "L", "XL", "XXL"]
SOLD_KEYWORDS = ["ПРОДАНО", "SOLD", "НЕМАЄ", "ЗАБРАНО", "ПРОДАЛ"]
ITEMS_PER_PAGE = 20

# =================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PORT = int(os.environ.get("PORT", 10000))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")
KEEP_ALIVE_URL = RENDER_URL.rstrip("/") + "/health" if RENDER_URL else None

storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

# ========== НАЛАШТУВАННЯ GOOGLE SHEETS ==========
def init_google_sheet():
    """Підключається до Google Sheets через JSON-файл або змінну середовища"""
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # Спершу перевіряємо, чи є змінна середовища GOOGLE_CREDS (для Render)
        if os.environ.get("GOOGLE_CREDS"):
            creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            logger.info("✅ Підключення через змінну середовища GOOGLE_CREDS")
        else:
            # Якщо немає, шукаємо файл (для локального запуску)
            creds_file = os.path.join(os.path.dirname(__file__), GOOGLE_CREDS_FILE)
            if not os.path.exists(creds_file):
                logger.error(f"Файл {GOOGLE_CREDS_FILE} не знайдено в папці бота!")
                return None, None
            creds = ServiceAccountCredentials.from_json_keyfile_name(creds_file, scope)
            logger.info(f"✅ Підключення через файл {GOOGLE_CREDS_FILE}")
        
        gc = gspread.authorize(creds)
        
        try:
            sheet = gc.open(GOOGLE_SHEET_NAME)
        except gspread.SpreadsheetNotFound:
            logger.error(f"Таблиця '{GOOGLE_SHEET_NAME}' не знайдена!")
            return None, None

        try:
            worksheet = sheet.worksheet(GOOGLE_WORKSHEET_NAME)
        except gspread.WorksheetNotFound:
            logger.info(f"Створюємо аркуш '{GOOGLE_WORKSHEET_NAME}'...")
            worksheet = sheet.add_worksheet(title=GOOGLE_WORKSHEET_NAME, rows="1000", cols="20")
            worksheet.append_row(["id", "message_id", "text", "sizes", "gender", "category", "season"])
            logger.info("Аркуш створено з заголовками (з колонкою season).")
        
        return sheet, worksheet
    except Exception as e:
        logger.error(f"Помилка підключення до Google Sheets: {e}")
        return None, None

SHEET, WORKSHEET = init_google_sheet()
if WORKSHEET is None:
    logger.error("НЕ ВДАЛОСЯ ПІДКЛЮЧИТИСЯ ДО GOOGLE SHEETS!")
    class FakeWorksheet:
        def get_all_records(self): return []
        def append_row(self, row): pass
        def find(self, query): return None
        def update_cell(self, row, col, value): pass
        def delete_rows(self, row): pass
    WORKSHEET = FakeWorksheet()

# ========== ФУНКЦІЇ GOOGLE SHEETS ==========
def get_next_id():
    records = WORKSHEET.get_all_records()
    if not records:
        return 1
    max_id = max([row.get('id', 0) for row in records])
    return max_id + 1

def add_product_to_sheet(message_id: int, text: str, sizes: str, gender: str, category: str, season: str = None):
    try:
        new_id = get_next_id()
        WORKSHEET.append_row([new_id, message_id, text[:500], sizes, gender, category, season if season else ""])
        logger.info(f"✅ Товар {message_id} додано в Google Sheets")
        return True
    except Exception as e:
        logger.error(f"Помилка додавання: {e}")
        return False

def update_product_in_sheet(message_id: int, text: str, sizes: str, gender: str, category: str, season: str = None):
    try:
        cell = WORKSHEET.find(str(message_id), in_column=2)
        if cell:
            row_num = cell.row
            WORKSHEET.update_cell(row_num, 3, text[:500])
            WORKSHEET.update_cell(row_num, 4, sizes)
            WORKSHEET.update_cell(row_num, 5, gender)
            WORKSHEET.update_cell(row_num, 6, category)
            WORKSHEET.update_cell(row_num, 7, season if season else "")
            logger.info(f"🔄 Товар {message_id} оновлено")
            return True
    except Exception as e:
        logger.error(f"Помилка оновлення: {e}")
    return False

def delete_product_from_sheet(message_id: int):
    try:
        cell = WORKSHEET.find(str(message_id), in_column=2)
        if cell:
            WORKSHEET.delete_rows(cell.row)
            logger.info(f"🗑️ Товар {message_id} видалено")
            return True
    except Exception as e:
        logger.error(f"Помилка видалення: {e}")
    return False

def get_all_products():
    try:
        # Отримуємо всі записи, де значення читаються як текст
        records = WORKSHEET.get_all_records(value_render_option='UNFORMATTED_VALUE')
        return records
    except Exception as e:
        logger.error(f"Помилка отримання: {e}")
        return []

def find_products_by_size_and_gender(size: str, gender: str, category: str = None, season: str = None):
    products = get_all_products()
    result = []
    search_pattern_with_comma = f",{size},"
    search_pattern_without_comma = size
    
    for p in products:
        if p.get('gender') != gender:
            continue
        if category and p.get('category') != category:
            continue
        if season and p.get('season') != season:
            continue
        sizes_str = p.get('sizes', '')
        
        # Примусово перетворюємо в рядок, якщо це число
        if not isinstance(sizes_str, str):
            sizes_str = str(sizes_str)
        
        # Якщо число (наприклад 4243) - розділяємо на окремі розміри
        if sizes_str.isdigit() and len(sizes_str) > 2:
            import re
            parts = re.findall(r'\d{2}', sizes_str)
            sizes_str = "," + ",".join(parts) + ","
        
        # Шукаємо обидва формати
        if search_pattern_with_comma in sizes_str or sizes_str == search_pattern_without_comma:
            result.append(p)
    
    return result

# ========== ДОПОМІЖНА ФУНКЦІЯ ДЛЯ ЗНИЖКИ ==========
def calculate_discounted_price(total: float) -> tuple:
    """Повертає (сума знижки, ціна зі знижкою)"""
    discount = total * DISCOUNT_PERCENT / 100
    discounted_price = total - discount
    return discount, discounted_price

# ========== КЛАСИ СТАНІВ ==========
class OrderState(StatesGroup):
    waiting_for_name = State()
    waiting_for_phone = State()
    waiting_for_city = State()
    waiting_for_department = State()
    waiting_for_bank = State()
    waiting_for_payment = State()

class UserState(StatesGroup):
    gender = State()

# ========== БАЗА ДАНИХ (SQLITE для кошика, замовлень, налаштувань) ==========
conn = sqlite3.connect("shop.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY,
        message_id INTEGER,
        text TEXT,
        sizes TEXT,
        gender TEXT,
        category TEXT,
        season TEXT
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        product_id INTEGER,
        message_id INTEGER,
        group_id INTEGER,
        product_name TEXT,
        product_size TEXT,
        product_price REAL,
        quantity INTEGER DEFAULT 1,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY,
        order_number TEXT UNIQUE,
        user_id INTEGER,
        user_name TEXT,
        user_phone TEXT,
        user_city TEXT,
        user_department TEXT,
        total_amount REAL,
        original_amount REAL,
        discount_amount REAL,
        items TEXT,
        items_with_links TEXT,
        order_gender TEXT,
        selected_bank TEXT,
        status TEXT DEFAULT 'нове',
        payment_status TEXT DEFAULT 'очікує',
        payment_screenshot TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
""")

cursor.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
""")

cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('mono_card_man', '')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('privat_card_man', '')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('mono_card_woman', '')")
cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('privat_card_woman', '')")
conn.commit()

# ========== ДОПОМІЖНІ ФУНКЦІЇ ==========
def get_gender_by_chat_id(chat_id: int) -> str:
    for gender, gid in GROUPS.items():
        if gid == chat_id:
            return gender
    return "унісекс"

def extract_sizes(text: str, category: str = None, gender: str = None) -> list:
    sizes_found = []
    if category == "Взуття" and gender:
        shoe_sizes = SHOE_SIZES.get(gender, [])
        for size in shoe_sizes:
            pattern = r'\b' + re.escape(size) + r'\b'
            if re.search(pattern, text):
                sizes_found.append(size)
    else:
        pattern = r'\b(XXL|XL|XS|М|ХL|ХХL|S|M|L)\b'
        matches = re.findall(pattern, text.upper())
        convert = {'М': 'M', 'ХL': 'XL', 'ХХL': 'XXL'}
        for m in matches:
            m_converted = convert.get(m, m)
            if m_converted not in sizes_found:
                sizes_found.append(m_converted)
        sizes_found.sort(key=lambda x: (len(x), x), reverse=True)
    return sizes_found

def extract_category(text: str, gender: str) -> str:
    if not text:
        return None
    text_lower = text.lower()
    categories = CATEGORIES_BY_GENDER.get(gender, {})
    for category, keywords in categories.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                return category
    return None

def extract_season(text: str) -> str:
    """Визначає сезон товару за ключовими словами"""
    if not text:
        return None
    text_lower = text.lower()
    for season, keywords in SEASONS.items():
        for kw in keywords:
            if kw in text_lower:
                return season
    return None

def is_sold(text: str) -> bool:
    if not text:
        return False
    text_upper = text.upper()
    for kw in SOLD_KEYWORDS:
        if kw.upper() in text_upper:
            return True
    return False

def extract_price(text: str) -> float:
    if not text:
        return 0
    text_lower = text.lower()
    match = re.search(r'ціна\s*:?\s*(\d+(?:\.\d+)?)', text_lower, re.IGNORECASE)
    if match:
        return float(match.group(1))
    match = re.search(r'(\d+(?:\.\d+)?)\s*грн', text_lower, re.IGNORECASE)
    if match:
        return float(match.group(1))
    matches = re.findall(r'\b(\d+(?:\.\d+)?)\b', text)
    for m in matches:
        price = float(m)
        if 10 < price < 10000:
            return price
    return 0

def generate_order_number():
    now = datetime.datetime.now()
    return f"ORD-{now.strftime('%Y%m%d%H%M%S')}"

async def get_main_menu_keyboard(gender: str = None):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Всі розміри", callback_data="show_all_sizes")],
        [InlineKeyboardButton(text="📂 Детальний пошук", callback_data="show_categories")],
        [InlineKeyboardButton(text="🛒 Кошик", callback_data="show_cart"),
         InlineKeyboardButton(text="🔄 Змінити стать", callback_data="change_gender")],
        [InlineKeyboardButton(text="📱 Наші групи", callback_data="our_groups"),
         InlineKeyboardButton(text="ℹ️ Допомога", callback_data="help")]
    ])

async def safe_send_new_message(callback, text, reply_markup=None):
    try:
        await callback.message.delete()
    except:
        pass
    await callback.message.answer(text, reply_markup=reply_markup)
    await callback.answer()

# ========== ФУНКЦІЇ КОШИКА ==========
def add_to_cart(user_id: int, product_id: int, message_id: int, group_id: int, product_name: str, product_size: str, product_price: float):
    cursor.execute("""
        INSERT INTO cart (user_id, product_id, message_id, group_id, product_name, product_size, product_price)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, product_id, message_id, group_id, product_name, product_size, product_price))
    conn.commit()

def get_cart(user_id: int):
    cursor.execute("""
        SELECT product_id, message_id, group_id, product_name, product_size, product_price, quantity
        FROM cart WHERE user_id = ?
    """, (user_id,))
    return cursor.fetchall()

def clear_cart(user_id: int):
    cursor.execute("DELETE FROM cart WHERE user_id = ?", (user_id,))
    conn.commit()

def get_cart_total(user_id: int):
    cursor.execute("SELECT SUM(product_price * quantity) FROM cart WHERE user_id = ?", (user_id,))
    total = cursor.fetchone()[0]
    return total if total else 0

def remove_from_cart(user_id: int, product_id: int, size: str):
    cursor.execute("DELETE FROM cart WHERE user_id = ? AND product_id = ? AND product_size = ?", (user_id, product_id, size))
    conn.commit()

async def show_cart(callback_or_message, user_id: int, edit: bool = False):
    cart_items = get_cart(user_id)
    total = get_cart_total(user_id)
    
    if not cart_items:
        text = "🛒 Ваш кошик порожній.\n\nДодайте товари через кнопку '🛒 В кошик' під товаром."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
        ])
        if edit and hasattr(callback_or_message, 'message'):
            await callback_or_message.message.edit_text(text, reply_markup=keyboard)
        else:
            await callback_or_message.answer(text, reply_markup=keyboard)
        return
    
    discount, discounted_total = calculate_discounted_price(total)
    
    text = "🛒 **Ваш кошик:**\n\n"
    for item in cart_items:
        product_id, msg_id, group_id, name, size, price, qty = item
        post_link = f"https://t.me/c/{str(group_id)[4:]}/{msg_id}"
        text += f"📦 [{name}]({post_link}) (Розмір: {size}) x{qty} = {price * qty} грн\n"
    text += f"\n💰 **Загальна сума: {total:.2f} грн**"
    if discount > 0:
        text += f"\n🎁 **Ваша знижка (-{DISCOUNT_PERCENT}%): {discount:.2f} грн**"
    text += f"\n💎 **Сума до оплати: {discounted_total:.2f} грн**\n\n"
    text += "Для оформлення замовлення натисніть '📦 Оформити замовлення'"
    
    keyboard_buttons = []
    for item in cart_items:
        product_id, msg_id, group_id, name, size, price, qty = item
        keyboard_buttons.append([
            InlineKeyboardButton(text=f"❌ Видалити {name} ({size})", callback_data=f"remove_cart_{product_id}_{size}")
        ])
    keyboard_buttons.append([InlineKeyboardButton(text="📦 Оформити замовлення", callback_data="checkout")])
    keyboard_buttons.append([InlineKeyboardButton(text="🗑 Очистити кошик", callback_data="clear_cart")])
    keyboard_buttons.append([InlineKeyboardButton(text="🔙 Головне меню", callback_data="main_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)
    
    if edit and hasattr(callback_or_message, 'message'):
        await callback_or_message.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await callback_or_message.answer(text, reply_markup=keyboard, parse_mode="Markdown", disable_web_page_preview=True)

# ========== КОМАНДА /start ==========
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Чоловік", callback_data="gender_чоловік")],
        [InlineKeyboardButton(text="👩 Жінка", callback_data="gender_жінка")]
    ])
    await message.answer(
        "👕 **Вітаю в магазині!**\n\n"
        "Обери стать, для якої шукатимеш товари:\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🎁 **ЗНИЖКА 5%** при онлайн-оплаті!\n"
        "💰 Знижка автоматично застосовується до всього замовлення.\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📱 **Підпишіться на наші групи:**\n"
        "• [👕 Чоловічі речі](https://t.me/ston_107)\n"
        "• [👗 Жіночі речі](https://t.me/brandpage_she)\n\n"
        "Підписка потрібна для перегляду всіх товарів! 🔓",
        reply_markup=keyboard,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

@dp.callback_query(lambda c: c.data.startswith("gender_"))
async def set_gender(callback: types.CallbackQuery, state: FSMContext):
    gender = callback.data.split("_")[1]
    await state.update_data(gender=gender)
    keyboard = await get_main_menu_keyboard(gender)
    await safe_send_new_message(
        callback,
        f"👋 Вибрана стать: {gender}\n\n🏠 Головне меню:",
        keyboard
    )

@dp.callback_query(lambda c: c.data == "change_gender")
async def change_gender(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨 Чоловік", callback_data="gender_чоловік")],
        [InlineKeyboardButton(text="👩 Жінка", callback_data="gender_жінка")]
    ])
    await safe_send_new_message(callback, "🔄 Обери нову стать:", keyboard)

@dp.callback_query(lambda c: c.data == "main_menu")
async def back_to_main_menu(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    gender = data.get("gender", "чоловік")
    keyboard = await get_main_menu_keyboard(gender)
    await safe_send_new_message(
        callback,
        f"👋 Вибрана стать: {gender}\n\n🏠 Головне меню:",
        keyboard
    )

@dp.callback_query(lambda c: c.data == "help")
async def show_help(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await safe_send_new_message(
        callback,
        "📖 **Інструкція для покупця:**\n\n"
        "1️⃣ Обери 🔍 'Всі розміри' → вибери розмір → отримаєш всі товари твого розміру.\n\n"
        "2️⃣ Обери 📂 'Детальний пошук' → обери категорію → обери розмір.\n\n"
        "3️⃣ Під товаром натисни 🛒 'В кошик' → товар додасться до кошика.\n\n"
        "4️⃣ Перейди в 🛒 'Кошик' → оформи замовлення → вкажи дані для доставки.\n\n"
        "5️⃣ Після оформлення обери банк (Монобанк або Приватбанк) → підтверди → надішли скріншот чека.\n\n"
        "🔄 Змінити стать можна кнопкою в головному меню."
        "🎁 **Знижка 5% при онлайн-оплаті!**\n\n"
        "📌 **Для взуття:** розміри вказані в європейському форматі (EUR).\n\n",
        keyboard
    )

# ========== НАШІ ГРУПИ ==========
@dp.callback_query(lambda c: c.data == "our_groups")
async def our_groups(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👕 Чоловічі речі", url="https://t.me/ston_107")],
        [InlineKeyboardButton(text="👗 Жіночі речі", url="https://t.me/brandpage_she")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")]
    ])
    await safe_send_new_message(
        callback,
        "📱 **Наші групи в Telegram**\n\n"
        "👇 **Підпишіться, щоб бачити всі товари:**\n\n"
        "• **👕 Чоловічі речі** – одяг, взуття, аксесуари для чоловіків\n"
        "• **👗 Жіночі речі** – стильний одяг для жінок\n\n"
        "Після підписки ви зможете переглядати всі товари прямо в боті! 🛍️",
        reply_markup=keyboard
    )

# ========== КОШИК (обробники) ==========
@dp.callback_query(lambda c: c.data == "show_cart")
async def show_cart_callback(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await show_cart(callback, callback.from_user.id, edit=True)

@dp.callback_query(lambda c: c.data == "clear_cart")
async def clear_cart_callback(callback: types.CallbackQuery):
    clear_cart(callback.from_user.id)
    await callback.answer("✅ Кошик очищено!", show_alert=True)
    await show_cart(callback, callback.from_user.id, edit=True)

@dp.callback_query(lambda c: c.data.startswith("remove_cart_"))
async def remove_cart_item(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    product_id = int(parts[2])
    size = parts[3]
    remove_from_cart(callback.from_user.id, product_id, size)
    await callback.answer("❌ Товар видалено з кошика!", show_alert=True)
    await show_cart(callback, callback.from_user.id, edit=True)

@dp.callback_query(lambda c: c.data == "checkout")
async def start_checkout(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cart_items = get_cart(user_id)
    total = get_cart_total(user_id)
    
    if not cart_items:
        await callback.answer("Кошик порожній!", show_alert=True)
        return
    
    discount, discounted_total = calculate_discounted_price(total)
    
    order_gender = "чоловік"
    for item in cart_items:
        product_id, msg_id, group_id, name, size, price, qty = item
        products = get_all_products()
        for p in products:
            if p.get('message_id') == msg_id:
                order_gender = p.get('gender', 'чоловік')
                break
        break
    
    await state.update_data(
        cart_items=cart_items, 
        total=total, 
        discount=discount, 
        discounted_total=discounted_total,
        order_gender=order_gender
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Повернутись до кошика", callback_data="show_cart")]
    ])
    
    await callback.message.edit_text(
        "📝 **Оформлення замовлення**\n\n"
        "Будь ласка, введіть ваші дані для доставки Новою Поштою.\n\n"
        "✏️ Введіть **ваше ім'я та прізвище**:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(OrderState.waiting_for_name)
    await callback.answer()

@dp.message(OrderState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(user_name=message.text)
    await message.answer("📞 Введіть ваш **номер телефону** (наприклад, +380XXXXXXXXX):", parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_phone)

@dp.message(OrderState.waiting_for_phone)
async def process_phone(message: types.Message, state: FSMContext):
    await state.update_data(user_phone=message.text)
    await message.answer("🏙️ Введіть **назву міста**:", parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_city)

@dp.message(OrderState.waiting_for_city)
async def process_city(message: types.Message, state: FSMContext):
    await state.update_data(user_city=message.text)
    await message.answer("🏢 Введіть **номер відділення Нової Пошти**:", parse_mode="Markdown")
    await state.set_state(OrderState.waiting_for_department)

@dp.message(OrderState.waiting_for_department)
async def process_department(message: types.Message, state: FSMContext):
    await state.update_data(user_department=message.text)
    
    data = await state.get_data()
    total = data.get('total', 0)
    discounted_total = data.get('discounted_total', total)
    cart_items = data.get('cart_items', [])
    
    items_list = []
    items_with_links = []
    
    for item in cart_items:
        product_id, msg_id, group_id, name, size, price, qty = item
        post_link = f"https://t.me/c/{str(group_id)[4:]}/{msg_id}"
        items_list.append(f"{name} (розмір {size}) x{qty} = {price * qty} грн")
        items_with_links.append(f"[{name}]({post_link}) (розмір {size}) x{qty} = {price * qty} грн")
    
    items_text = "\n".join(items_list)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити замовлення", callback_data="confirm_order")],
        [InlineKeyboardButton(text="🔙 Редагувати", callback_data="show_cart")]
    ])
    
    await message.answer(
        f"📋 **Перевірте дані замовлення:**\n\n"
        f"👤 Ім'я: {data['user_name']}\n"
        f"📞 Телефон: {data['user_phone']}\n"
        f"🏙️ Місто: {data['user_city']}\n"
        f"🏢 Відділення НП: {data['user_department']}\n\n"
        f"📦 **Товари:**\n{items_text}\n\n"
        f"💰 **Сума до сплати: {discounted_total:.2f} грн**\n"
        f"🎁 (знижка -{DISCOUNT_PERCENT}%)\n\n"
        f"Якщо все вірно, натисніть 'Підтвердити замовлення'",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.set_state(OrderState.waiting_for_bank)

@dp.callback_query(lambda c: c.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    discounted_total = data.get('discounted_total', 0)
    order_gender = data.get('order_gender', 'чоловік')
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Монобанк", callback_data="bank_mono"),
         InlineKeyboardButton(text="💳 Приватбанк", callback_data="bank_privat")],
        [InlineKeyboardButton(text="🔙 Змінити дані", callback_data="show_cart")]
    ])
    
    await callback.message.edit_text(
        f"✅ **Стать замовлення:** {order_gender}\n"
        f"💰 **Сума до сплати:** {discounted_total:.2f} грн\n"
        f"🎁 (знижка -{DISCOUNT_PERCENT}%)\n\n"
        f"💳 **Виберіть банк для оплати:**",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("bank_"))
async def process_bank_selection(callback: types.CallbackQuery, state: FSMContext):
    bank = callback.data.split("_")[1]
    data = await state.get_data()
    order_gender = data.get('order_gender', 'чоловік')
    discounted_total = data.get('discounted_total', 0)
    
    if order_gender == "чоловік":
        cursor.execute(f"SELECT value FROM settings WHERE key = '{bank}_card_man'")
    else:
        cursor.execute(f"SELECT value FROM settings WHERE key = '{bank}_card_woman'")
    
    result = cursor.fetchone()
    card_number = result[0] if result and result[0] else "XXXX-XXXX-XXXX-XXXX"
    
    await state.update_data(selected_bank=bank, selected_card=card_number)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Підтвердити замовлення", callback_data="final_confirm")],
        [InlineKeyboardButton(text="🔙 Змінити банк", callback_data="confirm_order")]
    ])
    
    await callback.message.edit_text(
        f"✅ **Вибрано банк:** {'Монобанк' if bank == 'mono' else 'Приватбанк'}\n"
        f"💳 **Картка:** `{card_number}`\n\n"
        f"💰 **Сума до сплати:** {discounted_total:.2f} грн\n"
        f"🎁 (знижка -{DISCOUNT_PERCENT}%)\n\n"
        f"Натисніть 'Підтвердити замовлення' для продовження",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await callback.answer()

@dp.callback_query(lambda c: c.data == "final_confirm")
async def final_confirm_order(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    
    order_number = generate_order_number()
    
    cart_items = data.get('cart_items', [])
    selected_card = data.get('selected_card', '')
    selected_bank = data.get('selected_bank', '')
    order_gender = data.get('order_gender', 'чоловік')
    original_total = data.get('total', 0)
    discounted_total = data.get('discounted_total', original_total)
    discount = data.get('discount', 0)
    
    items_list = []
    items_with_links = []
    
    for item in cart_items:
        product_id, msg_id, group_id, name, size, price, qty = item
        items_list.append(f"{name} (розмір {size}) x{qty} = {price * qty} грн")
        post_link = f"https://t.me/c/{str(group_id)[4:]}/{msg_id}"
        items_with_links.append(f"[{name}]({post_link}) (розмір {size}) x{qty} = {price * qty} грн")
    
    items_text = "\n".join(items_list)
    items_with_links_text = "\n".join(items_with_links)
    
    cursor.execute("""
        INSERT INTO orders (order_number, user_id, user_name, user_phone, user_city, user_department, 
                           total_amount, original_amount, discount_amount, items, items_with_links, 
                           order_gender, selected_bank, status, payment_status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'нове', 'очікує')
    """, (order_number, user_id, data['user_name'], data['user_phone'], 
          data['user_city'], data['user_department'], discounted_total, original_total, discount,
          items_text, items_with_links_text, order_gender, selected_bank))
    conn.commit()
    
    clear_cart(user_id)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Додати чек/скрін", callback_data=f"upload_payment_{order_number}")],
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
    ])
    
    if order_gender == "чоловік":
        admin_to_notify = ADMIN_ID
    else:
        admin_to_notify = WOMAN_ADMIN_ID
    
    admin_text = (
        f"🆕 **НОВЕ ЗАМОВЛЕННЯ #{order_number}**\n\n"
        f"👤 Клієнт: {data['user_name']}\n"
        f"🆔 ID: {user_id}\n"
        f"📞 Телефон: {data['user_phone']}\n"
        f"🏙️ Місто: {data['user_city']}\n"
        f"🏢 Відділення НП: {data['user_department']}\n"
        f"💰 Сума зі знижкою: {discounted_total:.2f} грн\n"
        f"💰 Оригінальна сума: {original_total:.2f} грн\n"
        f"🎁 Знижка: {discount:.2f} грн ({DISCOUNT_PERCENT}%)\n"
        f"💳 Банк: {'Монобанк' if selected_bank == 'mono' else 'Приватбанк'}\n"
        f"⚧️ Стать замовлення: {order_gender}\n\n"
        f"📦 **Товари:**\n{items_with_links_text}\n\n"
        f"⏳ Статус: очікує оплати"
    )
    
    await bot.send_message(admin_to_notify, admin_text, parse_mode="Markdown", disable_web_page_preview=True)
    
    await callback.message.edit_text(
        f"✅ **Замовлення #{order_number} створено!**\n\n"
        f"💳 **Оплата на картку {selected_bank.upper()}:**\n"
        f"`{selected_card}`\n\n"
        f"💰 **Сума до сплати:** {discounted_total:.2f} грн\n"
        f"🎁 (знижка -{DISCOUNT_PERCENT}%)\n\n"
        f"📸 Після оплати натисніть кнопку 'Додати чек/скрін' та завантажте фото чека.\n\n"
        f"Ми перевіримо оплату та надішлемо замовлення Новою Поштою.",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await state.clear()
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("upload_payment_"))
async def upload_payment(callback: types.CallbackQuery, state: FSMContext):
    order_number = callback.data.split("_")[2]
    await state.update_data(order_number=order_number)
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
    ])
    
    await callback.message.edit_text(
        f"📸 **Завантажте фото/скріншот чека** для замовлення #{order_number}\n\n"
        f"Надішліть фото або файл з підтвердженням оплати.",
        reply_markup=keyboard
    )
    await state.set_state(OrderState.waiting_for_payment)
    await callback.answer()

@dp.message(OrderState.waiting_for_payment)
async def process_payment_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    order_number = data.get('order_number')
    
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    
    if file_id:
        cursor.execute("UPDATE orders SET payment_screenshot = ?, payment_status = 'оплачено' WHERE order_number = ?",
                       (file_id, order_number))
        conn.commit()
        
        cursor.execute("SELECT user_name, user_phone, user_city, user_department, total_amount, original_amount, discount_amount, items_with_links, order_gender FROM orders WHERE order_number = ?", (order_number,))
        order = cursor.fetchone()
        
        if order[8] == "чоловік":
            admin_to_notify = ADMIN_ID
        else:
            admin_to_notify = WOMAN_ADMIN_ID
        
        admin_text = (
            f"✅ **ОПЛАЧЕНО ЗАМОВЛЕННЯ #{order_number}**\n\n"
            f"👤 Клієнт: @{message.from_user.username if message.from_user.username else message.from_user.full_name}\n"
            f"🆔 ID: {message.from_user.id}\n"
            f"📞 Телефон: {order[1]}\n"
            f"🏙️ Місто: {order[2]}\n"
            f"🏢 Відділення НП: {order[3]}\n"
            f"💰 Сума зі знижкою: {order[4]:.2f} грн\n"
            f"💰 Оригінальна сума: {order[5]:.2f} грн\n"
            f"🎁 Знижка: {order[6]:.2f} грн\n"
            f"⚧️ Стать замовлення: {order[8]}\n\n"
            f"📦 **Товари:**\n{order[7]}\n\n"
            f"🚀 **Статус: оплата підтверджена! Відправляйте замовлення.**"
        )
        
        await bot.send_message(admin_to_notify, admin_text, parse_mode="Markdown", disable_web_page_preview=True)
        
        if message.photo:
            await bot.send_photo(admin_to_notify, file_id, caption=f"🧾 Чек до замовлення #{order_number}")
        elif message.document:
            await bot.send_document(admin_to_notify, file_id, caption=f"🧾 Чек до замовлення #{order_number}")
        
        await message.answer(
            f"✅ **Дякуємо за оплату!**\n\n"
            f"Ваше замовлення #{order_number} прийнято в роботу.\n"
            f"Ми перевіримо оплату та надішлемо замовлення Новою Поштою.\n\n"
            f"Очікуйте повідомлення з трек-номером.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")]
            ])
        )
    else:
        await message.answer("❌ Будь ласка, надішліть фото або файл чека.")
        return
    
    await state.clear()

# ========== АДМІН-КОМАНДИ ==========
@dp.message(Command("setcard"))
async def set_bank_card(message: types.Message):
    if message.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await message.answer("⛔ Немає прав.")
        return
    
    args = message.text.replace("/setcard", "").strip().split()
    if len(args) < 3:
        await message.answer("Введіть: /setcard mono man 4149-XXXX-XXXX-XXXX\n"
                            "Або: /setcard privat woman 5168-XXXX-XXXX-XXXX\n\n"
                            "Доступні банки: mono, privat\n"
                            "Доступні статі: man, woman")
        return
    
    bank = args[0].lower()
    gender = args[1].lower()
    card_number = args[2]
    
    if bank not in ["mono", "privat"]:
        await message.answer("Банк має бути 'mono' або 'privat'")
        return
    
    if gender not in ["man", "woman"]:
        await message.answer("Стать має бути 'man' або 'woman'")
        return
    
    key = f"{bank}_card_{gender}"
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, card_number))
    conn.commit()
    
    bank_name = "Монобанк" if bank == "mono" else "Приватбанк"
    gender_name = "чоловічих" if gender == "man" else "жіночих"
    await message.answer(f"✅ {bank_name} картка для {gender_name} замовлень встановлена: {card_number}")

@dp.message(Command("orders"))
async def show_orders(message: types.Message):
    if message.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await message.answer("⛔ Немає прав.")
        return
    
    if message.from_user.id == ADMIN_ID:
        cursor.execute("SELECT order_number, user_name, total_amount, original_amount, discount_amount, selected_bank, status, payment_status, created_at FROM orders WHERE order_gender = 'чоловік' ORDER BY created_at DESC LIMIT 10")
    else:
        cursor.execute("SELECT order_number, user_name, total_amount, original_amount, discount_amount, selected_bank, status, payment_status, created_at FROM orders WHERE order_gender = 'жінка' ORDER BY created_at DESC LIMIT 10")
    
    orders = cursor.fetchall()
    
    if not orders:
        await message.answer("Немає замовлень.")
        return
    
    text = "📋 **Останні замовлення:**\n\n"
    for order in orders:
        bank_name = "Монобанк" if order[5] == "mono" else "Приватбанк" if order[5] else "—"
        text += f"#{order[0]} | {order[1]} | {order[2]:.2f} грн (зі знижкою) | {bank_name} | {order[6]} | {order[7]} | {order[8][:10]}\n"
    
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("info"))
async def admin_info(message: types.Message):
    if message.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await message.answer("⛔ Ця команда тільки для адміністраторів.")
        return
    
    text = (
        "👨‍💼 **Інструкція для адміністраторів**\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📝 **Додавання товарів:**\n"
        "• Просто напиши пост у відповідній групі\n"
        "• Бот автоматично визначить розміри, категорію, сезон та стать\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "❌ **Продаж товару:**\n"
        "• Відредагуй пост → допиши в кінці 'ПРОДАНО'\n"
        "• Бот автоматично прибере товар з пошуку\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📏 **Зміна розмірів:**\n"
        "• Додати розмір → відредагуй пост і вкажи новий розмір\n"
        "• Прибрати розмір → відредагуй пост і прибери непотрібний розмір\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🌸 **Сезони (додаються автоматично):**\n"
        "• **❄️ Зима**: зима, зимовий, пуховик, теплий\n"
        "• **🌞 Літо**: літо, літній, спекотно, легкий, пляж\n"
        "• **🍂 Демісезон**: демісезон, весна, осінь, дощ, вітровка\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💰 **Знижка:**\n"
        "• При онлайн-оплаті надається знижка {DISCOUNT_PERCENT}%\n"
        "• Знижка автоматично застосовується при оформленні замовлення\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "💳 **Встановлення карток:**\n"
        "• `/setcard mono man 4149-XXXX-XXXX-XXXX` — твоя Монобанк\n"
        "• `/setcard privat man 5168-XXXX-XXXX-XXXX` — твій Приватбанк\n"
        "• `/setcard mono woman 4149-XXXX-XXXX-XXXX` — Монобанк дружини\n"
        "• `/setcard privat woman 5168-XXXX-XXXX-XXXX` — Приватбанк дружини\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📋 **Інші команди:**\n"
        "• `/orders` — перегляд останніх замовлень\n"
        "• `/info` — ця інструкція\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 **Важливо:**\n"
        "• Для взуття використовуйте європейські розміри (38, 39, 40...)\n"
        "• Для одягу використовуйте XS, S, M, L, XL, XXL\n"
        "• **Формат ціни:** `ціна: 850 грн` або `850 грн`\n"
    )
    
    await message.answer(text, parse_mode="Markdown")

# ========== ТИМЧАСОВА КОМАНДА ДЛЯ ДІАГНОСТИКИ ==========
@dp.message(Command("test_season"))
async def test_season(message: types.Message):
    if message.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await message.answer("⛔ Немає прав.")
        return
    
    products = get_all_products()
    result = "📊 **Всі товари з сезонами:**\n\n"
    for p in products:
        result += f"ID: {p.get('message_id')} | Кат: {p.get('category')} | Сезон: {p.get('season')} | Розміри: {p.get('sizes')}\n"
        if len(result) > 3000:
            break
    
    await message.answer(result, parse_mode="Markdown")

# ========== НОВА КОМАНДА /del_product ==========
@dp.message(Command("del_product"))
async def delete_product(message: types.Message):
    if message.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await message.answer("⛔ Немає прав.")
        return
    
    args = message.text.replace("/del_product", "").strip()
    if not args:
        await message.answer("Введіть ID повідомлення: /del_product 123")
        return
    
    try:
        message_id = int(args)
        delete_product_from_sheet(message_id)
        await message.answer(f"✅ Товар з ID {message_id} видалено з бази.")
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

# ========== обробник для кнопки "Видалити" ==========
@dp.callback_query(lambda c: c.data.startswith("del_"))
async def delete_product_callback(callback: types.CallbackQuery):
    # Перевіряємо, чи користувач адмін
    if callback.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await callback.answer("⛔ Немає прав!", show_alert=True)
        return
    
    msg_id = int(callback.data.split("_")[1])
    delete_product_from_sheet(msg_id)
    
    await callback.answer("✅ Товар видалено!", show_alert=True)
    
    # Оновлюємо повідомлення, щоб прибрати видалений товар
    await callback.message.delete()
    await callback.message.answer("🔄 Список оновлено. Почніть пошук заново.")

@dp.message(Command("pin_bot"))
async def pin_bot_button(message: types.Message):
    if message.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await message.answer("⛔ Немає прав.")
        return
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Відкрити бота", url="https://t.me/ston107_bot")]
    ])
    
    msg = await message.answer(
        "🛍️ **ШВИДКИЙ ПОШУК ТОВАРІВ** 🛍️\n\n"
        "👇 Натисни кнопку нижче, обери свій розмір 👇",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    
    try:
        await msg.pin()
        await message.answer("✅ Повідомлення закріплено!")
    except Exception as e:
        await message.answer(f"❌ Помилка: {e}")

@dp.message(Command("reset_db"))
async def reset_database(message: types.Message):
    # Перевірка, що команду виконав адмін
    if message.from_user.id not in [ADMIN_ID, WOMAN_ADMIN_ID]:
        await message.answer("⛔ Немає прав.")
        return

    try:
        # Шлях до файлу бази даних
        db_path = "shop.db"
        
        # Перевіряємо, чи існує файл
        if os.path.exists(db_path):
            os.remove(db_path)
            await message.answer("✅ Файл `shop.db` успішно видалено. Перезапустіть бота, щоб створити нову базу.", parse_mode="Markdown")
        else:
            await message.answer("❌ Файл `shop.db` не знайдено.")
    except Exception as e:
        await message.answer(f"❌ Сталася помилка: {e}")

# ========== ВСІ РОЗМІРИ ==========
@dp.callback_query(lambda c: c.data == "show_all_sizes")
async def show_all_sizes(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    gender = data.get("gender", "чоловік")
    
    sizes = CLOTHING_SIZES
    buttons = []
    row = []
    for i, size in enumerate(sizes):
        row.append(InlineKeyboardButton(text=size, callback_data=f"all_size_{size}_{gender}"))
        if len(row) == 4 or i == len(sizes) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton(text="🔙 Головне меню", callback_data="main_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_send_new_message(callback, "🔍 Обери розмір одягу:", keyboard)

@dp.callback_query(lambda c: c.data.startswith("all_size_"))
async def show_products_by_size(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    size = parts[2]
    gender = parts[3]
    await show_products_list(callback, size, gender=gender, category=None, season=None, page=0, prefix="all")

# ========== ДЕТАЛЬНИЙ ПОШУК ==========
@dp.callback_query(lambda c: c.data == "show_categories")
async def show_categories(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    gender = data.get("gender", "чоловік")
    
    # Об'єднуємо звичайні категорії та сезони
    categories = list(CATEGORIES_BY_GENDER.get(gender, {}).keys())
    seasons = list(SEASONS.keys())
    
    buttons = []
    # Звичайні категорії (по 2 в рядку)
    for i in range(0, len(categories), 2):
        row = []
        for cat in categories[i:i+2]:
            row.append(InlineKeyboardButton(text=cat, callback_data=f"cat_{cat}_{gender}"))
        buttons.append(row)
    
    # Роздільник
    buttons.append([InlineKeyboardButton(text="━━━ 🌸 СЕЗОНИ 🌸 ━━━", callback_data="noop")])
    
    # Сезони (по 2 в рядку)
    for i in range(0, len(seasons), 2):
        row = []
        for season in seasons[i:i+2]:
            row.append(InlineKeyboardButton(text=season, callback_data=f"season_{season}_{gender}"))
        buttons.append(row)
    
    buttons.append([InlineKeyboardButton(text="🔙 Головне меню", callback_data="main_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_send_new_message(callback, "📂 Обери категорію або сезон:", keyboard)

@dp.callback_query(lambda c: c.data == "noop")
async def noop_handler(callback: types.CallbackQuery):
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("cat_") and not c.data.startswith("cat_size_"))
async def choose_size_for_category(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    category = parts[1]
    gender = parts[2]
    
    if category == "Взуття":
        sizes = SHOE_SIZES.get(gender, CLOTHING_SIZES)
        size_label = "EUR"
    else:
        sizes = CLOTHING_SIZES
        size_label = ""
    
    buttons = []
    row = []
    for i, size in enumerate(sizes):
        button_text = f"{size} {size_label}" if size_label else size
        row.append(InlineKeyboardButton(text=button_text, callback_data=f"cat_size_{category}_{gender}_{size}"))
        if len(row) == 4 or i == len(sizes) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton(text="🔙 Категорії", callback_data="show_categories")])
    buttons.append([InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    
    if category == "Взуття":
        size_hint = "\n\nРозміри вказані в європейському форматі (EUR)"
    else:
        size_hint = ""
    
    await safe_send_new_message(callback, f"📂 {category}{size_hint}\n\nОбери розмір:", keyboard)

@dp.callback_query(lambda c: c.data.startswith("season_") and not c.data.startswith("season_size_"))
async def choose_size_for_season(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    season = parts[1]
    gender = parts[2]
    
    sizes = CLOTHING_SIZES
    buttons = []
    row = []
    for i, size in enumerate(sizes):
        callback_data = f"season_size_{season}_{gender}_{size}"
        row.append(InlineKeyboardButton(text=size, callback_data=callback_data))
        if len(row) == 4 or i == len(sizes) - 1:
            buttons.append(row)
            row = []
    buttons.append([InlineKeyboardButton(text="🔙 Категорії", callback_data="show_categories")])
    buttons.append([InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu")])
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    await safe_send_new_message(callback, f"📂 {season}\n\nОбери розмір:", keyboard)

@dp.callback_query(lambda c: c.data.startswith("season_size_"))
async def show_products_by_season_size(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    # Формат: season_size_🌞 Літо_жінка_XS
    if len(parts) >= 5:
        season = parts[2]
        gender = parts[3]
        size = parts[4]
    else:
        await callback.message.answer("❌ Помилка формату даних")
        await callback.answer()
        return
    
    await show_products_list(callback, size, gender=gender, category=None, season=season, page=0, prefix="season")

@dp.callback_query(lambda c: c.data.startswith("cat_size_"))
async def show_products_by_category_size(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    category = parts[2]
    gender = parts[3]
    size = parts[4]
    await show_products_list(callback, size, gender=gender, category=category, season=None, page=0, prefix="cat")

# ========== ПОКАЗ ТОВАРІВ (з кнопкою В кошик) ==========
async def show_products_list(callback: types.CallbackQuery, size: str, gender: str, category: str = None, season: str = None, page: int = 0, prefix: str = "all"):
    group_id = GROUPS.get(gender)
    if not group_id:
        await callback.message.answer("❌ Помилка: не знайдено групу для цієї статі")
        return
    
    all_products = find_products_by_size_and_gender(size, gender, category, season)
    
    available = []
    for p in all_products:
        text = p.get('text', '')
        if is_sold(text):
            delete_product_from_sheet(p.get('message_id'))
        else:
            available.append(p)
    
    total = len(available)
    if total == 0:
        await callback.message.answer(f"😕 Товарів не знайдено.")
        await callback.answer()
        return
    
    total_pages = (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    page = max(0, min(page, total_pages - 1))
    start = page * ITEMS_PER_PAGE
    end = min(start + ITEMS_PER_PAGE, total)
    products_page = available[start:end]
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    
    for p in products_page:
        msg_id = p.get('message_id')
        text = p.get('text', '')
        price = extract_price(text)
        price_text = f" - {price} грн" if price > 0 else ""
        short_name = (text[:35] + "..") if len(text) > 35 else text
        short_name = short_name.replace("\n", " ").replace("_", " ").strip()
        
        # Кнопка з посиланням на товар
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text=f"📦 {short_name}{price_text}", url=f"https://t.me/c/{str(group_id)[4:]}/{msg_id}")
        ])
        
        # Рядок з кнопками дій
        action_buttons = []
        
        # Кнопка "В кошик" для всіх
        callback_data = f"add_{msg_id}_{size}_{price}"
        if len(callback_data) > 60:
            callback_data = f"add_{msg_id}_{size}"
        action_buttons.append(InlineKeyboardButton(text="🛒 В кошик", callback_data=callback_data))
        
        # Кнопка "Видалити" тільки для адмінів
        if callback.from_user.id in [ADMIN_ID, WOMAN_ADMIN_ID]:
            action_buttons.append(InlineKeyboardButton(text="❌ Видалити", callback_data=f"del_{msg_id}"))
        
        keyboard.inline_keyboard.append(action_buttons)
    
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Назад", callback_data=f"{prefix}_page_{page-1}_{size}_{gender}_{category if category else ''}_{season if season else ''}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперед ▶️", callback_data=f"{prefix}_page_{page+1}_{size}_{gender}_{category if category else ''}_{season if season else ''}"))
    if nav_buttons:
        keyboard.inline_keyboard.append(nav_buttons)
    
    back_btn = []
    if category:
        back_btn.append(InlineKeyboardButton(text="🔙 До категорій", callback_data="show_categories"))
    elif season:
        back_btn.append(InlineKeyboardButton(text="🔙 До сезонів", callback_data="show_categories"))
    else:
        back_btn.append(InlineKeyboardButton(text="🔙 До розмірів", callback_data="show_all_sizes"))
    back_btn.append(InlineKeyboardButton(text="🏠 Головне меню", callback_data="main_menu"))
    keyboard.inline_keyboard.append(back_btn)
    
    try:
        await callback.message.delete()
    except:
        pass
    
    header = f"✅ "
    if category:
        header += f"{category} • "
    elif season:
        header += f"{season} • "
    header += f"Розмір {size}"
    
    await callback.message.answer(
        f"{header}\n📄 Сторінка {page+1} з {total_pages}\n📦 Знайдено: {total} товарів",
        reply_markup=keyboard
    )
    await callback.answer()

# ========== ОБРОБКА ДОДАВАННЯ В КОШИК ==========
@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart_handler(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    product_id = int(parts[1])
    size = parts[2]
    price = float(parts[3]) if len(parts) > 3 and parts[3].replace('.', '').isdigit() else 0
    
    products = get_all_products()
    for p in products:
        if p.get('message_id') == product_id:
            product_name = p.get('text', 'Товар')[:50].replace("\n", " ").strip()
            message_id = p.get('message_id')
            product_gender = p.get('gender', 'чоловік')
            group_id = GROUPS.get(product_gender, GROUPS["чоловік"])
            add_to_cart(callback.from_user.id, product_id, message_id, group_id, product_name, size, price)
            break
    else:
        add_to_cart(callback.from_user.id, product_id, product_id, GROUPS["чоловік"], "Товар", size, price)
    
    await callback.answer("✅ Товар додано до кошика!", show_alert=True)

# ========== ПАГІНАЦІЯ ==========
@dp.callback_query(lambda c: c.data.startswith(("all_page_", "cat_page_", "season_page_")))
async def handle_pagination(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    prefix = parts[0]
    page = int(parts[2])
    size = parts[3]
    gender = parts[4]
    category = parts[5] if len(parts) > 5 and parts[5] else None
    season = parts[6] if len(parts) > 6 and parts[6] else None
    await show_products_list(callback, size, gender, category, season, page, prefix)

# ========== ОБРОБКА ПОСТІВ З ГРУП ==========
@dp.message()
async def catch_group_post(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in GROUPS.values():
        return
    
    gender = get_gender_by_chat_id(chat_id)
    full_text = (message.text or message.caption or "")
    
    if is_sold(full_text):
        logger.info(f"⏩ Продано: {message.message_id}")
        delete_product_from_sheet(message.message_id)
        return
    
    category = extract_category(full_text, gender)
    season = extract_season(full_text)
    
    # Якщо немає категорії, але є сезон - не додаємо (бо потрібна хоч якась категорія)
    if not category:
        logger.info(f"⏩ Немає категорії: {message.message_id}")
        return
    
    sizes = extract_sizes(full_text, category, gender)
    if not sizes:
        logger.info(f"⏩ Немає розмірів: {message.message_id}")
        return
    
    sizes_str = "," + ",".join(sizes) + ","
    
    # Перевіряємо чи є вже такий товар в Google Sheets
    products = get_all_products()
    exists = False
    for p in products:
        if p.get('message_id') == message.message_id:
            update_product_in_sheet(message.message_id, full_text, sizes_str, gender, category, season)
            exists = True
            break
    
    if not exists:
        add_product_to_sheet(message.message_id, full_text, sizes_str, gender, category, season)
    
    logger.info(f"✅ Збережено: {message.message_id} | Розм: {sizes} | Кат: {category} | Сезон: {season} | Стать: {gender}")

@dp.edited_message()
async def catch_edited_post(message: types.Message):
    chat_id = message.chat.id
    if chat_id not in GROUPS.values():
        return
    
    gender = get_gender_by_chat_id(chat_id)
    full_text = (message.text or message.caption or "")
    
    if is_sold(full_text):
        delete_product_from_sheet(message.message_id)
        logger.info(f"🗑️ Видалено (ПРОДАНО): {message.message_id}")
        return
    
    category = extract_category(full_text, gender)
    season = extract_season(full_text)
    
    if not category:
        delete_product_from_sheet(message.message_id)
        logger.info(f"🗑️ Видалено (немає категорії): {message.message_id}")
        return
    
    sizes = extract_sizes(full_text, category, gender)
    if not sizes:
        delete_product_from_sheet(message.message_id)
        logger.info(f"🗑️ Видалено (немає розмірів): {message.message_id}")
        return
    
    sizes_str = "," + ",".join(sizes) + ","
    update_product_in_sheet(message.message_id, full_text, sizes_str, gender, category, season)
    logger.info(f"🔄 Оновлено після редагування: {message.message_id}")

# ========== HTTP СЕРВЕР ==========
async def health_check(request):
    return web.Response(text="OK")

async def ping_self():
    while True:
        await asyncio.sleep(600)
        if KEEP_ALIVE_URL:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(KEEP_ALIVE_URL, timeout=10) as resp:
                        logger.info(f"✅ Самопінг: {resp.status}")
            except Exception as e:
                logger.error(f"❌ Помилка самопінгу: {e}")

async def start_http_server():
    app = web.Application()
    app.router.add_get("/health", health_check)
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 HTTP сервер на порту {PORT}")

async def main():
    await start_http_server()
    asyncio.create_task(ping_self())
    logger.info("🤖 Бот запущено!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
