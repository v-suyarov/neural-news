from aiogram.filters import Command
from aiogram.types import Message
from telethon.errors import UserNotParticipantError, ChatAdminRequiredError, \
    ChannelInvalidError
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from client.client_manager import get_user_client
from client.client_manager import start_user_client
from bot.bot_instance import dp
from db.utils import add_channel, remove_channel_by_id, get_active_channels, \
    fetch_channel_title, remove_tag_from_target_channel, \
    add_tag_to_target_channel, get_target_channels, remove_target_channel, \
    add_target_channel, get_tags_for_target_channel, get_all_tags, \
    get_or_create_user, get_rewrite_prompt, set_rewrite_prompt, \
    set_telegram_account, get_telegram_account, get_user, set_include_image, \
    get_include_image, set_image_prompt, get_image_prompt
from client.listeners import add_channel_listener, remove_channel_listener

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, \
    CallbackQuery


class ListenerSetup(StatesGroup):
    waiting_api_id = State()
    waiting_api_hash = State()
    waiting_phone = State()
    waiting_code = State()



class SourceAddState(StatesGroup):
    waiting_for_chat_id = State()


# Главное меню
def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚙️ Настройка слушателя",
                              callback_data="menu_listener")],
        [InlineKeyboardButton(text="📥 Каналы-источники",
                              callback_data="menu_sources")],
        [InlineKeyboardButton(text="🎯 Таргетные каналы",
                              callback_data="menu_targets")],
        [InlineKeyboardButton(text="🏷 Теги", callback_data="menu_tags")],
        [InlineKeyboardButton(text="✏️ Рерайт", callback_data="menu_rewrite")],
        [InlineKeyboardButton(text="🖼 Изображения",
                              callback_data="menu_images")],
    ])


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "🤖 Выберите действие:",
        reply_markup=get_main_menu()
    )


def get_sources_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить канал",
                              callback_data="source_add")],
        [InlineKeyboardButton(text="❌ Удалить канал",
                              callback_data="source_remove")],
        [InlineKeyboardButton(text="📋 Список каналов",
                              callback_data="source_list")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_main")]
    ])


def get_listener_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Показать слушателя",
                              callback_data="listener_show")],
        [InlineKeyboardButton(text="➕ Установить слушателя",
                              callback_data="listener_set")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_main")]
    ])


@dp.callback_query()
async def handle_callback(query: CallbackQuery, state: FSMContext):
    data = query.data
    telegram_id = query.from_user.id
    user = get_or_create_user(telegram_id)

    if data == "menu_main":
        await show_main_menu(query)

    elif data == "menu_sources":
        await show_sources_menu(query)

    elif data == "source_list":
        await show_source_list(query, user)
    elif data == "menu_listener":
        await query.message.edit_text(
            "🔐 Настройка слушателя — выберите действие:",
            reply_markup=get_listener_menu()
        )
        await query.answer()
    elif data == "source_add":
        await show_source_add_instruction(query, state)
    elif data == "listener_set":
        await query.message.edit_text(
            "🛠 Давайте настроим слушателя.\nВведите ваш `api_id`:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="⬅️ Назад",
                                      callback_data="menu_listener")]
            ]),
            parse_mode="Markdown"
        )
        await state.set_state(ListenerSetup.waiting_api_id)
        await query.answer()
    elif data == "listener_show":
        account = get_telegram_account(user.id)
        client = get_user_client(user.id)

        if not account:
            await query.message.edit_text("❌ Слушатель не настроен.",
                                          reply_markup=get_listener_menu())
            await query.answer()
            return

        if not client:
            await query.message.edit_text(
                "⚠️ Слушатель неактивен. Выполните настройку заново.",
                reply_markup=get_listener_menu())
            await query.answer()
            return

        try:
            dialogs = await client.get_dialogs()
            channels = [
                dialog for dialog in dialogs
                if getattr(dialog.entity, "megagroup", False) or getattr(
                    dialog.entity, "broadcast", False)
            ]

            text = (
                    f"👤 Текущий слушатель:\n"
                    f"• Телефон: `{account.phone}`\n"
                    f"📡 Каналы:\n"
                    + "\n".join(
                f"• `{ch.entity.id}` — {ch.name}" for ch in channels)
            )
            await query.message.edit_text(text,
                                          reply_markup=get_listener_menu(),
                                          parse_mode="Markdown")

        except Exception as e:
            await query.message.edit_text(f"❌ Ошибка при получении данных: {e}",
                                          reply_markup=get_listener_menu())
        await query.answer()
    elif data == "source_remove":
        await show_source_removal_menu(query, user)

    elif data.startswith("remove_source_"):
        try:
            chat_id = int(data.replace("remove_source_", ""))
            await handle_source_removal(query, user, chat_id)
        except ValueError:
            await query.answer("⚠️ Неверный chat_id")


