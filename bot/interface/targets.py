from aiogram.types import CallbackQuery, InlineKeyboardMarkup, \
    InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext
from db.utils import get_target_channels, remove_target_channel, \
    add_target_channel, get_or_create_user
from client.client_manager import get_user_client
from db.utils import fetch_channel_title
from aiogram.fsm.state import State, StatesGroup
from bot.bot_instance import dp


class TargetChannelSetup(StatesGroup):
    waiting_chat_id = State()


def get_target_channels_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="target_add")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data="target_remove")],
        [InlineKeyboardButton(text="📋 Список", callback_data="target_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])


async def handle_menu_targets(query: CallbackQuery):
    await query.message.edit_text("🎯 Работа с таргетными каналами:",
                                  reply_markup=get_target_channels_menu())
    await query.answer()


async def handle_target_list(query: CallbackQuery, user):
    channels = get_target_channels(user.id)
    if not channels:
        text = "❌ Нет таргетных каналов."
    else:
        text = "🎯 Таргетные каналы:\n" + "\n".join(
            f"• `{ch.chat_id}` — {ch.title or 'Без названия'}" for ch in
            channels
        )
    await query.message.edit_text(text,
                                  reply_markup=get_target_channels_menu(),
                                  parse_mode="Markdown")
    await query.answer()


async def handle_target_add(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text(
        "Введите ID таргетного канала:\n(Бот должен иметь туда доступ)",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад",
                                  callback_data="menu_targets")]
        ])
    )
    await state.set_state(TargetChannelSetup.waiting_chat_id)
    await query.answer()


async def handle_target_remove_menu(query: CallbackQuery, user):
    channels = get_target_channels(user.id)
    if not channels:
        await query.message.edit_text("❌ Нет каналов для удаления.",
                                      reply_markup=get_target_channels_menu())
        await query.answer()
        return

    keyboard = [
        [InlineKeyboardButton(
            text=f"{ch.title or 'Без названия'} ({ch.chat_id}) ❌",
            callback_data=f"remove_target_{ch.chat_id}"
        )] for ch in channels
    ]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад",
                                          callback_data="menu_targets")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await query.message.edit_text("Выберите канал для удаления:",
                                  reply_markup=markup)
    await query.answer()


async def handle_target_remove_by_id(query: CallbackQuery, user, data: str):
    chat_id = int(data.replace("remove_target_", ""))
    remove_target_channel(chat_id, user.id)
    await query.message.edit_text("✅ Канал удалён.",
                                  reply_markup=get_target_channels_menu())
    await query.answer()


async def handle_target_add_from_input(message, state: FSMContext, user):
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id.")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer("⚠️ Слушатель не активен.")
        await state.clear()
        return

    title = await fetch_channel_title(chat_id, client)
    if add_target_channel(chat_id, user.id, title=title):
        await message.answer(
            f"✅ Таргетный канал `{chat_id}` ({title}) добавлен.",
            reply_markup=get_target_channels_menu(), parse_mode="Markdown")
    else:
        await message.answer("⚠️ Такой канал уже существует.",
                             reply_markup=get_target_channels_menu(),
                             parse_mode="Markdown")
    await state.clear()


@dp.message(TargetChannelSetup.waiting_chat_id)
async def add_target_channel_fsm(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id.")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer("⚠️ Слушатель не активен.")
        await state.clear()
        return

    title = await fetch_channel_title(chat_id, client)

    if add_target_channel(chat_id, user.id, title=title):
        await message.answer(
            f"✅ Таргетный канал `{chat_id}` ({title}) добавлен.",
            reply_markup=get_target_channels_menu(), parse_mode="Markdown")
    else:
        await message.answer(f"⚠️ Такой канал уже есть.",
                             reply_markup=get_target_channels_menu(),
                             parse_mode="Markdown")

    await state.clear()
