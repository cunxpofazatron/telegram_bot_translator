#!/usr/bin/env python3
"""
Курсовая работа
ТГ-чат-бот «Обучалка английскому языку» (EnglishCard)

В этом файле:
1. SQL-скрипты для создания БД
2. Telegram-бот на Python
3. Работа с PostgreSQL
"""

# =====================================================
# 📌 1. SQL СКРИПТЫ ДЛЯ СОЗДАНИЯ БАЗЫ ДАННЫХ
# =====================================================
"""
-- Таблица пользователей
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE,
    first_name TEXT
);

-- Общие слова (для всех пользователей)
CREATE TABLE words (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL,
    translation TEXT NOT NULL
);

-- Персональные слова пользователя
CREATE TABLE user_words (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    word TEXT NOT NULL,
    translation TEXT NOT NULL
);

-- Начальный набор слов (10 штук)
INSERT INTO words (word, translation) VALUES
('red', 'красный'),
('blue', 'синий'),
('green', 'зелёный'),
('yellow', 'жёлтый'),
('black', 'чёрный'),
('white', 'белый'),
('I', 'я'),
('you', 'ты'),
('he', 'он'),
('she', 'она');
"""
# ⬆️ ЭТОТ SQL ВЫПОЛНЯЕТСЯ ОДИН РАЗ В PostgreSQL ⬆️


# =====================================================
# 📌 2. PYTHON-КОД TELEGRAM-БОТА
# =====================================================

import os
import random
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)

# =====================================================
# ⚙️ НАСТРОЙКИ
# =====================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")


def get_db():
    return psycopg2.connect(
        host=DB_HOST,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        cursor_factory=RealDictCursor
    )


# =====================================================
# 👤 ПОЛЬЗОВАТЕЛИ
# =====================================================

def get_or_create_user(tg_id, name):
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT id FROM users WHERE tg_id=%s;", (tg_id,))
    user = cur.fetchone()

    if user:
        user_id = user["id"]
    else:
        cur.execute(
            "INSERT INTO users (tg_id, first_name) VALUES (%s, %s) RETURNING id;",
            (tg_id, name)
        )
        user_id = cur.fetchone()["id"]
        conn.commit()

    cur.close()
    conn.close()
    return user_id


# =====================================================
# 🚀 КОМАНДЫ БОТА
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.first_name)

    text = (
        f"👋 Привет, {user.first_name}!\n\n"
        "📚 Я бот для изучения английских слов.\n\n"
        "Команды:\n"
        "/train — начать тренировку\n"
        "/add — добавить слово\n"
        "/delete — удалить слово\n"
        "/mywords — мои слова\n"
        "/help — помощь"
    )
    await update.message.reply_text(text)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Выбирай правильный перевод слова из 4 вариантов.\n"
        "Добавленные слова видишь только ты."
    )


# =====================================================
# 🧠 ТРЕНИРОВКА
# =====================================================

async def train(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.first_name)

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT word, translation FROM words
        UNION
        SELECT word, translation FROM user_words WHERE user_id=%s;
    """, (user_id,))

    words = cur.fetchall()
    cur.close()
    conn.close()

    if len(words) < 4:
        await update.message.reply_text("❗ Нужно минимум 4 слова.")
        return

    correct = random.choice(words)
    variants = {correct["translation"]}

    while len(variants) < 4:
        variants.add(random.choice(words)["translation"])

    buttons = [
        [InlineKeyboardButton(v, callback_data=f"{correct['word']}|{v}")]
        for v in random.sample(list(variants), 4)
    ]

    await update.message.reply_text(
        f"Как переводится слово *{correct['word']}*?",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="Markdown"
    )


async def check_answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    word, answer = query.data.split("|")

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT translation FROM words WHERE word=%s
        UNION
        SELECT translation FROM user_words WHERE word=%s;
    """, (word, word))
    correct = cur.fetchone()["translation"]
    cur.close()
    conn.close()

    if answer == correct:
        await query.edit_message_text(f"✅ Верно! {word} = {correct}")
    else:
        await query.edit_message_text(
            f"❌ Неверно.\nПравильно: {word} = {correct}"
        )


# =====================================================
# ➕ ДОБАВЛЕНИЕ СЛОВА
# =====================================================

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите слово и перевод через пробел:\n"
        "apple яблоко"
    )


async def save_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.startswith("/"):
        return

    try:
        word, translation = update.message.text.split(" ", 1)
    except ValueError:
        await update.message.reply_text("❌ Формат: слово перевод")
        return

    user = update.effective_user
    user_id = get_or_create_user(user.id, user.first_name)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_words (user_id, word, translation) VALUES (%s,%s,%s);",
        (user_id, word, translation)
    )
    conn.commit()

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM user_words WHERE user_id=%s;",
        (user_id,)
    )
    count = cur.fetchone()["cnt"]

    cur.close()
    conn.close()

    await update.message.reply_text(
        f"✅ Слово добавлено!\n"
        f"📊 Вы изучаете {count} слов"
    )


# =====================================================
# ❌ УДАЛЕНИЕ СЛОВА
# =====================================================

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.first_name)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT word FROM user_words WHERE user_id=%s;", (user_id,))
    words = cur.fetchall()
    cur.close()
    conn.close()

    if not words:
        await update.message.reply_text("📭 У вас нет слов для удаления.")
        return

    buttons = [
        [InlineKeyboardButton(w["word"], callback_data=f"del|{w['word']}")]
        for w in words
    ]

    await update.message.reply_text(
        "Выберите слово для удаления:",
        reply_markup=InlineKeyboardMarkup(buttons)
    )


async def delete_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, word = query.data.split("|")
    user = query.from_user
    user_id = get_or_create_user(user.id, user.first_name)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "DELETE FROM user_words WHERE user_id=%s AND word=%s;",
        (user_id, word)
    )
    conn.commit()
    cur.close()
    conn.close()

    await query.edit_message_text(f"🗑 Слово «{word}» удалено.")


# =====================================================
# 📋 МОИ СЛОВА
# =====================================================

async def mywords(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.first_name)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT word, translation FROM user_words WHERE user_id=%s;",
        (user_id,)
    )
    words = cur.fetchall()
    cur.close()
    conn.close()

    if not words:
        await update.message.reply_text("📭 У вас нет персональных слов.")
        return

    text = "📝 Ваши слова:\n\n"
    for w in words:
        text += f"{w['word']} — {w['translation']}\n"

    await update.message.reply_text(text)


# =====================================================
# ▶️ ЗАПУСК
# =====================================================

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("train", train))
    app.add_handler(CommandHandler("add", add))
    app.add_handler(CommandHandler("delete", delete))
    app.add_handler(CommandHandler("mywords", mywords))

    app.add_handler(CallbackQueryHandler(delete_word, pattern="^del\\|"))
    app.add_handler(CallbackQueryHandler(check_answer))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, save_word))

    print("🚀 EnglishCard бот запущен")
    app.run_polling()


if __name__ == "__main__":
    main()
