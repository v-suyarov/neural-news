from telethon import events

from db.models import Channel
from db.session import Session
from .client_instance import client
from .handlers import global_handler

active_listeners = {}


async def add_channel_listener(chat_id):
    if chat_id in active_listeners:
        return

    with Session() as session:
        channel = session.query(Channel).filter_by(chat_id=chat_id).first()
        title = f" ({channel.title})" if channel and channel.title else ""

    event_filter = events.NewMessage(chats=chat_id)
    client.add_event_handler(global_handler, event_filter)
    active_listeners[chat_id] = event_filter
    print(f"➕ Подписка добавлена на {chat_id}{title}")


async def remove_channel_listener(chat_id):
    if chat_id not in active_listeners:
        return

    with Session() as session:
        channel = session.query(Channel).filter_by(chat_id=chat_id).first()
        title = f" ({channel.title})" if channel and channel.title else ""

    client.remove_event_handler(global_handler, active_listeners.pop(chat_id))
    print(f"➖ Подписка удалена с {chat_id}{title}")