# Главное меню
async def show_main_menu(query: CallbackQuery):
    await query.message.edit_text("🤖 Выберите действие:",
                                  reply_markup=get_main_menu())
    await query.answer()


# Меню источников
async def show_sources_menu(query: CallbackQuery):
    await query.message.edit_text("📥 Источники каналов:",
                                  reply_markup=get_sources_menu())
    await query.answer()


# Список источников
async def show_source_list(query: CallbackQuery, user):
    channels = get_active_channels(user.id)
    if not channels:
        text = "❌ Нет активных источников."
    else:
        text = "📋 Список источников:\n" + "\n".join(
            f"• `{ch.chat_id}` — {ch.title or 'Без названия'}" for ch in
            channels
        )
    await query.message.edit_text(text, reply_markup=get_sources_menu(),
                                  parse_mode="Markdown")
    await query.answer()


# Добавление источника (инструкция)
async def show_source_add_instruction(query: CallbackQuery, state: FSMContext):
    await query.message.edit_text(
        "Введите ID канала для добавления 📥\n\n"
        "Убедитесь, что вы уже добавили туда слушателя и он может читать сообщения.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Назад",
                                     callback_data="menu_sources"),
                InlineKeyboardButton(text="🏠 Главное меню",
                                     callback_data="menu_main")
            ]
        ])
    )
    await state.set_state(SourceAddState.waiting_for_chat_id)
    await query.answer()


@dp.message(ListenerSetup.waiting_api_id)
async def set_api_id(message: Message, state: FSMContext):
    try:
        api_id = int(message.text.strip())
        await state.update_data(api_id=api_id)
        await state.set_state(ListenerSetup.waiting_api_hash)
        await message.answer("✅ API ID сохранён.\nТеперь введите `api_hash`:",
                             parse_mode="Markdown")
    except ValueError:
        await message.answer("⚠️ Неверный формат API ID. Введите число.")


@dp.message(ListenerSetup.waiting_api_hash)
async def set_api_hash(message: Message, state: FSMContext):
    await state.update_data(api_hash=message.text.strip())
    await state.set_state(ListenerSetup.waiting_phone)
    await message.answer(
        "📞 Отлично. Теперь введите номер телефона в формате +7...",
        parse_mode="Markdown")


@dp.message(ListenerSetup.waiting_phone)
async def set_phone(message: Message, state: FSMContext):
    phone = message.text.strip()
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    data = await state.get_data()
    api_id = data.get("api_id")
    api_hash = data.get("api_hash")

    set_telegram_account(user.id, api_id, api_hash, phone)

    try:
        result = await start_user_client(user.id)
        if result == 'awaiting_code':
            await message.answer("📩 Код отправлен в Telegram. Введите его сюда:")
            await state.set_state(ListenerSetup.waiting_code)
        else:
            await message.answer("✅ Слушатель авторизован и подключён.", reply_markup=get_listener_menu())
            await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка авторизации: {e}", reply_markup=get_listener_menu())
        await state.clear()


