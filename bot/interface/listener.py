from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, \
    InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from client.client_manager import start_user_client, get_user_client
from db.utils import get_or_create_user, get_telegram_account, \
    set_telegram_account
from bot.bot_instance import dp


class ListenerSetup(StatesGroup):
    waiting_api_id = State()
    waiting_api_hash = State()
    waiting_phone = State()
    waiting_code = State()


def get_listener_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Показать слушателя",
                              callback_data="listener_show")],
        [InlineKeyboardButton(text="➕ Установить слушателя",
                              callback_data="listener_set")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])


@dp.message(Command("set_listener"))
async def cmd_set_listener(message: Message):
    args = message.text.split(maxsplit=4)
    if len(args) < 4:
        await message.answer(
            "⚠️ Формат: /set_listener <api_id> <api_hash> <phone>")
        return
    print(1)
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    print(1)
    try:
        api_id = int(args[1])
        api_hash = args[2]
        phone = args[3]
    except Exception:
        await message.answer("⚠️ Неверный формат данных.")
        return
    print(1)
    set_telegram_account(user.id, api_id, api_hash, phone)
    print(1)
    try:
        result = await start_user_client(user.id)
        if result == 'awaiting_code':
            await message.answer(
                "📩 Код отправлен. Введите его командой:\n`/code <ваш_код>`",
                parse_mode="Markdown")
        else:
            await message.answer("✅ Слушатель авторизован и подключен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка авторизации слушателя: {e}")


@dp.message(Command("get_listener"))
async def cmd_get_listener(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    account = get_telegram_account(user.id)
    if not account:
        await message.answer("❌ Слушатель не настроен.")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer("⚠️ Слушатель неактивен. Выполните /set_listener.")
        return

    try:
        dialogs = await client.get_dialogs()
        channels = [
            dialog for dialog in dialogs
            if getattr(dialog.entity, "megagroup", False)
               or getattr(dialog.entity, "broadcast", False)
        ]

        if not channels:
            await message.answer("ℹ️ Слушатель не состоит ни в одном канале.")
            return

        text = (
                f"👤 Текущий слушатель:\n"
                f"• ID: {user.telegram_id}\n"
                f"• Телефон: {account.phone}\n"
                f"📡 Каналы:\n"
                + "\n".join(
            f"• `{ch.entity.id}` — {ch.name}" for ch in channels)
        )

        await message.answer(text)

    except Exception as e:
        await message.answer(f"❌ Ошибка при получении каналов: {e}")


@dp.message(Command("code"))
async def cmd_code(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    code = message.text.split(maxsplit=1)[1] if len(
        message.text.split()) > 1 else None

    if not code:
        await message.answer("⚠️ Введите код, полученный в Telegram.")
        return

    try:
        result = await start_user_client(user.id, code=code)
        if result == 'ok':
            await message.answer("✅ Авторизация завершена и клиент запущен.")
        else:
            await message.answer("⚠️ Не удалось завершить авторизацию.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при вводе кода: {e}")


@dp.message(ListenerSetup.waiting_api_id)
async def set_api_id(message: Message, state: FSMContext):
    try:
        api_id = int(message.text.strip())
        await state.update_data(api_id=api_id)
        await state.set_state(ListenerSetup.waiting_api_hash)
        await message.answer("✅ API ID сохранён.\nТеперь введите `api_hash`:",
                             parse_mode="Markdown")
    except ValueError:
        await message.answer("⚠️ Неверный формат API ID. Введите число.")


@dp.message(ListenerSetup.waiting_api_hash)
async def set_api_hash(message: Message, state: FSMContext):
    await state.update_data(api_hash=message.text.strip())
    await state.set_state(ListenerSetup.waiting_phone)
    await message.answer(
        "📞 Отлично. Теперь введите номер телефона в формате +7...",
        parse_mode="Markdown")


@dp.message(ListenerSetup.waiting_phone)
async def set_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")

    set_telegram_account(user.id, api_id, api_hash, phone)

    try:
        result = await start_user_client(user.id)
        if result == 'awaiting_code':
            await message.answer(
                "📩 Код отправлен в Telegram. Введите его сюда:")
            await state.set_state(ListenerSetup.waiting_code)
        else:
            await message.answer("✅ Слушатель авторизован и подключён.",
                                 reply_markup=get_listener_menu())
            await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка авторизации: {e}",
                             reply_markup=get_listener_menu())
        await state.clear()


@dp.message(ListenerSetup.waiting_code)
async def set_auth_code(message: Message, state: FSMContext):
    code = message.text.strip()
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    try:
        result = await start_user_client(user.id, code=code)
        if result == 'ok':
            await message.answer(
                "✅ Авторизация завершена. Слушатель подключён.",
                reply_markup=get_listener_menu())
        else:
            await message.answer("⚠️ Что-то пошло не так. Попробуйте заново.",
                                 reply_markup=get_listener_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка входа по коду: {e}",
                             reply_markup=get_listener_menu())

    await state.clear()


async def show_listener_menu(query: CallbackQuery):
    await query.message.edit_text(
        "🔐 Настройка слушателя — выберите действие:",
        reply_markup=get_listener_menu()
    )
    await query.answer()


async def handle_listener_set(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text(
        "🛠 Давайте настроим слушателя.\nВведите ваш `api_id`:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад",
                                  callback_data="menu_listener")]
        ]),
        parse_mode="Markdown"
    )
    await state.set_state(ListenerSetup.waiting_api_id)
    await query.answer()


async def handle_listener_show(query: CallbackQuery, user):
    account = get_telegram_account(user.id)
    client = get_user_client(user.id)

    if not account:
        await query.message.edit_text("❌ Слушатель не настроен.",
                                      reply_markup=get_listener_menu())
        await query.answer()
        return

    if not client:
        await query.message.edit_text(
            "⚠️ Слушатель неактивен. Выполните настройку заново.",
            reply_markup=get_listener_menu())
        await query.answer()
        return

    try:
        dialogs = await client.get_dialogs()
        channels = [
            dialog for dialog in dialogs
            if getattr(dialog.entity, "megagroup", False) or getattr(
                dialog.entity, "broadcast", False)
        ]

        text = (
                f"👤 Текущий слушатель:\n"
                f"• Телефон: `{account.phone}`\n"
                f"📡 Каналы:\n"
                + "\n".join(
            f"• `{ch.entity.id}` — {ch.name}" for ch in channels)
        )
        await query.message.edit_text(text,
                                      reply_markup=get_listener_menu(),
                                      parse_mode="Markdown")

    except Exception as e:
        await query.message.edit_text(f"❌ Ошибка при получении данных: {e}",
                                      reply_markup=get_listener_menu())
    await query.answer()
