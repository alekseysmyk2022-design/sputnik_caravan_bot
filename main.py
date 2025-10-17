import os
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, Router, types
from aiogram.types import (
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatMemberUpdated,
)
from aiogram.filters import Command, ChatMemberUpdatedFilter, IS_MEMBER, JOIN_TRANSITION
from aiogram.client.bot import DefaultBotProperties
from aiogram.enums import ParseMode
import logging

# --- HTTP заглушка для Render ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        else:
            self.send_response(404)
            self.end_headers()

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()
# --- конец заглушки ---

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RULES_MESSAGE_LINK = os.getenv("RULES_MESSAGE_LINK", "")  # Ссылка на правила

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан!")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()

# Права: запретить всё, кроме чтения
RESTRICTED_PERMISSIONS = ChatPermissions(
    can_send_messages=False,
    can_send_media_messages=False,
    can_send_polls=False,
    can_send_other_messages=False,
    can_add_web_page_previews=False,
    can_change_info=False,
    can_invite_users=False,
    can_pin_messages=False,
)

# Права: полный доступ (после подтверждения)
FULL_PERMISSIONS = ChatPermissions(
    can_send_messages=True,
    can_send_media_messages=True,
    can_send_polls=True,
    can_send_other_messages=True,
    can_add_web_page_previews=True,
    can_change_info=False,
    can_invite_users=True,
    can_pin_messages=False,
)

# Обработка входа нового участника
@router.chat_member(ChatMemberUpdatedFilter(JOIN_TRANSITION))
async def on_user_join(event: ChatMemberUpdated):
    user = event.new_chat_member.user
    chat = event.chat

    # Если это бот — игнорируем
    if user.is_bot:
        return

    # Ограничиваем пользователя
    await bot.restrict_chat_member(chat.id, user.id, RESTRICTED_PERMISSIONS)

    # Формируем ссылку на правила
    rules_text = f'<a href="{RULES_MESSAGE_LINK}">Правилами</a>' if RULES_MESSAGE_LINK else "Правилами"

    # Кнопка подтверждения
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Я прочитал(а) и согласен(на)", callback_data=f"accept_{user.id}")]
        ]
    )

    # Отправляем приветствие
    welcome_msg = await bot.send_message(
        chat.id,
        f"Привет, {user.first_name}! 🏕️\n\n"
        f"Вступая в клуб владельцев Sputnik Caravan, вы соглашаетесь с {rules_text} группы.\n"
        f"Если ты всё прочитал(а), то подтверди это, нажав на кнопку ниже.",
        reply_markup=keyboard,
        disable_web_page_preview=True,
    )

    # Опционально: сохраните welcome_msg.message_id, чтобы удалить позже

# Обработка нажатия кнопки
@router.callback_query(lambda c: c.data.startswith("accept_"))
async def on_accept(callback: types.CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    chat_id = callback.message.chat.id
    current_user_id = callback.from_user.id

    # Проверка: только сам пользователь может подтвердить
    if current_user_id != user_id:
        await callback.answer("Вы не можете подтвердить за другого участника.", show_alert=True)
        return

    # Даём полные права
    await bot.restrict_chat_member(chat_id, user_id, FULL_PERMISSIONS)

    # Удаляем кнопку и меняем текст
    await bot.edit_message_text(
        chat_id=chat_id,
        message_id=callback.message.message_id,
        text=f"Привет, {callback.from_user.first_name}! 🏕️\n\n"
             f"Спасибо, что ознакомились с Правилами! Добро пожаловать в клуб владельцев Sputnik Caravan!",
    )

    await callback.answer()

# Команда для теста
@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Бот модерации запущен.")

dp.include_router(router)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
