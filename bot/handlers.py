from aiogram.filters import Command
from aiogram.types import Message
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError, \
    ChannelInvalidError
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from client.client_manager import get_user_client
from client.client_manager import start_user_client
from bot.bot_instance import dp
from db.utils import add_channel, remove_channel_by_id, get_active_channels, \
    fetch_channel_title, remove_tag_from_target_channel, \
    add_tag_to_target_channel, get_target_channels, remove_target_channel, \
    add_target_channel, get_tags_for_target_channel, get_all_tags, \
    get_or_create_user, get_rewrite_prompt, set_rewrite_prompt, \
    set_telegram_account, get_telegram_account, get_user, set_include_image, \
    get_include_image, set_image_prompt, get_image_prompt
from client.listeners import add_channel_listener, remove_channel_listener

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery
from bot.interface.listener import (
    show_listener_menu, handle_listener_set, handle_listener_show
)
from bot.interface.base import (
    show_main_menu, get_main_menu
)
from bot.interface.sources import (
    get_sources_menu, handle_menu_sources, handle_source_list,
    handle_source_add, handle_source_remove, handle_source_delete_by_id,
    SourceAddState
)


class TargetChannelSetup(StatesGroup):
    waiting_chat_id = State()


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


def get_target_channels_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить", callback_data="target_add")],
        [InlineKeyboardButton(text="❌ Удалить", callback_data="target_remove")],
        [InlineKeyboardButton(text="📋 Список", callback_data="target_list")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])


# Главное меню


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🤖 Выберите действие:",
        reply_markup=get_main_menu()
    )


@dp.callback_query()
async def handle_callback(query: CallbackQuery, state: FSMContext):
    data = query.data
    telegram_id = query.from_user.id
    user = get_or_create_user(telegram_id)
    print(data)

    if data == "menu_main":
        await show_main_menu(query)

    elif data == "menu_sources":
        await handle_menu_sources(query)
    elif data == "source_list":
        await handle_source_list(query, user)
    elif data == "source_add":
        await handle_source_add(query, state)
    elif data == "source_remove":
        await handle_source_remove(query, user)
    elif data.startswith("remove_source_"):
        await handle_source_delete_by_id(query, user, data)

    elif data == "menu_listener":
        await show_listener_menu(query)
    elif data == "listener_set":
        await handle_listener_set(query, state)
    elif data == "listener_show":
        await handle_listener_show(query, user)




    elif data == "menu_targets":
        await query.message.edit_text("🎯 Работа с таргетными каналами:",
                                      reply_markup=get_target_channels_menu())
        await query.answer()

    elif data == "target_list":
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

    elif data == "target_add":
        await query.message.edit_text(
            "Введите ID таргетного канала:\n(Бот должен иметь туда доступ)",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад",
                                      callback_data="menu_targets")]
            ])
        )
        await state.set_state(TargetChannelSetup.waiting_chat_id)
        await query.answer()

    elif data == "target_remove":
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

    elif data.startswith("remove_target_"):
        chat_id = int(data.replace("remove_target_", ""))
        remove_target_channel(chat_id, user.id)
        await query.message.edit_text("✅ Канал удалён.",
                                      reply_markup=get_target_channels_menu())
        await query.answer()

    elif data == "menu_tags":
        await query.message.edit_text("🏷 Работа с тегами:",
                                      reply_markup=get_tags_menu())
        await query.answer()

    elif data == "tags_all":
        tags = get_all_tags()
        if not tags:
            text = "❌ Нет тегов."
        else:
            text = "🏷 Все доступные теги:\n" + "\n".join(
                f"• {t.name}" for t in tags)
        await query.message.edit_text(text, reply_markup=get_tags_menu())
        await query.answer()

    elif data == "tags_of_channel":
        channels = get_target_channels(user.id)
        if not channels:
            await query.message.edit_text("❌ Нет доступных каналов.",
                                          reply_markup=get_tags_menu())
            await query.answer()
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
    elif data.startswith("tag_add_"):
        chat_id = int(data.replace("tag_add_", ""))
        await state.update_data(tag_op_chat_id=chat_id)
        await state.set_state(TagManagement.waiting_tag_name_to_add)
        await query.message.edit_text(
            f"Введите имя тега, который хотите добавить в канал `{chat_id}`:",
            parse_mode="Markdown")
        await query.answer()
    elif data.startswith("tag_delete_"):
        payload = data[len("tag_delete_"):]  # "123456789_Спорт"
        try:
            chat_id_str, tag_name = payload.split("_", 1)
            chat_id = int(chat_id_str)
        except Exception:
            await query.message.answer("⚠️ Ошибка разбора callback.")
            await query.answer()
            return

        telegram_id = query.from_user.id
        user = get_or_create_user(telegram_id)

        if remove_tag_from_target_channel(chat_id, user.id, tag_name):
            await query.message.delete()  # 🔥 удалить старый блок с кнопками
            await query.message.answer(
                f"🗑 Тег `{tag_name}` удалён у канала `{chat_id}`.",
                parse_mode="Markdown"
            )
        else:
            await query.message.delete()
            await query.message.answer("⚠️ Не удалось удалить тег.")

        # отправить новый блок с кнопками (в виде обычного сообщения)
        await show_channel_tags(chat_id, user, message_or_query=query.message)
    elif data.startswith("tag_remove_"):
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
    elif data.startswith("show_tags_"):
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
    elif data == "tags_add":
        await query.message.edit_text(
            "Введите ID канала, к которому вы хотите добавить тег:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад",
                                      callback_data="menu_tags")]
            ]))
        await state.set_state(TagManagement.waiting_channel_id_for_add)
        await query.answer()

    elif data == "tags_remove":
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


