CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    tg_id BIGINT UNIQUE NOT NULL,
    first_name TEXT
);

CREATE TABLE words (
    id SERIAL PRIMARY KEY,
    word TEXT NOT NULL,
    translation TEXT NOT NULL
);

CREATE TABLE user_words (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    translation TEXT NOT NULL
);

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
