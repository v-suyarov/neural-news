from aiogram.filters import Command
from aiogram.types import Message

from client.client_manager import get_user_client
from client.client_manager import start_user_client
from .bot_instance import dp
from db.utils import add_channel, remove_channel_by_id, get_active_channels, \
    fetch_channel_title, remove_tag_from_target_channel, \
    add_tag_to_target_channel, get_target_channels, remove_target_channel, \
    add_target_channel, get_tags_for_target_channel, get_all_tags, \
    get_or_create_user, get_rewrite_prompt, set_rewrite_prompt, \
    set_telegram_account, get_telegram_account, get_user
from client.listeners import add_channel_listener, remove_channel_listener


@dp.message(Command("start"))
async def cmd_start(message: Message):
    text = (
        "🤖 *Бот запущен!* Вот что я умею на данный момент:\n\n"

        "🔐 *Настройка слушателя:*\n"
        "• `/set_listener <api_id> <api_hash> <phone>` — авторизовать Telegram-аккаунт для прослушивания\n"
        "• `/get_listener` — показать информацию о слушателе и список каналов\n\n"

        "📥 *Работа с каналами-источниками:*\n"
        "• `/add_channel <chat_id>` — добавить канал для прослушивания\n"
        "• `/remove_channel <chat_id>` — удалить канал из прослушивания\n"
        "• `/list_channels` — показать все каналы-источники\n\n"

        "🎯 *Работа с таргетными каналами:*\n"
        "• `/add_target_channel <chat_id>` — добавить таргетный канал\n"
        "• `/remove_target_channel <chat_id>` — удалить таргетный канал\n"
        "• `/list_target_channels` — показать все таргетные каналы\n\n"

        "🏷 *Управление тегами таргетных каналов:*\n"
        "• `/add_target_tag <chat_id> <тег>` — добавить разрешённый тег для таргетного канала\n"
        "• `/remove_target_tag <chat_id> <тег>` — удалить тег из таргетного канала\n"
        "• `/list_target_tags <chat_id>` — показать теги, разрешённые для канала\n"
        "• `/list_tags` — показать все существующие теги\n\n"

        "✏️ *Настройка рерайта сообщений:*\n"
        "• `/set_rewrite_prompt <chat_id> <промт>` — задать промт для рерайта постов канала\n"
        "• `/get_rewrite_prompt <chat_id>` — посмотреть текущий промт канала\n"
    )
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("add_channel"))
async def cmd_add_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer(
            "⚠️ Вам необходимо добавить слушателя /set_listener")
        return

    title = await fetch_channel_title(chat_id, client)

    if add_channel(chat_id, user.id, title=title):
        await add_channel_listener(chat_id, client)
        await message.answer(f"✅ Канал {chat_id} добавлен.")
    else:
        await message.answer(f"⚠️ Канал {chat_id} уже существует.")


@dp.message(Command("remove_channel"))
async def cmd_remove_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    remove_channel_by_id(chat_id, user.id)
    await remove_channel_listener(chat_id)
    await message.answer(f"🗑 Канал {chat_id} удалён.")


