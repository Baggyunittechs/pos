import sqlite3


#create db file
conn = sqlite3.connect("users.db")
cursor = conn.cursor()

#create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, 
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,
    reset_token TEXT,
    reset_token_expiry INTEGER,
    created_at INTEGER NOT NULL
    )
""")

conn.commit()
conn.close()

print("database created")