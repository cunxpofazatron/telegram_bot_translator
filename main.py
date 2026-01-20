#!/usr/bin/env python3
"""
Telegram-бот EnglishCard
Изучение английских слов с использованием PostgreSQL
"""

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
# 🚀 КОМАНДЫ
# =====================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_or_create_user(user.id, user.first_name)

    await update.message.reply_text(
        f"👋 Привет, {user.first_name}!\n\n"
        "📚 Я бот для изучения английских слов.\n\n"
        "Команды:\n"
        "/train — тренировка\n"
        "/add — добавить слово\n"
        "/delete — удалить слово\n"
        "/mywords — мои слова\n"
        "/help — помощь"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ Выбери правильный перевод слова из 4 вариантов.\n"
        "Добавленные слова видны только тебе."
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
        SELECT word, translation
        FROM (
            SELECT word, translation FROM words
            UNION
            SELECT word, translation FROM user_words WHERE user_id=%s
        ) t
        ORDER BY RANDOM()
        LIMIT 4;
    """, (user_id,))

    words = cur.fetchall()
    cur.close()
    conn.close()

    correct = random.choice(words)
    translations = [w["translation"] for w in words]
    random.shuffle(translations)

    buttons = [
        [InlineKeyboardButton(t, callback_data=f"{correct['word']}|{t}")]
        for t in translations
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
# ➕ ДОБАВЛЕНИЕ СЛОВ
# =====================================================

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Введите слово и перевод через пробел:\n"
        "apple яблоко\n\n"
        "Для выхода напишите: Назад"
    )


async def save_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()

    if text.lower().startswith("назад"):
        await update.message.reply_text("📘 Вы в главном меню")
        return

    if text.startswith("/"):
        return

    try:
        word, translation = text.split(" ", 1)
    except ValueError:
        await update.message.reply_text("❌ Формат: слово перевод")
        return

    user = update.effective_user
    user_id = get_or_create_user(user.id, user.first_name)

    conn = get_db()
    cur = conn.cursor()

    # Проверка на дубли
    cur.execute("""
        SELECT 1 FROM words WHERE word=%s
        UNION
        SELECT 1 FROM user_words WHERE word=%s AND user_id=%s;
    """, (word, word, user_id))

    if cur.fetchone():
        await update.message.reply_text("❌ Такое слово уже существует")
        cur.close()
        conn.close()
        return

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
# ❌ УДАЛЕНИЕ
# =====================================================

async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = get_or_create_user(user.id, user.first_name)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "SELECT word FROM user_words WHERE user_id=%s;",
        (user_id,)
    )
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
