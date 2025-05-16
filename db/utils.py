import asyncio
import base64
import os
import tempfile
import time

from aiogram import Bot
from PIL import Image
from aiogram.types import FSInputFile
from client.constants import SESSIONS_DIR
from img_generate.img_generator import FusionBrainAPI
from text_generate.tag_predictor import tag_predict_client
from text_generate.text_rewriter import rewrite_client
from .models import Channel, ParsedPost, Tag, PostTag, Base, TargetChannelTag, \
    TargetChannel, User, TelegramAccount
from .session import Session
import random

fusion_api = FusionBrainAPI()


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


async def predict_tags_async(text: str) -> list:
    from .models import Tag
    from .session import Session
    import asyncio

    with Session() as session:
        all_tags = session.query(Tag).all()
        tag_names = [t.name for t in all_tags]

    def task():
        return tag_predict_client.predict_tags(text, tag_names)

    predicted_tag_names = await asyncio.to_thread(task)

    with Session() as session:
        return session.query(Tag).filter(Tag.name.in_(predicted_tag_names)).all()


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


async def save_post(message_id, chat_id, text):
    with Session() as session:
        post = ParsedPost(message_id=message_id, chat_id=chat_id, text=text)
        session.add(post)
        session.commit()
        return post.id


async def assign_tags_to_post(post_id: int, text: str):
    with Session() as session:
        all_tags = session.query(Tag).all()
        available = [t.name for t in all_tags]

    def task():
        return tag_predict_client.predict_tags(text, available)

    predicted_names = await asyncio.to_thread(task)

    with Session() as session:
        tag_objs = session.query(Tag).filter(Tag.name.in_(predicted_names)).all()
        for tag in tag_objs:
            session.add(PostTag(post_id=post_id, tag_id=tag.id))
        session.commit()


async def fetch_channel_title(chat_id, client):
    if not client.is_connected():
        await client.connect()

    try:
        entity = await client.get_entity(chat_id)
        return entity.title
    except Exception as e:
        print(f"⚠️ Ошибка при получении имени канала {chat_id}: {e}")
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


def get_allowed_target_channels(post_id: int):
    with Session() as session:
        post_tags = session.query(PostTag).filter_by(post_id=post_id).all()
        if not post_tags:
            return []

        post_tag_ids = {pt.tag_id for pt in post_tags}
        target_channels = session.query(TargetChannel).all()

        result = []
        for tc in target_channels:
            allowed = session.query(TargetChannelTag).filter_by(
                target_channel_id=tc.id
            ).all()
            allowed_tag_ids = {at.tag_id for at in allowed}
            if post_tag_ids & allowed_tag_ids:
                result.append(tc)
        return result


async def rewrite_text_if_needed(text: str, prompt: str) -> str:
    if not prompt:
        return text

    loop = asyncio.get_event_loop()

    def rewrite_blocking():
        return rewrite_client.rewrite(text=text, prompt=prompt)

    return await loop.run_in_executor(None, rewrite_blocking)


async def generate_image_if_needed(post_text: str, user_prompt: str) -> str:
    loop = asyncio.get_event_loop()

    def generate():
        pipeline_id = fusion_api.get_pipeline()
        uuid = fusion_api.generate(post_text=post_text, user_prompt=user_prompt,
                                   pipeline_id=pipeline_id)
        return fusion_api.check_generation(uuid)[0]

    base64_image = await loop.run_in_executor(None, generate)
    return base64.b64decode(base64_image)


async def send_to_channel(bot, chat_id: int, title: str, text: str,
                          image_data: bytes = None):
    try:
        if image_data:
            with tempfile.NamedTemporaryFile(suffix=".jpg",
                                             delete=False) as tmp:
                tmp.write(image_data)
                tmp_path = tmp.name
            photo = FSInputFile(tmp_path)
            await bot.send_photo(chat_id, photo, caption=text, parse_mode="Markdown")
            os.remove(tmp_path)
        else:
            await bot.send_message(chat_id, text, parse_mode="Markdown")

        print(f"📤 Отправлено в {chat_id} ({title})")

    except Exception as e:
        print(f"❌ Ошибка отправки в {chat_id}: {e}")


