import os
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from datetime import datetime

# Словари для хранения данных
user_items = {}  # {user_id: ['item1', 'item2']}
active_jobs = {}
last_notifications = {}  # {user_id: {'item': datetime}}

# --- Функция получения магазина через API ---
def get_fortnite_shop():
    try:
        response = requests.get("https://fortnite-api.com/v2/shop/br", timeout=10)
        response.raise_for_status()
        data = response.json()
        if data.get("status") == 200:
            items = []
            for entry in data["data"]["featured"]["entries"] + data["data"]["daily"]["entries"]:
                for item in entry["items"]:
                    name = item.get("name")
                    if name:
                        items.append(name.lower())
            return items
        else:
            print("API вернул ошибку:", data.get("status"))
            return []
    except Exception as e:
        print("Ошибка при получении магазина:", e)
        return []

# --- Функция получения изображения магазина ---
def get_shop_image_url():
    try:
        # Попробуем получить изображение магазина из другого источника
        # fortnitey.com предоставляет кешированное изображение магазина
        # Обычно оно обновляется раз в день
        date_today = datetime.now().strftime('%Y-%m-%d')
        # Это пример URL. Он может отличаться или быть недоступен.
        # Реальный URL нужно искать на сайте или в другом API.
        # Пока что используем заглушку.
        return f"https://fortnitey.com/shop-image-{date_today}.jpg" # Замени на реальный URL
    except Exception as e:
        print("Не удалось получить изображение магазина:", e)
        return None

# --- Функция для периодической проверки ---
async def check_fortnite_shop(context: ContextTypes.DEFAULT_TYPE):
    user_id = context.job.user_id
    tracked_items = user_items.get(user_id, [])
    if not tracked_items:
        return

    shop_items = get_fortnite_shop()
    if not shop_items:
        print("Не удалось получить магазин.")
        return

    found_items = [item for item in tracked_items if item.lower() in shop_items]

    if found_items:
        now = datetime.now()
        notified_items = last_notifications.get(user_id, {})
        interval_minutes = 1440  # фиксированный интервал: 24 часа
        interval_seconds = interval_minutes * 60
        should_notify = []

        for item in found_items:
            last_time = notified_items.get(item)
            if last_time is None or (now - last_time).total_seconds() >= interval_seconds:
                should_notify.append(item)
                notified_items[item] = now

        if should_notify:
            last_notifications[user_id] = notified_items
            found_str = ", ".join(should_notify)
            try:
                await context.bot.send_message(chat_id=user_id, text=f"🎉 В магазине Fortnite появились: {found_str}!")
            except Exception as e:
                print(f"Не удалось отправить сообщение пользователю {user_id}: {e}")

# --- Функция проверки магазина по кнопке ---
async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    tracked_items = user_items.get(user_id, [])
    if not tracked_items:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text("❌ Вы не отслеживаете ни одного предмета.", reply_markup=reply_markup)
        return

    shop_items = get_fortnite_shop()
    if not shop_items:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text("❌ Не удалось получить магазин.", reply_markup=reply_markup)
        return

    found_items = [item for item in tracked_items if item.lower() in shop_items]

    if found_items:
        found_str = ", ".join(found_items)
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(f"🔍 В магазине найдены: {found_str}!", reply_markup=reply_markup)
    else:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text("❌ В магазине нет отслеживаемых предметов.", reply_markup=reply_markup)

