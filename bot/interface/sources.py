from aiogram.types import CallbackQuery, InlineKeyboardMarkup, \
    InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext

from client.client_manager import get_user_client
from db.utils import get_active_channels, add_channel, fetch_channel_title, \
    get_or_create_user
from client.listeners import remove_channel_listener, add_channel_listener
from db.utils import remove_channel_by_id
from aiogram.fsm.state import State, StatesGroup
from bot.bot_instance import dp


class SourceAddState(StatesGroup):
    waiting_for_chat_id = State()


def get_sources_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить канал",
                              callback_data="source_add")],
        [InlineKeyboardButton(text="❌ Удалить канал",
                              callback_data="source_remove")],
        [InlineKeyboardButton(text="📋 Список каналов",
                              callback_data="source_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")]
    ])


async def handle_menu_sources(query: CallbackQuery):
    await query.message.edit_text("📥 Источники каналов:",
                                  reply_markup=get_sources_menu())
    await query.answer()


async def handle_source_list(query: CallbackQuery, user):
    channels = get_active_channels(user.id)
    if not channels:
        text = "❌ Нет активных источников."
    else:
        text = "📋 Список источников:\n" + "\n".join(
            f"• `{ch.chat_id}` — {ch.title or 'Без названия'}" for ch in
            channels
        )
    await query.message.edit_text(text, reply_markup=get_sources_menu(),
                                  parse_mode="Markdown")
    await query.answer()


async def handle_source_add(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text(
        "Введите ID канала для добавления 📥\n\n"
        "Убедитесь, что вы уже добавили туда слушателя и он может читать сообщения.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад",
                                     callback_data="menu_sources"),
                InlineKeyboardButton(text="🏠 Главное меню",
                                     callback_data="menu_main")
            ]
        ])
    )
    await state.set_state(SourceAddState.waiting_for_chat_id)
    await query.answer()


async def handle_source_remove(query: CallbackQuery, user):
    channels = get_active_channels(user.id)
    if not channels:
        await query.message.edit_text("❌ Нет источников для удаления.",
                                      reply_markup=get_sources_menu())
        await query.answer()
        return

    keyboard = [
        [InlineKeyboardButton(
            text=f"{ch.title or 'Без названия'} ({ch.chat_id}) ❌",
            callback_data=f"remove_source_{ch.chat_id}"
        )] for ch in channels
    ]
    keyboard.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_sources")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await query.message.edit_text("❌ Выберите канал для удаления:",
                                  reply_markup=markup)
    await query.answer()


async def handle_source_delete_by_id(query: CallbackQuery, user, data: str):
    try:
        chat_id = int(data.replace("remove_source_", ""))
    except ValueError:
        await query.answer("⚠️ Неверный chat_id")
        return

    remove_channel_by_id(chat_id, user.id)
    await remove_channel_listener(chat_id)

    channels = get_active_channels(user.id)
    if not channels:
        await query.message.edit_text(
            "✅ Канал удалён.\n❌ Больше нет активных источников.",
            reply_markup=get_sources_menu()
        )
    else:
        keyboard = [
            [InlineKeyboardButton(
                text=f"{ch.title or 'Без названия'} ({ch.chat_id}) ❌",
                callback_data=f"remove_source_{ch.chat_id}"
            )] for ch in channels
        ]
        keyboard.append([InlineKeyboardButton(text="🔙 Назад",
                                              callback_data="menu_sources")])
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await query.message.edit_text("✅ Канал удалён.", reply_markup=markup)

    await query.answer()


@dp.message(SourceAddState.waiting_for_chat_id)
async def process_chat_id_input(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Неверный формат. Введите числовой ID канала.")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer(
            "⚠️ Слушатель не активен. Сначала установите слушателя")
        await state.clear()
        return

    try:
        me = await client.get_me()
        await client.get_permissions(chat_id, me.id)
    except Exception:
        await message.answer(
            "❌ Не удалось проверить права. Убедитесь, что слушатель в этом канале.")
        await state.clear()
        return

    title = await fetch_channel_title(chat_id, client)
    if add_channel(chat_id, user.id, title):
        await add_channel_listener(chat_id, client)
        await message.answer(
            f"✅ Канал `{chat_id}` ({title}) добавлен!",
            reply_markup=get_sources_menu(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"⚠️ Канал `{chat_id}` уже существует.",
            reply_markup=get_sources_menu(),
            parse_mode="Markdown"
        )

    await state.clear()
