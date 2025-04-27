from aiogram.filters import Command
from aiogram.types import Message

from client.client_instance import client
from .bot_instance import dp
from db.utils import add_channel, remove_channel_by_id, get_active_channels, \
    fetch_channel_title, remove_tag_from_target_channel, \
    add_tag_to_target_channel, get_target_channels, remove_target_channel, \
    add_target_channel, get_tags_for_target_channel, get_all_tags
from client.listeners import add_channel_listener, remove_channel_listener


@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "🤖 *Бот запущен!* Вот что я умею на данный момент:\n\n"

        "📥 *Работа с каналами-источниками:*\n"
        "• `/add_channel <chat_id>` — добавить канал для прослушивания\n"
        "• `/remove_channel <chat_id>` — удалить канал из прослушивания\n"
        "• `/list_channels` — показать все каналы-источники\n\n"

        "🎯 *Работа с таргетными каналами:*\n"
        "• `/add_target_channel <chat_id>` — добавить таргетный канал\n"
        "• `/remove_target_channel <chat_id>` — удалить таргетный канал\n"
        "• `/list_target_channels` — показать все таргетные каналы\n\n"

        "🏷 *Управление тегами таргетных каналов:*\n"
        "• `/add_target_tag <chat_id> <тег>` — добавить разрешённый тег для таргетного канала\n"
        "• `/remove_target_tag <chat_id> <тег>` — удалить тег из таргетного канала\n"
        "• `/list_target_tags <chat_id>` — показать теги, разрешённые для канала\n\n"

        "🏷 *Работа с тегами в базе:*\n"
        "• `/list_tags` — показать все существующие теги\n\n"

        "⚙️ *Прочее:*\n"
        "• Посты автоматически сохраняются в БД\n"
        "• Теги постов определяются автоматически (пока рандомно)\n"
        "• Посты публикуются в таргетные каналы после рерайта (пока мок 'рерайт GPT')\n\n"

        "ℹ️ *Функционал будет расширяться!*"
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("add_channel"))
async def cmd_add_channel(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    title = await fetch_channel_title(chat_id)

    if not add_channel(chat_id, title=title):
        await message.answer(f"⚠️ Канал {chat_id} уже добавлен.")
        return

    # 💥 Подключаем клиента, если он не подключен
    if not client.is_connected():
        await client.connect()

    # 💥 Подгружаем канал в Telethon сессию
    await client.get_entity(chat_id)

    # Теперь подписываемся
    await add_channel_listener(chat_id)

    await message.answer(f"✅ Канал {chat_id} добавлен.")


@dp.message(Command("remove_channel"))
async def cmd_remove_channel(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    remove_channel_by_id(chat_id)
    await remove_channel_listener(chat_id)
    await message.answer(f"🗑 Канал {chat_id} удалён.")


@dp.message(Command("list_channels"))
async def cmd_list_channels(message: Message):
    channels = get_active_channels()
    if not channels:
        await message.answer("❌ Нет активных каналов.")
        return

    text = "📋 Активные каналы:" + "\n".join(
        f"• {ch.chat_id}" for ch in channels)
    await message.answer(text)


@dp.message(Command("add_target_channel"))
async def cmd_add_target_channel(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    if add_target_channel(chat_id):
        await message.answer(f"✅ Таргетный канал {chat_id} добавлен.")
    else:
        await message.answer(f"⚠️ Таргетный канал {chat_id} уже существует.")


@dp.message(Command("remove_target_channel"))
async def cmd_remove_target_channel(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    remove_target_channel(chat_id)
    await message.answer(f"🗑 Таргетный канал {chat_id} удалён.")


@dp.message(Command("list_target_channels"))
async def cmd_list_target_channels(message: Message):
    channels = get_target_channels()
    if not channels:
        await message.answer("❌ Нет таргетных каналов.")
        return

    text = "🎯 Таргетные каналы:\n" + "\n".join(
        f"• {ch.chat_id} ({ch.title or 'Без названия'})" for ch in channels)
    await message.answer(text)


@dp.message(Command("add_target_tag"))
async def cmd_add_target_tag(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и название тега!")
        return

    try:
        chat_id = int(args[1])
        tag_name = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if add_tag_to_target_channel(chat_id, tag_name):
        await message.answer(f"✅ Тег '{tag_name}' добавлен к каналу {chat_id}.")
    else:
        await message.answer(
            f"⚠️ Не удалось добавить тег. Возможно он уже привязан или не существует.")


@dp.message(Command("remove_target_tag"))
async def cmd_remove_target_tag(message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и название тега!")
        return

    try:
        chat_id = int(args[1])
        tag_name = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if remove_tag_from_target_channel(chat_id, tag_name):
        await message.answer(f"🗑 Тег '{tag_name}' удалён у канала {chat_id}.")
    else:
        await message.answer(f"⚠️ Не удалось удалить тег.")


@dp.message(Command("list_target_tags"))
async def cmd_list_target_tags(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    tags = get_tags_for_target_channel(chat_id)
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

    text = "🏷 *Существующие теги:*\n" + "\n".join(
        f"• {tag.name}" for tag in tags)
    await message.answer(text, parse_mode="Markdown")
