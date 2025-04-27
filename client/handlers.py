from bot.bot_instance import bot
from db.utils import save_post, post_to_target_channels
from db.session import Session
from db.models import Channel


async def global_handler(event):
    text = event.raw_text
    sender = await event.get_sender()

    with Session() as session:
        channel = session.query(Channel).filter_by(chat_id=event.chat_id).first()
        channel_title = channel.title if channel and channel.title else "Неизвестный канал"

    print(f"\n📥 Новое сообщение от {sender.id if sender else 'Неизвестно'} в {channel_title} (ID {event.chat_id}):\n{text}\n{'-' * 40}")

    try:
        post_id = save_post(
            message_id=event.id,
            chat_id=event.chat_id,
            text=text
        )
        print("✅ Сообщение сохранено в БД.")

        await post_to_target_channels(bot, post_id, text)

    except Exception as e:
        print(f"⚠️ Ошибка при сохранении или постинге: {e}")
