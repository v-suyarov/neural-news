from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from bot.interface.tags import (
    handle_menu_tags, handle_tags_all, handle_tags_of_channel,
    handle_tags_show_channel, handle_tag_add_start, handle_tag_remove_start,
    handle_tag_delete, handle_tags_add_manual, handle_tags_remove_manual,
    handle_tag_pick
)
from bot.interface.listener import (
    show_listener_menu, handle_listener_set, handle_listener_show
)
from bot.interface.base import (
    show_main_menu
)
from bot.interface.sources import (
    handle_menu_sources, handle_source_list,
    handle_source_add, handle_source_remove, handle_source_delete_by_id,
)
from bot.interface.targets import (
    handle_menu_targets, handle_target_list, handle_target_add,
    handle_target_remove_menu, handle_target_remove_by_id
)
from client.client_manager import get_user_client
from bot.bot_instance import dp
from db.utils import (
    add_channel, fetch_channel_title, remove_tag_from_target_channel,
    add_tag_to_target_channel, get_target_channels,
    get_tags_for_target_channel, get_all_tags, get_or_create_user,
    get_rewrite_prompt, set_rewrite_prompt, set_include_image,
    get_include_image, set_image_prompt, get_image_prompt
)
from client.listeners import add_channel_listener

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
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
        await handle_menu_targets(query)
    elif data == "target_list":
        await handle_target_list(query, user)
    elif data == "target_add":
        await handle_target_add(query, state)
    elif data == "target_remove":
        await handle_target_remove_menu(query, user)
    elif data.startswith("remove_target_"):
        await handle_target_remove_by_id(query, user, data)

    elif data == "menu_tags":
        await handle_menu_tags(query)
    elif data == "tags_all":
        await handle_tags_all(query)
    elif data == "tags_of_channel":
        await handle_tags_of_channel(query, user)
    elif data.startswith("show_tags_"):
        await handle_tags_show_channel(query, user, data)
    elif data.startswith("tag_add_"):
        await handle_tag_add_start(query, state, data)
    elif data.startswith("tag_remove_"):
        await handle_tag_remove_start(query, user, data)
    elif data.startswith("tag_delete_"):
        await handle_tag_delete(query, user, data)
    elif data == "tags_add":
        await handle_tags_add_manual(query, state)
    elif data == "tags_remove":
        await handle_tags_remove_manual(query, state)
    elif data.startswith("tag_pick_"):
        await handle_tag_pick(query, user, data)

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
