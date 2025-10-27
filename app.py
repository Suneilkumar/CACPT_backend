from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import os

app = Flask(__name__)
CORS(app)  # allow React frontend to call this API

DB_PATH = "data.db"

# --- Database setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Routes ---
@app.route("/api/hello")
def hello():
    return jsonify(message="Hello from Flask and Sunil!")

@app.route("/api/users", methods=["POST"])
def add_user():
    data = request.get_json()
    name, email = data.get("name"), data.get("email")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO users (name, email) VALUES (?, ?)", (name, email))
    conn.commit()
    conn.close()
    return jsonify(success=True, message=f"User {name} added successfully")

@app.route("/api/users", methods=["GET"])
def get_users():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, name, email FROM users")
    users = [{"id": r[0], "name": r[1], "email": r[2]} for r in cur.fetchall()]
    conn.close()
    return jsonify(users)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
