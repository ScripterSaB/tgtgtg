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

# ---------- ТОКЕН (ТОЛЬКО ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ) ----------
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

def check_key_valid(key: str) -> dict:
    if len(key) != 27:
        return {'valid': False, 'reason': 'Неверная длина (27 символов)'}
    try:
        ts_str = key[:10]
        flag = key[10:11]
        signature = key[11:]
        timestamp = int(ts_str)
        now = int(time.time())
        if timestamp < now:
            return {'valid': False, 'reason': f'Ключ истёк (истёк {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))})'}
        if flag != '1':
            return {'valid': False, 'reason': 'Не премиум ключ'}
        data = ts_str + flag
        expected_sig = hmac.new(SECRET.encode(), data.encode(), hashlib.sha256).hexdigest()[:16].upper()
        if signature != expected_sig:
            return {'valid': False, 'reason': 'Неверная подпись'}
        return {'valid': True, 'reason': f'✅ Ключ действителен до {time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))}'}
    except:
        return {'valid': False, 'reason': 'Неверный формат ключа'}

# ---------- FSM ----------
class Form(StatesGroup):
    waiting_for_days = State()
    waiting_for_count = State()
    waiting_for_check_key = State()

# ---------- ТЕКСТЫ ----------
texts = {
    'ru': {
        'main_menu': "🏠 Главное меню\n\nВыберите действие:",
        'gen_key': "🔑 Сгенерировать ключ",
        'check_key': "✅ Проверить ключ",
        'settings': "⚙️ Настройки",
        'back': "🔙 Назад",
        'lang_ru': "🇷🇺 Русский",
        'lang_en': "🇬🇧 English",
        'lang_changed': "🌐 Язык изменён на русский",
        'choose_days': "📅 Выберите срок действия (дней) или нажмите кнопку:",
        'custom_days': f"📅 Введите количество дней (от 1 до {MAX_DAYS}):",
        'enter_count': f"✅ Срок: {{}} дн.\nТеперь введите количество ключей (от 1 до {MAX_KEYS}):",
        'generating': "⏳ Генерирую {} ключ(ей) на {} дн...",
        'keys_result': "✅ Ваши ключи:\n<pre>{}</pre>",
        'copied_hint': "Скопируйте нужный ключ",
        'error_days': f"❌ Ошибка: введите число от 1 до {MAX_DAYS}.",
        'error_count': f"❌ Ошибка: введите число от 1 до {MAX_KEYS}.",
        'error_generate': "❌ Ошибка генерации",
        'help_text': "/start — главное меню",
        'custom_btn': "✏️ Своё значение",
        'enter_key_to_check': "🔍 Введите ключ для проверки (27 символов):",
        'check_result': "{}\n\n{}",
        'check_again': "🔍 Проверить другой",
        'settings_menu': "⚙️ Настройки\n\nВыберите язык:"
    },
    'en': {
        'main_menu': "🏠 Main menu\n\nChoose action:",
        'gen_key': "🔑 Generate key",
        'check_key': "✅ Check key",
        'settings': "⚙️ Settings",
        'back': "🔙 Back",
        'lang_ru': "🇷🇺 Russian",
        'lang_en': "🇬🇧 English",
        'lang_changed': "🌐 Language changed to English",
        'choose_days': "📅 Choose validity period (days) or press button:",
        'custom_days': f"📅 Enter number of days (1 to {MAX_DAYS}):",
        'enter_count': f"✅ Period: {{}} days.\nNow enter number of keys (1 to {MAX_KEYS}):",
        'generating': "⏳ Generating {} key(s) for {} days...",
        'keys_result': "✅ Your keys:\n<pre>{}</pre>",
        'copied_hint': "Copy the key you need",
        'error_days': f"❌ Error: enter a number from 1 to {MAX_DAYS}.",
        'error_count': f"❌ Error: enter a number from 1 to {MAX_KEYS}.",
        'error_generate': "❌ Generation error",
        'help_text': "/start — main menu",
        'custom_btn': "✏️ Custom value",
        'enter_key_to_check': "🔍 Enter key to check (27 characters):",
        'check_result': "{}\n\n{}",
        'check_again': "🔍 Check another",
        'settings_menu': "⚙️ Settings\n\nChoose language:"
    }
}

