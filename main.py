import asyncio
from aiogram import Bot
from bot.bot_instance import dp, bot
from client.listeners import add_channel_listener
from db.utils import init_db, get_all_users_with_accounts, get_active_channels
from client.client_manager import start_user_client, get_user_client
from bot import handlers as bot_handlers  # Регистрируем хендлеры


async def start_all_user_clients():
    users = get_all_users_with_accounts()
    if users:
        print("🔄 Инициализация Telegram-клиентов для пользователей...")
        for user in users:
            try:
                result = await start_user_client(user.id)
                if result == 'ok':
                    client = get_user_client(user.id)
                    channels = get_active_channels(user.id)
                    for channel in channels:
                        await add_channel_listener(channel.chat_id, client)

            except Exception as e:
                print(f"⚠️ Не удалось запустить клиента для user_id={user.id}: {e}")
    else:
        print("❗️ Нет пользователей с Telegram-аккаунтами.")


async def main():
    init_db()
    await asyncio.gather(
        dp.start_polling(bot),
        start_all_user_clients()
    )


if __name__ == "__main__":
    asyncio.run(main())
