import asyncio
from bot.bot_instance import dp, bot
from client.client_instance import client
from db.utils import init_db, get_active_channels
from client.listeners import add_channel_listener
from bot import handlers as bot_handlers

from config import phone


async def phone_main():
    await client.start(phone=phone)
    init_db()

    channels = get_active_channels()
    if channels:
        print("✅ Инициализация подписок на каналы...")
        for channel in channels:
            await add_channel_listener(channel.chat_id)
    else:
        print("❗️ Нет активных каналов для подписки.")

    await client.run_until_disconnected()


async def main():
    init_db()
    await asyncio.gather(
        dp.start_polling(bot),
        phone_main()
    )


if __name__ == "__main__":
    asyncio.run(main())
