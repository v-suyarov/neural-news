from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, \
    InlineKeyboardButton, Message
from aiogram.fsm.context import FSMContext

from bot.bot_instance import dp
from db.utils import (
    get_all_tags, get_target_channels,
    get_tags_for_target_channel, remove_tag_from_target_channel,
    get_or_create_user, add_tag_to_target_channel
)


class TagManagement(StatesGroup):
    waiting_channel_id_for_add = State()
    waiting_tag_name_for_add = State()
    waiting_channel_id_for_remove = State()
    waiting_tag_name_for_remove = State()
    waiting_channel_id_for_list = State()
    waiting_tag_name_to_add = State()
    waiting_tag_name_to_remove = State()


def get_tags_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Все теги", callback_data="tags_all")],
        [InlineKeyboardButton(text="📦 Теги канала",
                              callback_data="tags_of_channel")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])


async def handle_menu_tags(query: CallbackQuery):
    await query.message.edit_text("🏷 Работа с тегами:",
                                  reply_markup=get_tags_menu())
    await query.answer()


async def handle_tags_all(query: CallbackQuery):
    tags = get_all_tags()
    if not tags:
        text = "❌ Нет тегов."
    else:
        text = "🏷 Все доступные теги:\n" + "\n".join(
            f"• {t.name}" for t in tags)
    await query.message.edit_text(text, reply_markup=get_tags_menu())
    await query.answer()


async def handle_tags_of_channel(query: CallbackQuery, user):
    channels = get_target_channels(user.id)
    if not channels:
        current_text = query.message.text or ""
        new_text = "❌ Нет доступных каналов."
        if current_text.strip() != new_text.strip():
            await query.message.edit_text(new_text,
                                          reply_markup=get_tags_menu())
        else:
            # Если текст тот же — просто обновим reply_markup (или проигнорируем)
            await query.answer("❌ Нет доступных каналов.")
        return

    keyboard = [
        [InlineKeyboardButton(
            text=f"{ch.title or 'Без названия'} ({ch.chat_id})",
            callback_data=f"show_tags_{ch.chat_id}"
        )] for ch in channels
    ]
    keyboard.append(
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_tags")])

    await query.message.edit_text("Выберите канал:",
                                  reply_markup=InlineKeyboardMarkup(
                                      inline_keyboard=keyboard))
    await query.answer()


async def handle_tags_show_channel(query: CallbackQuery, user, data: str):
    try:
        chat_id = int(data.replace("show_tags_", ""))
    except ValueError:
        await query.answer("⚠️ Неверный chat_id.")
        return

    tags = get_tags_for_target_channel(chat_id, user.id)
    tags_text = "\n".join(
        f"• {tag.name}" for tag in tags) if tags else "Нет тегов."

    text = (
        f"🏷 Теги канала `{chat_id}`:\n"
        f"{tags_text}\n\n"
        "Выберите действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить тег",
                              callback_data=f"tag_add_{chat_id}")],
        [InlineKeyboardButton(text="❌ Удалить тег",
                              callback_data=f"tag_remove_{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад",
                              callback_data="tags_of_channel")]
    ])

    await query.message.edit_text(text, reply_markup=keyboard,
                                  parse_mode="Markdown")
    await query.answer()


async def handle_tag_add_start(query: CallbackQuery, state: FSMContext,
                               data: str):
    chat_id = int(data.replace("tag_add_", ""))
    await state.update_data(tag_op_chat_id=chat_id)

    telegram_id = query.from_user.id
    user = get_or_create_user(telegram_id)

    # Получаем уже добавленные теги
    existing_tags = get_tags_for_target_channel(chat_id, user.id)
    existing_tag_ids = {tag.id for tag in existing_tags}

    # Получаем все теги и фильтруем
    all_tags = get_all_tags()
    available_tags = [tag for tag in all_tags if tag.id not in existing_tag_ids]

    if not available_tags:
        await query.message.edit_text(
            "✅ У канала уже есть все доступные теги.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад",
                                      callback_data=f"show_tags_{chat_id}")]
            ])
        )
        await query.answer()
        return

    keyboard = [
        [InlineKeyboardButton(text=tag.name,
                              callback_data=f"tag_pick_{chat_id}_{tag.id}")]
        for tag in available_tags
    ]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад",
                                          callback_data=f"show_tags_{chat_id}")])

    await query.message.edit_text(
        f"Выберите тег для добавления в канал `{chat_id}`:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await query.answer()


async def handle_tag_pick(query: CallbackQuery, user, data: str):
    try:
        chat_id_str, tag_id_str = data.replace("tag_pick_", "").split("_")
        chat_id = int(chat_id_str)
        tag_id = int(tag_id_str)
    except Exception:
        await query.message.answer("⚠️ Неверный формат данных.")
        await query.answer()
        return

    from db.session import Session
    from db.models import TargetChannel, TargetChannelTag, Tag

    with Session() as session:
        target = session.query(TargetChannel).filter_by(
            chat_id=chat_id, user_id=user.id
        ).first()
        tag = session.query(Tag).filter_by(id=tag_id).first()

        if not target or not tag:
            await query.message.answer("❌ Канал или тег не найден.")
            return

        exists = session.query(TargetChannelTag).filter_by(
            target_channel_id=target.id, tag_id=tag.id
        ).first()
        if exists:
            await query.message.answer("⚠️ Тег уже добавлен.")
            await show_channel_tags(chat_id, user, query.message)
            return

        # Сохраняем имя до выхода из сессии
        tag_name = tag.name

        session.add(TargetChannelTag(target_channel_id=target.id, tag_id=tag.id))
        session.commit()

    # 1. Сообщение об успешном добавлении
    await query.message.answer(
        f"✅ Тег `{tag_name}` добавлен к каналу `{chat_id}`.",
        parse_mode="Markdown"
    )

    # 2. Новый блок управления тегами
    await show_channel_tags(chat_id, user, query.message)

    await query.answer()




async def handle_tag_remove_start(query: CallbackQuery, user, data: str):
    chat_id = int(data.replace("tag_remove_", ""))
    tags = get_tags_for_target_channel(chat_id, user.id)

    if not tags:
        await query.message.edit_text("❌ У канала нет тегов.",
                                      reply_markup=get_tags_menu())
        await query.answer()
        return

    keyboard = [
        [InlineKeyboardButton(
            text=f"{tag.name} ❌",
            callback_data=f"tag_delete_{chat_id}_{tag.name}"
        )] for tag in tags
    ]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад",
                                          callback_data=f"show_tags_{chat_id}")])

    await query.message.edit_text(
        f"Выберите тег для удаления из канала `{chat_id}`:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard),
        parse_mode="Markdown"
    )
    await query.answer()


