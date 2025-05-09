from aiogram import Bot

from .models import Channel, ParsedPost, Tag, PostTag, Base, TargetChannelTag, \
    TargetChannel, User, TelegramAccount
from .session import Session
import random


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


def get_active_channels(user_id: int = None):
    with Session() as session:
        if user_id is not None:
            channels = session.query(Channel).filter_by(user_id=user_id).all()
        else:
            channels = session.query(Channel).all()

    unique = {}
    for channel in channels:
        if channel.chat_id not in unique:
            unique[channel.chat_id] = channel

    return list(unique.values())


def add_channel(chat_id, user_id, title=None):
    with Session() as session:
        if session.query(Channel).filter_by(chat_id=chat_id,
                                            user_id=user_id).first():
            return False
        session.add(Channel(chat_id=chat_id, user_id=user_id, title=title))
        session.commit()
        return True


def remove_channel_by_id(chat_id, user_id):
    with Session() as session:
        channel = session.query(Channel).filter_by(chat_id=chat_id,
                                                   user_id=user_id).first()
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

        return post.id


async def fetch_channel_title(chat_id, client):
    if not client.is_connected():
        await client.connect()

    try:
        entity = await client.get_entity(chat_id)
        return entity.title
    except Exception as e:
        print(f"⚠️ Ошибка при получении канала {chat_id}: {e}")
        return None


def add_target_channel(chat_id, user_id, title=None):
    with Session() as session:
        if session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                  user_id=user_id).first():
            return False
        session.add(
            TargetChannel(chat_id=chat_id, user_id=user_id, title=title))
        session.commit()
        return True


def remove_target_channel(chat_id, user_id):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                                user_id=user_id).first()
        if target_channel:
            session.delete(target_channel)
            session.commit()


def get_target_channels(user_id):
    with Session() as session:
        return session.query(TargetChannel).filter_by(user_id=user_id).all()


def add_tag_to_target_channel(chat_id, user_id, tag_name):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                                user_id=user_id).first()
        if not target_channel:
            return False

        tag = session.query(Tag).filter_by(name=tag_name).first()
        if not tag:
            return False

        existing = session.query(TargetChannelTag).filter_by(
            target_channel_id=target_channel.id, tag_id=tag.id
        ).first()
        if existing:
            return False

        session.add(TargetChannelTag(target_channel_id=target_channel.id,
                                     tag_id=tag.id))
        session.commit()
        return True


def remove_tag_from_target_channel(chat_id, user_id, tag_name):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                                user_id=user_id).first()
        if not target_channel:
            return False

        tag = session.query(Tag).filter_by(name=tag_name).first()
        if not tag:
            return False

        association = session.query(TargetChannelTag).filter_by(
            target_channel_id=target_channel.id, tag_id=tag.id
        ).first()
        if association:
            session.delete(association)
            session.commit()
            return True
        return False


def get_tags_for_target_channel(chat_id, user_id):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                                user_id=user_id).first()
        if not target_channel:
            return []
        tags = (
            session.query(Tag)
            .join(TargetChannelTag, Tag.id == TargetChannelTag.tag_id)
            .filter(TargetChannelTag.target_channel_id == target_channel.id)
            .all()
        )
        return tags


async def post_to_target_channels(bot: Bot, post_id: int, text: str):
    with Session() as session:
        post_tags = session.query(PostTag).filter_by(post_id=post_id).all()
        if not post_tags:
            print(f"⚠️ Нет тегов у поста {post_id}")
            return

        post_tag_ids = {pt.tag_id for pt in post_tags}
        target_channels = session.query(TargetChannel).all()
        if not target_channels:
            print(f"⚠️ Нет таргетных каналов.")
            return

        for target_channel in target_channels:
            allowed_tags = session.query(TargetChannelTag).filter_by(
                target_channel_id=target_channel.id).all()
            allowed_tag_ids = {at.tag_id for at in allowed_tags}

            if post_tag_ids & allowed_tag_ids:
                rewritten_text = rewrite_text(text,
                                              target_channel.rewrite_prompt)
                try:
                    await bot.send_message(target_channel.chat_id,
                                           rewritten_text)
                    print(
                        f"📤 Отправлено в {target_channel.chat_id} ({target_channel.title})")
                except Exception as e:
                    print(f"⚠️ Ошибка отправки в {target_channel.chat_id}: {e}")


def get_all_tags():
    with Session() as session:
        return session.query(Tag).order_by(Tag.name).all()


def get_or_create_user(telegram_id):
    with Session() as session:
        user = session.query(User).filter_by(telegram_id=telegram_id).first()
        if not user:
            user = User(telegram_id=telegram_id)
            session.add(user)
            session.commit()
        return user


def set_rewrite_prompt(chat_id, user_id, prompt):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                                user_id=user_id).first()
        if not target_channel:
            return False
        target_channel.rewrite_prompt = prompt
        session.commit()
        return True


def get_rewrite_prompt(chat_id, user_id):
    with Session() as session:
        target_channel = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                                user_id=user_id).first()
        if not target_channel:
            return None
        return target_channel.rewrite_prompt


def rewrite_text(text, prompt=None):
    if not prompt:
        return text  # если промта нет, возвращаем оригинал
    return f"{text}\n\n[Переписано с промтом: {prompt}]"


def set_telegram_account(user_id, api_id, api_hash, phone):
    session_name = f"user_{user_id}.session"
    with Session() as session:
        account = session.query(TelegramAccount).filter_by(
            user_id=user_id).first()
        if not account:
            account = TelegramAccount(
                user_id=user_id,
                api_id=api_id,
                api_hash=api_hash,
                phone=phone,
                session_name=session_name
            )
            session.add(account)
        else:
            account.api_id = api_id
            account.api_hash = api_hash
            account.phone = phone
            account.session_name = session_name
        session.commit()


def get_telegram_account(user_id):
    with Session() as session:
        return session.query(TelegramAccount).filter_by(user_id=user_id).first()


def get_all_users_with_accounts():
    with Session() as session:
        return session.query(User).join(TelegramAccount).all()
