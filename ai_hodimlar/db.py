import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("AI_HODIMLAR_DB", os.path.join(os.path.dirname(__file__), "ai_hodimlar.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS mijozlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nom TEXT NOT NULL,
    telefon TEXT DEFAULT '',
    biznes_tavsifi TEXT DEFAULT '',
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS ofislar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mijoz_id INTEGER NOT NULL REFERENCES mijozlar(id) ON DELETE CASCADE,
    nom TEXT NOT NULL,
    hajm TEXT NOT NULL DEFAULT 'kichik',
    dizayn TEXT NOT NULL DEFAULT 'klassik',
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS hodimlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ofis_id INTEGER NOT NULL REFERENCES ofislar(id) ON DELETE CASCADE,
    shablon_id TEXT NOT NULL,
    ism TEXT NOT NULL,
    qoshimcha_instruksiya TEXT DEFAULT '',
    holat TEXT DEFAULT 'bosh',
    created TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS bilimlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    shablon_id TEXT NOT NULL,
    sarlavha TEXT NOT NULL,
    xulosa TEXT DEFAULT '',
    manba TEXT NOT NULL,
    sana TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (shablon_id, manba)
);
CREATE TABLE IF NOT EXISTS xabarlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hodim_id INTEGER NOT NULL REFERENCES hodimlar(id) ON DELETE CASCADE,
    rol TEXT NOT NULL,
    matn TEXT NOT NULL,
    sana TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vazifalar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hodim_id INTEGER NOT NULL REFERENCES hodimlar(id) ON DELETE CASCADE,
    matn TEXT NOT NULL,
    holat TEXT DEFAULT 'yangi',
    natija TEXT DEFAULT '',
    created TEXT DEFAULT CURRENT_TIMESTAMP,
    done TEXT,
    topshiriq_id INTEGER
);
CREATE TABLE IF NOT EXISTS topshiriqlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ofis_id INTEGER NOT NULL REFERENCES ofislar(id) ON DELETE CASCADE,
    matn TEXT NOT NULL,
    holat TEXT DEFAULT 'yangi',
    reja TEXT DEFAULT '',
    hisobot TEXT DEFAULT '',
    chat_id TEXT,
    created TEXT DEFAULT CURRENT_TIMESTAMP,
    done TEXT
);
"""

# Eski bazalarga qo'shiladigan ustunlar: (jadval, ustun, turi)
MIGRATSIYALAR = [
    ("ofislar", "ulash_kodi", "TEXT"),
    ("ofislar", "telegram_chat_id", "TEXT"),
    ("vazifalar", "topshiriq_id", "INTEGER"),
]


def connect():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def tx():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init():
    with tx() as c:
        c.executescript(SCHEMA)
        for jadval, ustun, turi in MIGRATSIYALAR:
            if ustun not in {r["name"] for r in c.execute(f"PRAGMA table_info({jadval})")}:
                c.execute(f"ALTER TABLE {jadval} ADD COLUMN {ustun} {turi}")


def rows(sql, *args):
    with tx() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def one(sql, *args):
    r = rows(sql, *args)
    return r[0] if r else None


def run(sql, *args):
    with tx() as c:
        return c.execute(sql, args).lastrowid
