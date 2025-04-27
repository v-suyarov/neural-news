from aiogram import Bot

from .models import Channel, ParsedPost, Tag, PostTag, Base, TargetChannelTag, \
    TargetChannel
from .session import Session
import random
from client.client_instance import client


def init_db():
    Base.metadata.create_all(bind=Session.kw["bind"])
    preload_tags()


def preload_tags():
    default_tags = [
        "Политика", "Экономика", "Технологии", "Игры", "Культура",
        "Здоровье", "Спорт", "Образование", "Наука", "Развлечения",
        "Искусственный интеллект", "Финансы", "Бизнес", "Закон", "Происшествия",
        "Экология", "Кибербезопасность", "Медицина", "Музыка", "Кино"
    ]
    with Session() as session:
        if not session.query(Tag).count():
            for name in default_tags:
                session.add(Tag(name=name))
            session.commit()


def predict_tags(text):
    """Замоканный метод предсказания тегов на основе текста."""
    with Session() as session:
        all_tags = session.query(Tag).all()
        if not all_tags:
            return []

        num_tags = random.randint(1, min(3, len(all_tags)))
        return random.sample(all_tags, num_tags)


def get_active_channels():
    with Session() as session:
        return session.query(Channel).all()


def add_channel(chat_id, title=None):
    """Сохранить канал в базу данных."""
    with Session() as session:
        if session.query(Channel).filter_by(chat_id=chat_id).first():
            return False
        session.add(Channel(chat_id=chat_id, title=title))
        session.commit()
        return True


def remove_channel_by_id(chat_id):
    with Session() as session:
        channel = session.query(Channel).filter_by(chat_id=chat_id).first()
        if channel:
            session.delete(channel)
            session.commit()


def save_post(message_id, chat_id, text):
    with Session() as session:
        post = ParsedPost(message_id=message_id, chat_id=chat_id, text=text)
        session.add(post)
        session.commit()

        predicted_tags = predict_tags(text)

        for tag in predicted_tags:
            session.add(PostTag(post_id=post.id, tag_id=tag.id))

        session.commit()

        return post



async def fetch_channel_title(chat_id):
    """Получить название канала по chat_id через Telethon."""
    async with client:
        try:
            entity = await client.get_entity(chat_id)
            return entity.title
        except Exception as e:
            print(f"⚠️ Ошибка получения названия канала {chat_id}: {e}")
            return None


def add_target_channel(chat_id, title=None):
    with Session() as session:
        if session.query(TargetChannel).filter_by(chat_id=chat_id).first():
            return False
        session.add(TargetChannel(chat_id=chat_id, title=title))
        session.commit()
        return True


def remove_target_channel(chat_id):
    with Session() as session:
        channel = session.query(TargetChannel).filter_by(
            chat_id=chat_id).first()
        if channel:
            session.delete(channel)
            session.commit()


def get_target_channels():
    with Session() as session:
        return session.query(TargetChannel).all()


def add_tag_to_target_channel(chat_id, tag_name):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(
            chat_id=chat_id).first()
        tag = session.query(Tag).filter_by(name=tag_name).first()
        if not target_channel or not tag:
            return False
        existing = session.query(TargetChannelTag).filter_by(
            target_channel_id=target_channel.id, tag_id=tag.id).first()
        if existing:
            return False
        session.add(TargetChannelTag(target_channel_id=target_channel.id,
                                     tag_id=tag.id))
        session.commit()
        return True


def remove_tag_from_target_channel(chat_id, tag_name):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(
            chat_id=chat_id).first()
        tag = session.query(Tag).filter_by(name=tag_name).first()
        if not target_channel or not tag:
            return False
        association = session.query(TargetChannelTag).filter_by(
            target_channel_id=target_channel.id, tag_id=tag.id).first()
        if association:
            session.delete(association)
            session.commit()
            return True
        return False


def get_tags_for_target_channel(chat_id):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(
            chat_id=chat_id).first()
        if not target_channel:
            return []
        tags = (
            session.query(Tag)
            .join(TargetChannelTag, Tag.id == TargetChannelTag.tag_id)
            .filter(TargetChannelTag.target_channel_id == target_channel.id)
            .all()
        )
        return tags


def rewrite_text(text):
    """Замоканный рерайт текста."""
    return f"{text}\n\n(рерайт GPT)"


async def post_to_target_channels(bot: Bot, post_id: int, text: str):
    """Определить куда постить новость и отправить её в таргетные каналы."""
    with Session() as session:
        # Получаем теги поста
        post_tags = session.query(PostTag).filter_by(post_id=post_id).all()
        if not post_tags:
            print(f"⚠️ Нет тегов у поста {post_id}")
            return

        post_tag_ids = {pt.tag_id for pt in post_tags}

        # Получаем все таргетные каналы
        target_channels = session.query(TargetChannel).all()
        if not target_channels:
            print(f"⚠️ Нет таргетных каналов.")
            return

        for target_channel in target_channels:
            # Получаем разрешённые теги для канала
            allowed_tags = session.query(TargetChannelTag).filter_by(
                target_channel_id=target_channel.id).all()
            allowed_tag_ids = {at.tag_id for at in allowed_tags}

            # Проверяем пересечение
            if post_tag_ids & allowed_tag_ids:
                # Есть хотя бы один совпадающий тег
                rewritten_text = rewrite_text(text)
                try:
                    await bot.send_message(target_channel.chat_id,
                                           rewritten_text)
                    print(
                        f"📤 Отправлено в {target_channel.chat_id} ({target_channel.title})")
                except Exception as e:
                    print(f"⚠️ Ошибка отправки в {target_channel.chat_id}: {e}")
