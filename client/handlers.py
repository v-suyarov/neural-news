from bot.bot_instance import bot
from db.utils import save_post, post_to_target_channels
from db.session import Session
from db.models import Channel, PostTag, Tag


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

        # 🔥 ДОБАВЛЯЕМ вывод тегов и фрагмента сообщения
        with Session() as session:
            post_tags = session.query(PostTag).filter_by(post_id=post_id).all()
            tag_ids = [pt.tag_id for pt in post_tags]
            tags = session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
            tag_names = [tag.name for tag in tags]

        tags_text = ", ".join(tag_names) if tag_names else "Нет тегов"
        text_snippet = (text[:10] + "...") if len(text) > 10 else text

        print(f"🏷 Теги поста: {tags_text}")
        print(f"📝 Фрагмент текста: {text_snippet}")

        await post_to_target_channels(bot, post_id, text)

    except Exception as e:
        print(f"⚠️ Ошибка при сохранении или постинге: {e}")
