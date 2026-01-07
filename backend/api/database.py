"""SQLite database for conversation persistence."""

import sqlite3
import json
import threading
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path
from contextlib import contextmanager

from utils.logger import get_logger
from utils.paths import get_database_path

logger = get_logger(__name__)

# Database file path - uses platform-specific user directory when packaged
DB_PATH = get_database_path()


class Database:
    """Thread-safe SQLite database wrapper."""

    _instance: Optional['Database'] = None
    _lock = threading.Lock()

    def __new__(cls) -> 'Database':
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Ensure data directory exists
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Thread-local connections
        self._local = threading.local()
        self._db_path = str(DB_PATH)

        # Initialize database schema
        self._init_schema()
        self._initialized = True
        logger.info(f"Database initialized at {self._db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'conn') or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
        return self._local.conn

    @contextmanager
    def get_cursor(self):
        """Get a cursor with automatic commit/rollback."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()

    def _init_schema(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self._db_path)
        try:
            cursor = conn.cursor()

            # Conversations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    title TEXT NOT NULL DEFAULT 'New Repo',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    provider TEXT NOT NULL DEFAULT 'glm',
                    model_name TEXT NOT NULL DEFAULT 'glm-4.6',
                    system_prompt TEXT,
                    metadata TEXT
                )
            """)

            # Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL DEFAULT '',
                    timestamp TEXT NOT NULL,
                    model_used TEXT,
                    provider_used TEXT,
                    tokens_used INTEGER,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                ON messages(conversation_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversations_user_id
                ON conversations(user_id)
            """)

            # Credentials table for storing API tokens
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.commit()
            logger.info("Database schema initialized")
        finally:
            conn.close()

    # ============ Conversation Operations ============

    def create_conversation(self, conv_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new conversation."""
        now = datetime.utcnow().isoformat()
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO conversations (id, user_id, title, created_at, updated_at,
                                          provider, model_name, system_prompt, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                conv_id,
                data.get('user_id', 'default'),
                data.get('title', 'New Repo'),
                now,
                now,
                data.get('provider', 'glm'),
                data.get('model_name', 'glm-4.6'),
                data.get('system_prompt'),
                data.get('metadata')
            ))

        return self.get_conversation(conv_id)

    def get_conversation(self, conv_id: str) -> Optional[Dict[str, Any]]:
        """Get a conversation by ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM conversations WHERE id = ?", (conv_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_all_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all conversations for a user with message counts."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT c.*, COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
            """, (user_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_conversation(self, conv_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update a conversation."""
        # Build SET clause dynamically
        allowed_fields = ['title', 'provider', 'model_name', 'system_prompt', 'metadata', 'updated_at']
        set_parts = []
        values = []

        for field in allowed_fields:
            if field in updates:
                set_parts.append(f"{field} = ?")
                values.append(updates[field])

        if not set_parts:
            return self.get_conversation(conv_id)

        values.append(conv_id)

        with self.get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE conversations
                SET {', '.join(set_parts)}
                WHERE id = ?
            """, values)

        return self.get_conversation(conv_id)

    def delete_conversation(self, conv_id: str) -> bool:
        """Delete a conversation and its messages."""
        with self.get_cursor() as cursor:
            # Delete messages first (foreign key)
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
            cursor.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
            return cursor.rowcount > 0

    def conversation_exists(self, conv_id: str) -> bool:
        """Check if a conversation exists."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT 1 FROM conversations WHERE id = ? LIMIT 1", (conv_id,))
            return cursor.fetchone() is not None

    # ============ Message Operations ============

    def add_message(self, conv_id: str, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Add a message to a conversation."""
        if not self.conversation_exists(conv_id):
            return None

        now = datetime.utcnow().isoformat()

        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO messages (id, conversation_id, role, content, timestamp,
                                     model_used, provider_used, tokens_used)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message['id'],
                conv_id,
                message['role'],
                message.get('content', ''),
                message.get('timestamp', now),
                message.get('model_used'),
                message.get('provider_used'),
                message.get('tokens_used')
            ))

            # Update conversation timestamp
            cursor.execute("""
                UPDATE conversations SET updated_at = ? WHERE id = ?
            """, (now, conv_id))

        return self.get_message(message['id'])

    def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get a message by ID."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT * FROM messages WHERE id = ?", (message_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_messages(self, conv_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a conversation."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                SELECT * FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conv_id,))
            return [dict(row) for row in cursor.fetchall()]

    def update_message(self, conv_id: str, message_id: str, content: str) -> Optional[Dict[str, Any]]:
        """Update a message's content."""
        with self.get_cursor() as cursor:
            cursor.execute("""
                UPDATE messages SET content = ?
                WHERE id = ? AND conversation_id = ?
            """, (content, message_id, conv_id))

            if cursor.rowcount > 0:
                return self.get_message(message_id)
        return None

    # ============ Credentials Operations ============

    def save_credential(self, key: str, value: str) -> bool:
        """Save or update a credential."""
        now = datetime.utcnow().isoformat()
        with self.get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO credentials (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
            """, (key, value, now))
            return True

    def get_credential(self, key: str) -> Optional[str]:
        """Get a credential value by key."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT value FROM credentials WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row['value']
        return None

    def get_all_credentials(self) -> Dict[str, str]:
        """Get all stored credentials."""
        with self.get_cursor() as cursor:
            cursor.execute("SELECT key, value FROM credentials")
            return {row['key']: row['value'] for row in cursor.fetchall()}

    def delete_credential(self, key: str) -> bool:
        """Delete a credential."""
        with self.get_cursor() as cursor:
            cursor.execute("DELETE FROM credentials WHERE key = ?", (key,))
            return cursor.rowcount > 0


# Global database instance
_db: Optional[Database] = None


def get_database() -> Database:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = Database()
    return _db