# --- Функция отправки изображения магазина ---
async def send_shop_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    image_url = get_shop_image_url()
    if image_url:
        try:
            await context.bot.send_photo(chat_id=update.effective_user.id, photo=image_url)
        except Exception as e:
            await update.callback_query.edit_message_text("❌ Не удалось загрузить изображение магазина.")
            print(f"Ошибка при отправке изображения: {e}")
    else:
        await update.callback_query.edit_message_text("❌ Не удалось получить изображение магазина.")
    
    # Показать главное меню
    keyboard = [
        [InlineKeyboardButton("➕ Добавить предмет", callback_data='add_item')],
        [InlineKeyboardButton("❌ Удалить предмет", callback_data='remove_item')],
        [InlineKeyboardButton("🔍 Проверить магазин сейчас", callback_data='check_now')],
        [InlineKeyboardButton("🖼️ Показать магазин", callback_data='show_shop_image')],
        [InlineKeyboardButton("⏹️ Остановить проверку", callback_data='stop_check')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text("Выберите действие:", reply_markup=reply_markup)


# --- Функция отправки главного меню ---
async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    keyboard = [
        [InlineKeyboardButton("➕ Добавить предмет", callback_data='add_item')],
        [InlineKeyboardButton("❌ Удалить предмет", callback_data='remove_item')],
        [InlineKeyboardButton("🔍 Проверить магазин сейчас", callback_data='check_now')],
        [InlineKeyboardButton("🖼️ Показать магазин", callback_data='show_shop_image')],
        [InlineKeyboardButton("⏹️ Остановить проверку", callback_data='stop_check')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = 'Выберите действие:'

    if query:
        await query.edit_message_text(text=text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup)

# --- Команды бота ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_items:
        user_items[user_id] = []
    await send_main_menu(update, context)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if user_id not in user_items:
        user_items[user_id] = []

    if query.data == 'add_item':
        context.user_data['awaiting_item'] = True
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Введите английское название предмета для отслеживания:", reply_markup=reply_markup)
    elif query.data == 'remove_item':
        items = user_items[user_id]
        if not items:
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("Список отслеживаемых предметов пуст.", reply_markup=reply_markup)
            return
        keyboard = [[InlineKeyboardButton(item, callback_data=f'del_item_{item}')] for item in items]
        keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data='main_menu')])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Выберите предмет для удаления:", reply_markup=reply_markup)
    elif query.data == 'check_now':
        await check_now(update, context)
    elif query.data == 'show_shop_image':
        await send_shop_image(update, context)
    elif query.data.startswith('int_'):
        minutes = int(query.data[4:])
        user_intervals[user_id] = minutes
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"✅ Интервал между уведомлениями: {minutes} минут.", reply_markup=reply_markup)
    elif query.data == 'stop_check':
        job = active_jobs.get(user_id)
        if job:
            job.schedule_removal()
            del active_jobs[user_id]
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("✅ Проверка остановлена.", reply_markup=reply_markup)
        else:
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text("❌ Проверка не запущена.", reply_markup=reply_markup)
    elif query.data == 'main_menu':
        await send_main_menu(update, context, query=query)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_items:
        user_items[user_id] = []

    if context.user_data.get('awaiting_item'):
        item = update.message.text.strip().lower()
        if item not in user_items[user_id]:
            user_items[user_id].append(item)
            await update.message.reply_text(f"Предмет добавлен: {item}")
        else:
            await update.message.reply_text("Предмет уже добавлен.")

        context.user_data['awaiting_item'] = False

        # Запускаем проверку, если ещё не запущена
        if user_id not in active_jobs:
            interval_minutes = 1440  # фиксированный интервал: 24 часа
            interval_seconds = interval_minutes * 60
            new_job = context.job_queue.run_repeating(
                check_fortnite_shop,
                interval=interval_seconds,  # Проверка каждые 24 часа
                first=0,
                user_id=user_id
            )
            active_jobs[user_id] = new_job
            await update.message.reply_text(f"✅ Проверка запущена. Интервал между уведомлениями: {interval_minutes} минут.")

        # Отправляем главное меню
        keyboard = [
            [InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Предмет добавлен. Нажмите кнопку ниже, чтобы вернуться в меню:", reply_markup=reply_markup)

async def handle_delete_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    item_to_delete = query.data[10:]  # Убираем 'del_item_'
    user_id = query.from_user.id
    if item_to_delete in user_items[user_id]:
        user_items[user_id].remove(item_to_delete)
        notified_items = last_notifications.get(user_id, {})
        notified_items.pop(item_to_delete, None)
        last_notifications[user_id] = notified_items
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Предмет удалён: {item_to_delete}", reply_markup=reply_markup)
    else:
        keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data='main_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Предмет не найден.", reply_markup=reply_markup)

# --- Запуск бота ---
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Получаем токен из переменной окружения
    if not TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения.")
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_delete_item, pattern=r'^del_item_'))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()
