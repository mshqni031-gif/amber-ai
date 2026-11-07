import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chats.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the SQLite database tables."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                user_ip TEXT,
                title TEXT,
                user_name TEXT DEFAULT '',
                user_avatar TEXT DEFAULT '',
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)
        
        # Check and add user_name and user_avatar if missing in existing database
        cursor.execute("PRAGMA table_info(sessions)")
        existing_cols = [col["name"] for col in cursor.fetchall()]
        if "user_name" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE sessions ADD COLUMN user_name TEXT DEFAULT ''")
            except Exception:
                pass
        if "user_avatar" not in existing_cols:
            try:
                cursor.execute("ALTER TABLE sessions ADD COLUMN user_avatar TEXT DEFAULT ''")
            except Exception:
                pass

        conn.commit()

def save_message(session_id: str, role: str, content: str, user_ip: str = "127.0.0.1", title: Optional[str] = None, user_name: Optional[str] = None, user_avatar: Optional[str] = None):
    """Saves a message and ensures session exists in database."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if session exists
        cursor.execute("SELECT session_id, title, user_name FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        
        if not row:
            # Auto-title from user's first message
            session_title = title or (content[:35] + ("..." if len(content) > 35 else "")) if role == "user" else "New chat"
            cursor.execute(
                "INSERT INTO sessions (session_id, user_ip, title, user_name, user_avatar, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (session_id, user_ip, session_title, user_name or "", user_avatar or "", now, now)
            )
        else:
            # Update session's updated_at and title/user_name
            current_title = row["title"]
            new_title = current_title
            if (current_title == "New chat" or not current_title) and role == "user":
                new_title = content[:35] + ("..." if len(content) > 35 else "")
            
            cursor.execute(
                "UPDATE sessions SET updated_at = ?, title = ?, user_name = COALESCE(NULLIF(?, ''), user_name) WHERE session_id = ?",
                (now, new_title, user_name or "", session_id)
            )
            
        # Insert message
        cursor.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )
        conn.commit()

def get_all_sessions() -> List[Dict]:
    """Returns all chat sessions with summary stats for the Admin Panel."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                s.session_id, 
                s.user_ip, 
                s.title, 
                s.created_at, 
                s.updated_at,
                COUNT(m.id) as message_count,
                (SELECT content FROM messages WHERE session_id = s.session_id ORDER BY id DESC LIMIT 1) as last_message,
                (SELECT role FROM messages WHERE session_id = s.session_id ORDER BY id DESC LIMIT 1) as last_role
            FROM sessions s
            LEFT JOIN messages m ON s.session_id = m.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def get_session_details(session_id: str) -> Optional[Dict]:
    """Returns full metadata and all messages for a specific session."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        session = cursor.fetchone()
        if not session:
            return None
        
        cursor.execute(
            "SELECT id, role, content, timestamp FROM messages WHERE session_id = ? ORDER BY id ASC",
            (session_id,)
        )
        messages = [dict(m) for m in cursor.fetchall()]
        
        res = dict(session)
        res["messages"] = messages
        return res

def get_admin_stats() -> Dict:
    """Returns high-level statistics for Admin Dashboard."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sessions")
        total_sessions = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]
        
        today = datetime.now().strftime("%Y-%m-%d")
        cursor.execute("SELECT COUNT(*) FROM messages WHERE timestamp LIKE ?", (f"{today}%",))
        today_messages = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(DISTINCT user_ip) FROM sessions")
        unique_users = cursor.fetchone()[0]
        
        return {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "today_messages": today_messages,
            "unique_users": unique_users
        }

def delete_session(session_id: str):
    """Deletes a session and associated messages."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        conn.commit()

def delete_multiple_sessions(session_ids: List[str]) -> int:
    """Deletes multiple sessions and associated messages in a single transaction."""
    if not session_ids:
        return 0
    with get_connection() as conn:
        cursor = conn.cursor()
        placeholders = ",".join("?" for _ in session_ids)
        cursor.execute(f"DELETE FROM messages WHERE session_id IN ({placeholders})", session_ids)
        cursor.execute(f"DELETE FROM sessions WHERE session_id IN ({placeholders})", session_ids)
        conn.commit()
        return len(session_ids)

def get_all_client_sessions() -> List[Dict]:
    """Returns all chat sessions and their messages for client history recovery."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT session_id, title, user_name, created_at, updated_at FROM sessions ORDER BY updated_at DESC LIMIT 60")
        sessions = [dict(r) for r in cursor.fetchall()]
        for s in sessions:
            cursor.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (s["session_id"],))
            s["messages"] = [dict(m) for m in cursor.fetchall()]
        return sessions
