from db.utils import save_post
from db.session import Session
from db.models import Channel


async def global_handler(event):
    text = event.raw_text
    sender = await event.get_sender()

    # Получаем название канала по chat_id
    with Session() as session:
        channel = session.query(Channel).filter_by(
            chat_id=event.chat_id).first()
        channel_title = channel.title if channel and channel.title else "Неизвестный канал"

    print(
        f"\n📥 Новое сообщение от {event.chat_id} ({channel_title})")

    try:
        save_post(
            message_id=event.id,
            chat_id=event.chat_id,
            text=text
        )
        print("✅ Сообщение сохранено в БД.")
    except Exception as e:
        print(f"⚠️ Ошибка при сохранении: {e}")