@dp.message(ListenerSetup.waiting_code)
async def set_auth_code(message: Message, state: FSMContext):
    code = message.text.strip()
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    try:
        result = await start_user_client(user.id, code=code)
        if result == 'ok':
            await message.answer("✅ Авторизация завершена. Слушатель подключён.", reply_markup=get_listener_menu())
        else:
            await message.answer("⚠️ Что-то пошло не так. Попробуйте заново.", reply_markup=get_listener_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка входа по коду: {e}", reply_markup=get_listener_menu())

    await state.clear()
@dp.message(SourceAddState.waiting_for_chat_id)
async def process_chat_id_input(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    try:
        chat_id = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Неверный формат. Введите числовой ID канала.")
        return

    client = get_user_client(user.id)
    if not client:
        await message.answer(
            "⚠️ Слушатель не активен. Сначала установите слушателя")
        await state.clear()
        return

    try:
        me = await client.get_me()
        await client.get_permissions(chat_id, me.id)
    except Exception:
        await message.answer(
            "❌ Не удалось проверить права. Убедитесь, что слушатель в этом канале.")
        await state.clear()
        return

    title = await fetch_channel_title(chat_id, client)
    if add_channel(chat_id, user.id, title):
        await add_channel_listener(chat_id, client)
        await message.answer(
            f"✅ Канал `{chat_id}` ({title}) добавлен!",
            reply_markup=get_sources_menu(),
            parse_mode="Markdown"
        )
    else:
        await message.answer(
            f"⚠️ Канал `{chat_id}` уже существует.",
            reply_markup=get_sources_menu(),
            parse_mode="Markdown"
        )

    await state.clear()


# Меню удаления каналов
async def show_source_removal_menu(query: CallbackQuery, user):
    channels = get_active_channels(user.id)
    if not channels:
        await query.message.edit_text("❌ Нет источников для удаления.",
                                      reply_markup=get_sources_menu())
        await query.answer()
        return

    keyboard = [
        [InlineKeyboardButton(
            text=f"{ch.title or 'Без названия'} ({ch.chat_id}) ❌",
            callback_data=f"remove_source_{ch.chat_id}"
        )] for ch in channels
    ]
    keyboard.append(
        [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_sources")])
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
    await query.message.edit_text("❌ Выберите канал для удаления:",
                                  reply_markup=markup)
    await query.answer()


# Удаление канала по кнопке
async def handle_source_removal(query: CallbackQuery, user, chat_id: int):
    remove_channel_by_id(chat_id, user.id)
    await remove_channel_listener(chat_id)

    channels = get_active_channels(user.id)
    if not channels:
        await query.message.edit_text(
            "✅ Канал удалён.\n❌ Больше нет активных источников.",
            reply_markup=get_sources_menu())
    else:
        keyboard = [
            [InlineKeyboardButton(
                text=f"{ch.title or 'Без названия'} ({ch.chat_id}) ❌",
                callback_data=f"remove_source_{ch.chat_id}"
            )] for ch in channels
        ]
        keyboard.append([InlineKeyboardButton(text="🔙 Назад",
                                              callback_data="menu_sources")])
        markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        await query.message.edit_text("✅ Канал удалён.",
                                      reply_markup=markup)

    await query.answer()


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
            "⚠️ Вы ещё не авторизованы. Сначала выполните /auth.")
        return

    try:
        me = await client.get_me()
        await client.get_permissions(chat_id, me.id)
    except Exception as e:
        await message.answer(
            f"❌ Не удалось добавить канал. "
            f"Убедитесь, что прослушиватель состоит в нем")
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


@dp.message(Command("set_include_image"))
async def cmd_set_include_image(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split()
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и 'yes' или 'no'!")
        return

    try:
        chat_id = int(args[1])
        include = args[2].lower() == "yes"
    except ValueError:
        await message.answer("⚠️ Неверный формат!")
        return

    if set_include_image(chat_id, user.id, include):
        await message.answer(
            f"✅ Настройка изображения для {chat_id} установлена: {'да' if include else 'нет'}.")
    else:
        await message.answer("⚠️ Не удалось обновить настройки.")


@dp.message(Command("get_include_image"))
async def cmd_get_include_image(message: Message):
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

    include = get_include_image(chat_id, user.id)
    if include is None:
        await message.answer("❌ Канал не найден или не принадлежит вам.")
    elif include:
        await message.answer(
            f"🖼 Генерация изображения для канала {chat_id} включена.")
    else:
        await message.answer(
            f"🚫 Генерация изображения для канала {chat_id} отключена.")


@dp.message(Command("set_image_prompt"))
async def cmd_set_image_prompt(message: Message):
    telegram_id = message.from_user.id
    user = get_or_create_user(telegram_id)

    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer("⚠️ Укажите chat_id и промт!")
        return

    try:
        chat_id = int(args[1])
        prompt = args[2]
    except ValueError:
        await message.answer("⚠️ Неверный формат chat_id!")
        return

    if set_image_prompt(chat_id, user.id, prompt):
        await message.answer(f"✅ Промт для генерации изображения установлен.")
    else:
        await message.answer("❌ Канал не найден.")


@dp.message(Command("get_image_prompt"))
async def cmd_get_image_prompt(message: Message):
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

    prompt = get_image_prompt(chat_id, user.id)
    if prompt:
        await message.answer(
            f"🖼 Промт изображения для канала {chat_id}:\n\n{prompt}")
    else:
        await message.answer(f"ℹ️ Промт изображения не задан.")