async def handle_tag_delete(query: CallbackQuery, user, data: str):
    try:
        chat_id_str, tag_name = data[len("tag_delete_"):].split("_", 1)
        chat_id = int(chat_id_str)
    except Exception:
        await query.message.answer("⚠️ Ошибка разбора callback.")
        await query.answer()
        return

    if remove_tag_from_target_channel(chat_id, user.id, tag_name):
        # 1. Отправляем сообщение об удалении
        await query.message.answer(
            f"🗑 Тег `{tag_name}` удалён у канала `{chat_id}`.",
            parse_mode="Markdown"
        )

        # 2. Генерируем блок управления тегами как новое сообщение
        await show_channel_tags(chat_id, user, query.message)
    else:
        await query.message.answer("⚠️ Не удалось удалить тег.")

    await query.answer()


async def handle_tags_add_manual(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text(
        "Введите ID канала, к которому вы хотите добавить тег:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад",
                                  callback_data="menu_tags")]
        ]))
    await state.set_state(TagManagement.waiting_channel_id_for_add)
    await query.answer()


async def handle_tags_remove_manual(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text(
        "Введите ID канала, у которого вы хотите удалить тег:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад",
                                  callback_data="menu_tags")]
        ]))
    await state.set_state(TagManagement.waiting_channel_id_for_remove)
    await query.answer()


@dp.message(TagManagement.waiting_channel_id_for_list)
async def handle_tag_list(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Неверный chat_id.")
        return

    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    tags = get_tags_for_target_channel(chat_id, user.id)
    if not tags:
        text = "❌ У канала нет тегов."
    else:
        text = "🏷 Теги канала:\n" + "\n".join(f"• {t.name}" for t in tags)
    print(1)
    await show_channel_tags(chat_id, user, message)
    await state.clear()


@dp.message(TagManagement.waiting_channel_id_for_add)
async def handle_add_tag_channel_id(message: Message, state: FSMContext):
    try:
        chat_id = int(message.text.strip())
        await state.update_data(add_tag_chat_id=chat_id)
        await state.set_state(TagManagement.waiting_tag_name_for_add)
        await message.answer("Введите имя тега:")
    except ValueError:
        await message.answer("⚠️ Неверный chat_id.")


@dp.message(TagManagement.waiting_tag_name_to_remove)
async def handle_remove_tag(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("tag_op_chat_id")

    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    tag_name = message.text.strip()
    if remove_tag_from_target_channel(chat_id, user.id, tag_name):
        await message.answer(
            f"🗑 Тег `{tag_name}` удалён у канала `{chat_id}`.",
            parse_mode="Markdown"
        )
        await show_channel_tags(chat_id, user, message)
    else:
        await message.answer("⚠️ Не удалось удалить тег.")
    await state.clear()


async def show_channel_tags(chat_id: int, user, message_or_query):
    tags = get_tags_for_target_channel(chat_id, user.id)
    tags_text = "\n".join(
        f"• {tag.name}" for tag in tags) if tags else "Нет тегов."

    text = (
        f"🏷 Теги канала `{chat_id}`:\n"
        f"{tags_text}\n\n"
        "Выберите действие:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить тег",
                              callback_data=f"tag_add_{chat_id}")],
        [InlineKeyboardButton(text="❌ Удалить тег",
                              callback_data=f"tag_remove_{chat_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="tags_of_channel")]
    ])

    if isinstance(message_or_query, CallbackQuery):
        await message_or_query.message.edit_text(text, reply_markup=keyboard,
                                                 parse_mode="Markdown")
    else:
        await message_or_query.answer(text, reply_markup=keyboard,
                                      parse_mode="Markdown")