# ---------- ИНИЦИАЛИЗАЦИЯ ----------
storage = MemoryStorage()
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=storage)
user_lang = {}

# ---------- КЛАВИАТУРЫ ----------
def main_menu(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts[lang]['gen_key'], callback_data="gen_key")],
        [InlineKeyboardButton(text=texts[lang]['check_key'], callback_data="check_key")],
        [InlineKeyboardButton(text=texts[lang]['settings'], callback_data="settings")]
    ])

def days_keyboard(lang):
    kb = []
    for d in AVAILABLE_DAYS:
        suffix = "дн" if lang == 'ru' else "days"
        kb.append([InlineKeyboardButton(text=f"{d} {suffix}", callback_data=f"days_{d}")])
    kb.append([InlineKeyboardButton(text=texts[lang]['custom_btn'], callback_data="days_custom")])
    kb.append([InlineKeyboardButton(text=texts[lang]['back'], callback_data="back_to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def settings_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts[lang]['lang_ru'], callback_data="lang_ru")],
        [InlineKeyboardButton(text=texts[lang]['lang_en'], callback_data="lang_en")],
        [InlineKeyboardButton(text=texts[lang]['back'], callback_data="back_to_menu")]
    ])

def after_check_keyboard(lang):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=texts[lang]['check_again'], callback_data="check_key")],
        [InlineKeyboardButton(text=texts[lang]['back'], callback_data="back_to_menu")]
    ])

# ---------- ХЕНДЛЕРЫ ----------
@dp.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await message.answer(texts[lang]['main_menu'], reply_markup=main_menu(lang))

@dp.callback_query(lambda c: c.data == "back_to_menu")
async def back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await callback.message.edit_text(texts[lang]['main_menu'], reply_markup=main_menu(lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "settings")
async def settings_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await callback.message.edit_text(texts[lang]['settings_menu'], reply_markup=settings_keyboard(lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("lang_"))
async def change_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_lang[callback.from_user.id] = lang
    await callback.message.edit_text(texts[lang]['lang_changed'], reply_markup=main_menu(lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data == "gen_key")
async def gen_key_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await callback.message.edit_text(texts[lang]['choose_days'], reply_markup=days_keyboard(lang))
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("days_"))
async def process_days(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    parts = callback.data.split("_")
    if parts[1] == "custom":
        await callback.message.edit_text(texts[lang]['custom_days'])
        await state.set_state(Form.waiting_for_days)
    else:
        days = int(parts[1])
        await state.update_data(days=days)
        msg = texts[lang]['enter_count'].format(days)
        await callback.message.edit_text(msg)
        await state.set_state(Form.waiting_for_count)
    await callback.answer()

@dp.message(Form.waiting_for_days)
async def custom_days(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    try:
        days = int(message.text.strip())
        if days < 1 or days > MAX_DAYS:
            await message.answer(texts[lang]['error_days'])
            return
        await state.update_data(days=days)
        msg = texts[lang]['enter_count'].format(days)
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
        await message.answer(texts[lang]['main_menu'], reply_markup=main_menu(lang))
    except ValueError:
        await message.answer(texts[lang]['error_count'])

@dp.callback_query(lambda c: c.data == "check_key")
async def check_key_start(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await callback.message.edit_text(texts[lang]['enter_key_to_check'])
    await state.set_state(Form.waiting_for_check_key)
    await callback.answer()

@dp.message(Form.waiting_for_check_key)
async def check_key_process(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    key = message.text.strip().upper()
    result = check_key_valid(key)
    status = "✅ ДЕЙСТВИТЕЛЕН" if result['valid'] else "❌ НЕДЕЙСТВИТЕЛЕН"
    text = texts[lang]['check_result'].format(status, result['reason'])
    await message.answer(text, reply_markup=after_check_keyboard(lang))
    await state.clear()

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await message.answer(texts[lang]['help_text'])

@dp.message()
async def unknown(message: types.Message):
    user_id = message.from_user.id
    lang = user_lang.get(user_id, 'ru')
    await message.answer("❓ " + ("Используйте /start" if lang == 'ru' else "Use /start"))

# ---------- ЗАПУСК ----------
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
