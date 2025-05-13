from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from db.utils import get_target_channels, get_or_create_user, get_image_prompt, set_image_prompt, get_include_image, set_include_image
from bot.bot_instance import dp


class ImageFSM(StatesGroup):
    waiting_prompt = State()


def get_image_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Список каналов", callback_data="image_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])


async def handle_menu_images(query: CallbackQuery):
    await query.message.edit_text("🖼 Настройка изображений:", reply_markup=get_image_menu())
    await query.answer()


async def handle_image_list(query: CallbackQuery, user):
    channels = get_target_channels(user.id)
    if not channels:
        await query.message.edit_text("❌ Нет доступных каналов.", reply_markup=get_image_menu())
        await query.answer()
        return

    keyboard = [
        [InlineKeyboardButton(
            text=f"{ch.title or 'Без названия'} ({ch.chat_id})",
            callback_data=f"image_config_{ch.chat_id}"
        )] for ch in channels
    ]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_images")])
    await query.message.edit_text("Выберите канал:", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await query.answer()


async def handle_image_config(query: CallbackQuery | Message, user, data: str):
    chat_id = int(data.replace("image_config_", ""))
    prompt = get_image_prompt(chat_id, user.id)
    include = get_include_image(chat_id, user.id)

    title = next((ch.title for ch in get_target_channels(user.id) if ch.chat_id == chat_id), "Без названия")
    text = f"🖼 Настройки генерации для `{chat_id}` — *{title}*:\n\n"
    text += f"• Генерация: {'✅ ВКЛ' if include else '🚫 ВЫКЛ'}\n"
    text += f"• Промт: {prompt or 'ℹ️ Не задан'}"

    keyboard = [
        [InlineKeyboardButton(text="✏️ Изменить промт", callback_data=f"image_set_prompt_{chat_id}")],
        [InlineKeyboardButton(text="🔁 Вкл/выкл генерацию", callback_data=f"image_toggle_{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="image_list")]
    ]
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    if isinstance(query, CallbackQuery):
        await query.message.edit_text(text, reply_markup=markup, parse_mode="Markdown")
        await query.answer()
    else:
        await query.answer(text, reply_markup=markup, parse_mode="Markdown")


async def handle_image_prompt_set(query: CallbackQuery, state: FSMContext, data: str):
    chat_id = int(data.replace("image_set_prompt_", ""))
    await state.update_data(image_chat_id=chat_id)
    await state.set_state(ImageFSM.waiting_prompt)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"image_config_{chat_id}")]
    ])

    await query.message.edit_text(f"✏️ Введите новый промт для `{chat_id}`:", reply_markup=keyboard, parse_mode="Markdown")
    await query.answer()


@dp.message(ImageFSM.waiting_prompt)
async def process_image_prompt(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    data = await state.get_data()
    chat_id = data.get("image_chat_id")
    prompt = message.text.strip()

    if set_image_prompt(chat_id, user.id, prompt):
        await message.answer(f"✅ Промт установлен для `{chat_id}`.", parse_mode="Markdown")
        await handle_image_config(message, user, f"image_config_{chat_id}")
    else:
        await message.answer("⚠️ Не удалось сохранить промт.")
    await state.clear()


async def handle_image_toggle(query: CallbackQuery, user, data: str):
    chat_id = int(data.replace("image_toggle_", ""))
    current = get_include_image(chat_id, user.id)
    success = set_include_image(chat_id, user.id, not current)

    if success:
        await query.message.answer(f"🔁 Генерация {'включена' if not current else 'отключена'} для `{chat_id}`.", parse_mode="Markdown")
        await handle_image_config(query.message, user, f"image_config_{chat_id}")
    else:
        await query.message.answer("⚠️ Не удалось обновить настройку.")
    await query.answer()