@dp.message(Command("list_channels"))
async def cmd_list_channels(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    channels = get_active_channels(user.id)
    if not channels:
        await message.answer("❌ Нет активных каналов.")
        return

    text = "📋 Активные каналы:\n" + "\n".join(
        f"• {ch.chat_id} ({ch.title or 'Без названия'})" for ch in channels
    )
    await message.answer(text)


@dp.message(Command("add_target_channel"))
async def cmd_add_target_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer(
            "⚠️ Вы ещё не авторизованы. Сначала выполните /auth.")
        return

    title = await fetch_channel_title(chat_id, client)

    if add_target_channel(chat_id, user.id, title=title):
        await message.answer(f"✅ Таргетный канал {chat_id} добавлен.")
    else:
        await message.answer(f"⚠️ Таргетный канал {chat_id} уже существует.")


@dp.message(Command("remove_target_channel"))
async def cmd_remove_target_channel(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    remove_target_channel(chat_id, user.id)
    await message.answer(f"🗑 Таргетный канал {chat_id} удалён.")


@dp.message(Command("list_target_channels"))
async def cmd_list_target_channels(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    channels = get_target_channels(user.id)
    if not channels:
        await message.answer("❌ Нет таргетных каналов.")
        return

    text = "🎯 Таргетные каналы:\n" + "\n".join(
        f"• {ch.chat_id} ({ch.title or 'Без названия'})" for ch in channels
    )
    await message.answer(text)


@dp.message(Command("add_target_tag"))
async def cmd_add_target_tag(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и тег!")
        return

    try:
        chat_id = int(args[1])
        tag_name = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if add_tag_to_target_channel(chat_id, user.id, tag_name):
        await message.answer(f"✅ Тег '{tag_name}' добавлен к каналу {chat_id}.")
    else:
        await message.answer(f"⚠️ Не удалось добавить тег.")


@dp.message(Command("remove_target_tag"))
async def cmd_remove_target_tag(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и тег!")
        return

    try:
        chat_id = int(args[1])
        tag_name = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if remove_tag_from_target_channel(chat_id, user.id, tag_name):
        await message.answer(f"🗑 Тег '{tag_name}' удалён у канала {chat_id}.")
    else:
        await message.answer(f"⚠️ Не удалось удалить тег.")


@dp.message(Command("list_target_tags"))
async def cmd_list_target_tags(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id канала!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    tags = get_tags_for_target_channel(chat_id, user.id)
    if not tags:
        await message.answer(f"❌ У канала {chat_id} нет тегов.")
        return

    text = "🏷 Теги канала:\n" + "\n".join(f"• {tag.name}" for tag in tags)
    await message.answer(text)


@dp.message(Command("list_tags"))
async def cmd_list_tags(message: Message):
    tags = get_all_tags()
    if not tags:
        await message.answer("❌ Нет доступных тегов.")
        return

    text = "🏷 Существующие теги:\n" + "\n".join(f"• {tag.name}" for tag in tags)
    await message.answer(text, parse_mode="Markdown")


@dp.message(Command("set_rewrite_prompt"))
async def cmd_set_rewrite_prompt(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и текст промта!")
        return

    try:
        chat_id = int(args[1])
        prompt = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    if set_rewrite_prompt(chat_id, user.id, prompt):
        await message.answer(f"✅ Промт для канала {chat_id} установлен.")
    else:
        await message.answer(f"⚠️ Канал {chat_id} не найден.")


@dp.message(Command("get_rewrite_prompt"))
async def cmd_get_rewrite_prompt(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 2:
        await message.answer("⚠️ Укажите chat_id!")
        return

    try:
        chat_id = int(args[1])
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    prompt = get_rewrite_prompt(chat_id, user.id)
    if prompt:
        await message.answer(f"📜 Промт для канала {chat_id}:\n\n{prompt}")
    else:
        await message.answer(f"ℹ️ Промт для канала {chat_id} не установлен.")


@dp.message(Command("code"))
async def cmd_code(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    code = message.text.split(maxsplit=1)[1] if len(
        message.text.split()) > 1 else None

    if not code:
        await message.answer("⚠️ Введите код, полученный в Telegram.")
        return

    try:
        result = await start_user_client(user.id, code=code)
        if result == 'ok':
            await message.answer("✅ Авторизация завершена и клиент запущен.")
        else:
            await message.answer("⚠️ Не удалось завершить авторизацию.")
    except Exception as e:
        await message.answer(f"❌ Ошибка при вводе кода: {e}")


@dp.message(Command("set_listener"))
async def cmd_set_listener(message: Message):
    args = message.text.split(maxsplit=4)
    if len(args) < 4:
        await message.answer(
            "⚠️ Формат: /set_listener <api_id> <api_hash> <phone>")
        return
    print(1)
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    print(1)
    try:
        api_id = int(args[1])
        api_hash = args[2]
        phone = args[3]
    except Exception:
        await message.answer("⚠️ Неверный формат данных.")
        return
    print(1)
    set_telegram_account(user.id, api_id, api_hash, phone)
    print(1)
    try:
        result = await start_user_client(user.id)
        if result == 'awaiting_code':
            await message.answer(
                "📩 Код отправлен. Введите его командой:\n`/code <ваш_код>`",
                parse_mode="Markdown")
        else:
            await message.answer("✅ Слушатель авторизован и подключен.")
    except Exception as e:
        await message.answer(f"❌ Ошибка авторизации слушателя: {e}")


@dp.message(Command("get_listener"))
async def cmd_get_listener(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)
    account = get_telegram_account(user.id)
    if not account:
        await message.answer("❌ Слушатель не настроен.")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer("⚠️ Слушатель неактивен. Выполните /set_listener.")
        return

    try:
        dialogs = await client.get_dialogs()
        channels = [
            dialog for dialog in dialogs
            if getattr(dialog.entity, "megagroup", False)
               or getattr(dialog.entity, "broadcast", False)
        ]

        if not channels:
            await message.answer("ℹ️ Слушатель не состоит ни в одном канале.")
            return

        text = (
                f"👤 Текущий слушатель:\n"
                f"• ID: {user.telegram_id}\n"
                f"• Телефон: {account.phone}\n"
                f"📡 Каналы:\n"
                + "\n".join(
                f"• `{ch.entity.id}` — {ch.name}" for ch in channels)
        )

        await message.answer(text)

    except Exception as e:
        await message.answer(f"❌ Ошибка при получении каналов: {e}")
