from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, \
    CallbackQuery


async def show_main_menu(query: CallbackQuery):
    await query.message.edit_text("🤖 Выберите действие:",
                                  reply_markup=get_main_menu())
    await query.answer()


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