async def post_to_target_channels(bot, post_id: int, text: str):
    target_channels = get_allowed_target_channels(post_id)
    if not target_channels:
        print("⚠️ Нет подходящих таргетных каналов.")
        return

    for channel in target_channels:
        rewrite_prompt = (channel.rewrite_prompt or "").strip()
        image_prompt = (channel.image_prompt or "").strip()
        include_image = bool(channel.include_image)

        try:
            rewritten_text = await rewrite_text_if_needed(text, rewrite_prompt)
            image_data = await generate_image_if_needed(text,
                                                        image_prompt) if include_image else None
            await send_to_channel(bot, channel.chat_id, channel.title,
                                  rewritten_text, image_data)
        except Exception as e:
            print(f"❌ Ошибка при обработке канала {channel.chat_id}: {e}")


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
        accounts = session.query(TelegramAccount).all()
        valid_user_ids = []

        for acc in accounts:
            if acc.session_name:
                path = get_session_file_path(acc.session_name)
                if os.path.exists(path):
                    valid_user_ids.append(acc.user_id)
                else:
                    print(
                        f"⚠️ Session file missing for user_id={acc.user_id}, clearing session_name")
                    acc.session_name = None

                    session.commit()
        return session.query(User).filter(
            User.id.in_(valid_user_ids)).all()


def get_session_file_path(session_name):
    """
    Возвращает абсолютный путь до session-файла по его имени.
    Пример: "user_123.session" → "sessions/user_123.session"
    """
    if not os.path.exists(SESSIONS_DIR):
        os.makedirs(SESSIONS_DIR)
    return os.path.join(SESSIONS_DIR, session_name)


def get_user(user_id=None, telegram_id=None):
    with Session() as session:
        query = session.query(User)
        if user_id is not None:
            return query.filter_by(id=user_id).first()
        elif telegram_id is not None:
            return query.filter_by(telegram_id=telegram_id).first()
        else:
            raise ValueError("Нужно указать либо user_id, либо telegram_id")


def set_image_prompt(chat_id, user_id, prompt: str):
    with Session() as session:
        tc = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                    user_id=user_id).first()
        if not tc:
            return False
        tc.image_prompt = prompt.strip() if prompt.strip() else None
        session.commit()
        return True


def get_image_prompt(chat_id, user_id):
    with Session() as session:
        tc = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                    user_id=user_id).first()
        return tc.image_prompt if tc else None


def set_include_image(chat_id, user_id, include: bool):
    with Session() as session:
        tc = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                    user_id=user_id).first()
        if not tc:
            return False
        tc.include_image = 1 if include else 0
        session.commit()
        return True


def get_include_image(chat_id, user_id):
    with Session() as session:
        tc = session.query(TargetChannel).filter_by(chat_id=chat_id,
                                                    user_id=user_id).first()
        return bool(tc.include_image) if tc else None


def make_rewrite_callback(bot, chat_id, title, include_image, image_prompt):
    async def callback(result):
        try:
            if include_image:
                # здесь заглушка на картинку
                from aiogram.types import FSInputFile
                import tempfile, os
                from PIL import Image

                with tempfile.NamedTemporaryFile(suffix=".jpg",
                                                 delete=False) as tmp:
                    img = Image.new("RGB", (512, 512), (0, 0, 0))
                    img.save(tmp.name)
                    photo = FSInputFile(tmp.name)

                await bot.send_photo(chat_id, photo, caption=result)
                os.remove(tmp.name)
            else:
                await bot.send_message(chat_id, result)

            print(f"📤 Отправлено в {chat_id} ({title})")

        except Exception as e:
            print(f"⚠️ Ошибка отправки в {chat_id}: {e}")

    return callback
