from .models import Channel, ParsedPost, Tag, PostTag, Base
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


async def fetch_channel_title(chat_id):
    """Получить название канала по chat_id через Telethon."""
    async with client:
        try:
            entity = await client.get_entity(chat_id)
            return entity.title
        except Exception as e:
            print(f"⚠️ Ошибка получения названия канала {chat_id}: {e}")
            return None
