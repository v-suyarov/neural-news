from bot.bot_instance import bot
from db.utils import save_post, post_to_target_channels, assign_tags_to_post, \
    get_allowed_target_channels, rewrite_text_if_needed, \
    generate_image_if_needed, send_to_channel
from db.session import Session
from db.models import Channel, PostTag, Tag


async def global_handler(event):
    text = event.raw_text
    sender = await event.get_sender()

    # Получаем название канала
    with Session() as session:
        channel = session.query(Channel).filter_by(chat_id=event.chat_id).first()
        channel_title = channel.title if channel and channel.title else "Неизвестный канал"

    print(f"\n📥 Новое сообщение от {sender.id if sender else 'Неизвестно'} в {channel_title} (ID {event.chat_id}):\n{text}\n{'-' * 40}")

    try:
        post_id = await save_post(
            message_id=event.id,
            chat_id=event.chat_id,
            text=text
        )
        print("✅ Сообщение сохранено в БД.")

        # 2. Определяем теги через модель
        await assign_tags_to_post(post_id, text)

        with Session() as session:
            post_tags = session.query(PostTag).filter_by(post_id=post_id).all()
            tag_ids = [pt.tag_id for pt in post_tags]
            tags = session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
            tag_names = [tag.name for tag in tags]

        tags_text = ", ".join(tag_names) if tag_names else "Нет тегов"
        print(f"🏷 Определены теги: {tags_text}")

        # 3. Получаем подходящие таргет-каналы
        target_channels = get_allowed_target_channels(post_id)
        if not target_channels:
            print("⚠️ Нет подходящих таргетных каналов.")
            return

        # 4. Генерация для каждого таргетного канала
        for channel in target_channels:
            rewrite_prompt = (channel.rewrite_prompt or "").strip()
            image_prompt = (channel.image_prompt or "").strip()
            include_image = bool(channel.include_image)

            try:
                rewritten_text = await rewrite_text_if_needed(text, rewrite_prompt)
                image_data = await generate_image_if_needed(text, image_prompt) if include_image else None

                await send_to_channel(bot, channel.chat_id, channel.title, rewritten_text, image_data)

            except Exception as e:
                print(f"❌ Ошибка при обработке канала {channel.chat_id}: {e}")

    except Exception as e:
        print(f"⚠️ Ошибка в global_handler: {e}")
