import sqlite3

def connect():
    return sqlite3.connect("bot.db")

def init_db():
    conn = connect()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        coins INTEGER DEFAULT 1000
    )
    """)

    conn.commit()
    conn.close()

def get_user(user_id):
    conn = connect()
    c = conn.cursor()

    c.execute("SELECT coins FROM users WHERE user_id=?", (user_id,))
    data = c.fetchone()

    if not data:
        c.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        coins = 1000
    else:
        coins = data[0]

    conn.close()
    return coins

def update_coins(user_id, amount):
    conn = connect()
    c = conn.cursor()

    c.execute("UPDATE users SET coins=? WHERE user_id=?", (amount, user_id))

    conn.commit()
    conn.close()
