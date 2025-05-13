from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db.utils import get_target_channels, get_or_create_user, get_rewrite_prompt, set_rewrite_prompt
from bot.bot_instance import dp

class RewriteFSM(StatesGroup):
    waiting_channel_id = State()
    waiting_prompt = State()


def get_rewrite_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список каналов", callback_data="rewrite_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])


async def handle_menu_rewrite(query: CallbackQuery):
    await query.message.edit_text("✏️ Настройка рерайта:", reply_markup=get_rewrite_menu())
    await query.answer()


async def handle_rewrite_list(query: CallbackQuery, user):
    channels = get_target_channels(user.id)
    if not channels:
        await query.message.edit_text("❌ Нет доступных каналов.", reply_markup=get_rewrite_menu())
        await query.answer()
        return

    keyboard = [
        [InlineKeyboardButton(
            text=f"{ch.title or 'Без названия'} ({ch.chat_id})",
            callback_data=f"rewrite_config_{ch.chat_id}"
        )] for ch in channels
    ]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_rewrite")])
    await query.message.edit_text("Выберите канал:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await query.answer()


async def handle_rewrite_config(query: CallbackQuery | Message, user, data: str):
    print("handle_rewrite_config")
    chat_id = int(data.replace("rewrite_config_", ""))
    prompt = get_rewrite_prompt(chat_id, user.id)

    channel = next(
        (ch for ch in get_target_channels(user.id) if ch.chat_id == chat_id),
        None)
    title = channel.title if channel and channel.title else "Без названия"
    text = f"📜 Текущий промт для `{chat_id}` — *{title}*:\n\n"
    text += prompt if prompt else "ℹ️ Не задан."

    keyboard = [
        [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"rewrite_set_{chat_id}")],
        [InlineKeyboardButton(text="🧹 Очистить", callback_data=f"rewrite_clear_{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="rewrite_list")]
    ]

    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if isinstance(query, CallbackQuery):
        await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
        await query.answer()
    else:
        await query.answer(text, reply_markup=markup, parse_mode="Markdown")



async def handle_rewrite_set(query: CallbackQuery, state: FSMContext, data: str):
    chat_id = int(data.replace("rewrite_set_", ""))
    await state.update_data(chat_id=chat_id)
    await state.set_state(RewriteFSM.waiting_prompt)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"rewrite_config_{chat_id}")]
    ])

    await query.message.edit_text(
        f"✏️ Введите новый промт для канала `{chat_id}`:",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    await query.answer()


@dp.message(RewriteFSM.waiting_prompt)
async def process_new_prompt(message: Message, state: FSMContext):
    print("process_new_prompt")
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    data = await state.get_data()
    chat_id = data.get("chat_id")
    prompt = message.text.strip()

    if set_rewrite_prompt(chat_id, user.id, prompt):
        # 1. Уведомление об успешной установке
        await message.answer(f"✅ Промт установлен для канала `{chat_id}`.", parse_mode="Markdown")

        # 2. Отправка блока кнопок
        await handle_rewrite_config(message, user, f"rewrite_config_{chat_id}")
    else:
        await message.answer("⚠️ Не удалось сохранить промт.")

    await state.clear()


async def handle_rewrite_clear(query: CallbackQuery, user, data: str):
    chat_id = int(data.replace("rewrite_clear_", ""))
    set_rewrite_prompt(chat_id, user.id, "")

    # 1. Отправляем сообщение об очистке
    await query.message.answer(
        f"🧹 Промт для канала `{chat_id}` очищен.",
        parse_mode="Markdown"
    )

    # 2. Отправляем новый блок с кнопками
    await handle_rewrite_config(query.message, user, f"rewrite_config_{chat_id}")

    await query.answer()