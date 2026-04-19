"""
Database connection manager for BDDK Banking Analytics Dashboard
"""

import sqlite3
from pathlib import Path
from typing import Optional
import pandas as pd

class DatabaseManager:
    """Manages database connections and queries"""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize database manager

        Args:
            db_path: Path to SQLite database. If None, uses default path.
        """
        if db_path is None:
            # Default path: data/bddk_data.db
            base_dir = Path(__file__).parent.parent.parent.parent
            db_path = base_dir / 'data' / 'bddk_data.db'

        self.db_path = str(db_path)
        self._connection: Optional[sqlite3.Connection] = None

    def get_connection(self) -> sqlite3.Connection:
        """Get database connection (creates if doesn't exist)"""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path, check_same_thread=False)
        return self._connection

    def execute_query(self, query: str, params: tuple = None) -> pd.DataFrame:
        """Execute SQL query and return DataFrame

        Args:
            query: SQL query string
            params: Optional query parameters

        Returns:
            DataFrame with query results
        """
        conn = self.get_connection()
        if params:
            return pd.read_sql_query(query, conn, params=params)
        return pd.read_sql_query(query, conn)

    def close(self):
        """Close database connection"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()


# Global database manager instance
db_manager = DatabaseManager()
