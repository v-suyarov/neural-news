import os

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeExpiredError

from client.constants import SESSIONS_DIR
from db.utils import get_telegram_account, get_active_channels, \
    get_session_file_path
from client.listeners import add_channel_listener

_clients = {}  # user_id -> TelegramClient (авторизованные)
_pending_clients = {}  # user_id -> TelegramClient (ждущие код)


async def start_user_client(user_id, code=None):
    account = get_telegram_account(user_id)
    if not account:
        raise RuntimeError("Telegram account not found")

    session_path = get_session_file_path(account.session_name)
    client = TelegramClient(
        session_path,
        account.api_id,
        account.api_hash,
        system_version="4.16.30-vxTEST"
    )
    await client.connect()
    if not await client.is_user_authorized():
        if code is None:
            await client.send_code_request(account.phone)
            _pending_clients[user_id] = client
            return 'awaiting_code'

        try:
            client = _pending_clients.pop(user_id, client)
            await client.sign_in(account.phone, code)
        except PhoneCodeExpiredError:
            raise RuntimeError("❌ Код подтверждения просрочен или заблокирован. "
                               "Возможно, вы попытались авторизовать тот же аккаунт, с которого пишете в бота. "
                               "Пожалуйста, используйте другой Telegram-аккаунт.")
        except SessionPasswordNeededError:
            raise RuntimeError("🔐 Аккаунт требует пароль (2FA), пока не поддерживается.")
        except Exception as e:
            raise RuntimeError(f"Ошибка входа с кодом: {e}")

    # Успешная авторизация
    _clients[user_id] = client

    channels = get_active_channels(user_id)
    for channel in channels:
        await add_channel_listener(channel.chat_id, client)

    print(f"✅ Клиент для user_id={user_id} запущен.")
    return 'ok'


def get_user_client(user_id):
    return _clients.get(user_id)


def is_user_pending(user_id):
    return user_id in _pending_clients


async def stop_user_client(user_id):
    """
    Остановить и удалить клиент пользователя (если понадобится).
    """
    client = _clients.pop(user_id, None)
    if client:
        await client.disconnect()
        print(f"🛑 Клиент для user_id={user_id} остановлен.")
