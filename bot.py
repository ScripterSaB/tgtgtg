import os
import asyncio
import time
import hashlib
import hmac
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ---------- ТОКЕН (читаем из переменных окружения Render) ----------
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set! Add environment variable on Render.")

# ---------- НАСТРОЙКИ ----------
MAX_KEYS = 100
MAX_DAYS = 1000
AVAILABLE_DAYS = [30, 90, 180]

# ---------- СЕКРЕТ ----------
def get_secret():
    arr = [0x10, 0xb, 0x3, 0x19, 0x4f, 0x1d, 0xb7, 0xce, 0xdd, 0xfc, 0xf5, 0xc3,
           0xcd, 0x83, 0xff, 0xa6, 0xbc, 0x9d, 0xaf, 0xd2, 0xa4, 0x9d, 0x94, 0x89,
           0x3a, 0x70, 0x65, 0x56, 0x72, 0x75, 0x46, 0x47, 0x64, 0x20, 0x11, 0x62, 0x61]
    return ''.join(chr((arr[i] ^ (0x5b + i * 7)) & 0xff) for i in range(len(arr)))

SECRET = get_secret()

def generate_keys(count: int, days: int) -> list:
    now = int(time.time())
    base_expiry = now + days * 86400
    keys = []
    for i in range(min(count, MAX_KEYS)):
        expiry = base_expiry + i
        ts_str = str(expiry)
        if len(ts_str) != 10:
            ts_str = ts_str.zfill(10)
        data = ts_str + '1'
        signature = hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()[:16].upper()
        keys.append(ts_str + '1' + signature)
    return keys

# ---------- FSM ----------
class Form(StatesGroup):
    waiting_for_days = State()
    waiting_for_count = State()

# ---------- ТЕКСТЫ ----------
texts = {
    'ru': {
        'lang_choice': "🌐 Выберите язык / Choose language:",
        'welcome': "🇷🇺 Добро пожаловать! Я генерирую ключи для BSX.\n\nВыберите срок действия (дней) или нажмите кнопку:",
        'custom_days': f"📅 Введите количество дней (от 1 до {MAX_DAYS}):",
        'after_days': f"✅ Срок: {{}} дн.\nТеперь введите количество ключей (от 1 до {MAX_KEYS}):",
        'generating': "⏳ Генерирую {} ключ(ей) на {} дн...",
        'keys_result': "✅ Ваши ключи:\n<pre>{}</pre>",
        'copied_hint': "Скопируйте нужный ключ и активируйте в игре.",
        'error_days': f"❌ Ошибка: введите число от 1 до {MAX_DAYS}.",
        'error_count': f"❌ Ошибка: введите число от 1 до {MAX_KEYS}.",
        'error_generate': "❌ Ошибка генерации. Попробуйте позже.",
        'help_text': "/start — начать заново\n/help — эта справка",
        'custom_btn': "✏️ Своё значение"
    },
    'en': {
        'lang_choice': "🌐 Choose language / Выберите язык:",
        'welcome': "🇬🇧 Welcome! I generate keys for BSX.\n\nChoose validity period (days) or press button:",
        'custom_days': f"📅 Enter number of days (1 to {MAX_DAYS}):",
        'after_days': f"✅ Period: {{}} days.\nNow enter number of keys (1 to {MAX_KEYS}):",
        'generating': "⏳ Generating {} key(s) for {} days...",
        'keys_result': "✅ Your keys:\n<pre>{}</pre>",
        'copied_hint': "Copy the key and activate it in the game.",
        'error_days': f"❌ Error: enter a number from 1 to {MAX_DAYS}.",
        'error_count': f"❌ Error: enter a number from 1 to {MAX_KEYS}.",
        'error_generate': "❌ Generation error. Try again later.",
        'help_text': "/start — start over\n/help — this help",
        'custom_btn': "✏️ Custom value"
    }
}

# ---------- ИНИЦИАЛИЗАЦИЯ ----------
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
user_lang = {}

# ---------- КЛАВИАТУРЫ ----------
def lang_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")],
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en")]
    ])

def days_keyboard(lang):
    kb = []
    for d in AVAILABLE_DAYS:
        suffix = "дн" if lang == 'ru' else "days"
        kb.append([InlineKeyboardButton(text=f"{d} {suffix}", callback_data=f"days_{d}")])
    kb.append([InlineKeyboardButton(text=texts[lang]['custom_btn'], callback_data="days_custom")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# ---------- ХЕНДЛЕРЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(texts['ru']['lang_choice'], reply_markup=lang_keyboard())

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def process_lang(callback: types.CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    user_lang[callback.from_user.id] = lang
    await callback.message.edit_text(texts[lang]['welcome'], reply_markup=days_keyboard(lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("days_"))
async def process_days_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = callback.data.split("_")
    if parts[1] == "custom":
        await callback.message.edit_text(texts[lang]['custom_days'])
        await state.set_state(Form.waiting_for_days)
    else:
        days = int(parts[1])
        await state.update_data(days=days)
        msg = texts[lang]['after_days'].format(days)
        await callback.message.edit_text(msg)
        await state.set_state(Form.waiting_for_count)
    await callback.answer()

@dp.message(Form.waiting_for_days)
async def process_custom_days(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    try:
        days = int(message.text.strip())
        if days < 1 or days > MAX_DAYS:
            await message.answer(texts[lang]['error_days'])
            return
        await state.update_data(days=days)
        msg = texts[lang]['after_days'].format(days)
        await message.answer(msg)
        await state.set_state(Form.waiting_for_count)
    except ValueError:
        await message.answer(texts[lang]['error_days'])

@dp.message(Form.waiting_for_count)
async def process_count(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    try:
        count = int(message.text.strip())
        if count < 1 or count > MAX_KEYS:
            await message.answer(texts[lang]['error_count'])
            return
        data = await state.get_data()
        days = data.get('days')
        if not days:
            await message.answer(texts[lang]['error_days'])
            await state.clear()
            return
        await message.answer(texts[lang]['generating'].format(count, days))
        keys = generate_keys(count, days)
        if not keys:
            await message.answer(texts[lang]['error_generate'])
            return
        keys_text = "\n".join(keys)
        await message.answer(texts[lang]['keys_result'].format(keys_text), parse_mode="HTML")
        await message.answer(texts[lang]['copied_hint'])
        await state.clear()
    except ValueError:
        await message.answer(texts[lang]['error_count'])

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await message.answer(texts[lang]['help_text'])

@dp.message()
async def unknown(message: types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await message.answer("❓ " + ("Неизвестная команда. Используйте /start" if lang == 'ru' else "Unknown command. Use /start"))

# ---------- АВТОПЕРЕЗАПУСК ----------
async def main():
    while True:
        try:
            print("✅ Бот запущен и работает...")
            await dp.start_polling(bot)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("🔄 Перезапуск через 5 секунд...")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
