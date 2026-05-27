import sqlite3

def get_user(user_id):
    conn = sqlite3.connect("users.db")
    query = f"SELECT * FROM users WHERE id={user_id}"
    return conn.execute(query)

def login(username, password):
    if password == "admin123":
        return True
    return False