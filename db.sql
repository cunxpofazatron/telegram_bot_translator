-- =========================================
-- СХЕМА БАЗЫ ДАННЫХ ДЛЯ БОТА EnglishCard
-- =========================================

-- Таблица пользователей Telegram
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE NOT NULL,
    first_name TEXT
);

-- Общий словарь (доступен всем пользователям)
CREATE TABLE IF NOT EXISTS words (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL UNIQUE,
    translation TEXT NOT NULL
);

-- Персональные слова пользователей
CREATE TABLE IF NOT EXISTS user_words (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    translation TEXT NOT NULL,
    UNIQUE (user_id, word)
);

-- =========================================
-- НАЧАЛЬНЫЙ НАБОР СЛОВ (10 ШТУК)
-- =========================================

INSERT INTO words (word, translation) VALUES
('red', 'красный'),
('blue', 'синий'),
('green', 'зелёный'),
('yellow', 'жёлтый'),
('black', 'чёрный'),
('white', 'белый'),
('i', 'я'),
('you', 'ты'),
('he', 'он'),
('she', 'она')
ON CONFLICT DO NOTHING;
