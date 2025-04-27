from aiogram.filters import Command
from aiogram.types import Message
from .bot_instance import dp
from db.utils import add_channel, remove_channel_by_id, get_active_channels, \
    fetch_channel_title
from client.listeners import add_channel_listener, remove_channel_listener

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🤖 Бот запущен. Используйте /add_channel, /remove_channel, /list_channels.")

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

    title = await fetch_channel_title(chat_id)  # Новое: асинхронно получили название
    if not add_channel(chat_id, title=title):   # Старое: синхронно сохранили в базу
        await message.answer(f"⚠️ Канал {chat_id} уже добавлен.")
    else:
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

    text = "📋 Активные каналы:" + "\n".join(f"• {ch.chat_id}" for ch in channels)
    await message.answer(text)