@dp.message(Command("add_channel"))
async def cmd_add_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer(
            "⚠️ Вы ещё не авторизованы. Сначала выполните /auth.")
        return

    try:
        me = await client.get_me()
        await client.get_permissions(chat_id, me.id)
    except Exception as e:
        await message.answer(
            f"❌ Не удалось добавить канал. "
            f"Убедитесь, что прослушиватель состоит в нем")
        return

    title = await fetch_channel_title(chat_id, client)

    if add_channel(chat_id, user.id, title=title):
        await add_channel_listener(chat_id, client)
        await message.answer(f"✅ Канал {chat_id} добавлен.")
    else:
        await message.answer(f"⚠️ Канал {chat_id} уже существует.")


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


@dp.message(TagManagement.waiting_tag_name_to_add)
async def handle_add_tag(message: Message, state: FSMContext):
    data = await state.get_data()
    chat_id = data.get("tag_op_chat_id")

    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    tag_name = message.text.strip()
    if add_tag_to_target_channel(chat_id, user.id, tag_name):
        await message.answer(
            f"✅ Тег `{tag_name}` добавлен к каналу `{chat_id}`.",
            parse_mode="Markdown"
        )
        await show_channel_tags(chat_id, user, message)
    else:
        await message.answer("⚠️ Не удалось добавить тег.")
    await state.clear()


@dp.message(Command("remove_channel"))
async def cmd_remove_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    remove_channel_by_id(chat_id, user.id)
    await remove_channel_listener(chat_id)
    await message.answer(f"🗑 Канал {chat_id} удалён.")


@dp.message(Command("list_channels"))
async def cmd_list_channels(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    channels = get_active_channels(user.id)
    if not channels:
        await message.answer("❌ Нет активных каналов.")
        return

    text = "📋 Активные каналы:\n" + "\n".join(
        f"• {ch.chat_id} ({ch.title or 'Без названия'})" for ch in channels
    )
    await message.answer(text)


@dp.message(Command("add_target_channel"))
async def cmd_add_target_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer(
            "⚠️ Вы ещё не авторизованы. Сначала выполните /auth.")
        return

    title = await fetch_channel_title(chat_id, client)

    if add_target_channel(chat_id, user.id, title=title):
        await message.answer(f"✅ Таргетный канал {chat_id} добавлен.")
    else:
        await message.answer(f"⚠️ Таргетный канал {chat_id} уже существует.")


@dp.message(Command("remove_target_channel"))
async def cmd_remove_target_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    remove_target_channel(chat_id, user.id)
    await message.answer(f"🗑 Таргетный канал {chat_id} удалён.")


@dp.message(Command("list_target_channels"))
async def cmd_list_target_channels(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    channels = get_target_channels(user.id)
    if not channels:
        await message.answer("❌ Нет таргетных каналов.")
        return

    text = "🎯 Таргетные каналы:\n" + "\n".join(
        f"• {ch.chat_id} ({ch.title or 'Без названия'})" for ch in channels
    )
    await message.answer(text)


@dp.message(Command("add_target_tag"))
async def cmd_add_target_tag(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и тег!")
        return

    try:
        chat_id = int(args[1])
        tag_name = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if add_tag_to_target_channel(chat_id, user.id, tag_name):
        await message.answer(f"✅ Тег '{tag_name}' добавлен к каналу {chat_id}.")
    else:
        await message.answer(f"⚠️ Не удалось добавить тег.")


@dp.message(Command("remove_target_tag"))
async def cmd_remove_target_tag(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и тег!")
        return

    try:
        chat_id = int(args[1])
        tag_name = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if remove_tag_from_target_channel(chat_id, user.id, tag_name):
        await message.answer(
            f"🗑 Тег `{tag_name}` удалён у канала `{chat_id}`.",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"⚠️ Не удалось удалить тег.")


@dp.message(Command("list_target_tags"))
async def cmd_list_target_tags(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    tags = get_tags_for_target_channel(chat_id, user.id)
    if not tags:
        await message.answer(f"❌ У канала {chat_id} нет тегов.")
        return

    text = "🏷 Теги канала:\n" + "\n".join(f"• {tag.name}" for tag in tags)
    await message.answer(text)


@dp.message(Command("list_tags"))
async def cmd_list_tags(message: Message):
    tags = get_all_tags()
    if not tags:
        await message.answer("❌ Нет доступных тегов.")
        return

    text = "🏷 Существующие теги:\n" + "\n".join(f"• {tag.name}" for tag in tags)
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("set_rewrite_prompt"))
async def cmd_set_rewrite_prompt(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и текст промта!")
        return

    try:
        chat_id = int(args[1])
        prompt = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    if set_rewrite_prompt(chat_id, user.id, prompt):
        await message.answer(f"✅ Промт для канала {chat_id} установлен.")
    else:
        await message.answer(f"⚠️ Канал {chat_id} не найден.")


@dp.message(Command("get_rewrite_prompt"))
async def cmd_get_rewrite_prompt(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    prompt = get_rewrite_prompt(chat_id, user.id)
    if prompt:
        await message.answer(f"📜 Промт для канала {chat_id}:\n\n{prompt}")
    else:
        await message.answer(f"ℹ️ Промт для канала {chat_id} не установлен.")


@dp.message(Command("set_include_image"))
async def cmd_set_include_image(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и 'yes' или 'no'!")
        return

    try:
        chat_id = int(args[1])
        include = args[2].lower() == "yes"
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if set_include_image(chat_id, user.id, include):
        await message.answer(
            f"✅ Настройка изображения для {chat_id} установлена: {'да' if include else 'нет'}.")
    else:
        await message.answer("⚠️ Не удалось обновить настройки.")


@dp.message(Command("get_include_image"))
async def cmd_get_include_image(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    include = get_include_image(chat_id, user.id)
    if include is None:
        await message.answer("❌ Канал не найден или не принадлежит вам.")
    elif include:
        await message.answer(
            f"🖼 Генерация изображения для канала {chat_id} включена.")
    else:
        await message.answer(
            f"🚫 Генерация изображения для канала {chat_id} отключена.")


@dp.message(Command("set_image_prompt"))
async def cmd_set_image_prompt(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и промт!")
        return

    try:
        chat_id = int(args[1])
        prompt = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    if set_image_prompt(chat_id, user.id, prompt):
        await message.answer(f"✅ Промт для генерации изображения установлен.")
    else:
        await message.answer("❌ Канал не найден.")


@dp.message(Command("get_image_prompt"))
async def cmd_get_image_prompt(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    prompt = get_image_prompt(chat_id, user.id)
    if prompt:
        await message.answer(
            f"🖼 Промт изображения для канала {chat_id}:\n\n{prompt}")
    else:
        await message.answer(f"ℹ️ Промт изображения не задан.")
