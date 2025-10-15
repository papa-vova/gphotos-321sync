"""Database connection manager for SQLite with WAL mode and proper configuration."""

import sqlite3
import logging
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Manages SQLite database connection with proper configuration.
    
    Features:
    - WAL mode for concurrent reads
    - Proper timeout and synchronous settings
    - Transaction context manager
    - Connection pooling (single connection per instance)
    """
    
    def __init__(self, db_path: Path):
        """
        Initialize database connection manager.
        
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._connection: Optional[sqlite3.Connection] = None
        
    def connect(self) -> sqlite3.Connection:
        """
        Establish database connection with proper configuration.
        
        Returns:
            SQLite connection object
            
        Raises:
            sqlite3.Error: If connection fails
        """
        if self._connection is not None:
            return self._connection
            
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create connection
        logger.info(f"Connecting to database: {self.db_path}")
        self._connection = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow multi-threaded access (WAL mode)
            timeout=5.0  # 5 second timeout on lock contention
        )
        
        # Enable row factory for dict-like access
        self._connection.row_factory = sqlite3.Row
        
        # Apply PRAGMAs for performance and concurrency
        self._apply_pragmas()
        
        logger.info("Database connection established")
        return self._connection
    
    def _apply_pragmas(self):
        """Apply SQLite PRAGMAs for optimal performance."""
        cursor = self._connection.cursor()
        
        # Write-Ahead Logging for concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        logger.debug("Set journal_mode=WAL")
        
        # Wait 5 seconds on lock contention
        cursor.execute("PRAGMA busy_timeout=5000")
        logger.debug("Set busy_timeout=5000")
        
        # Balance safety and performance
        cursor.execute("PRAGMA synchronous=NORMAL")
        logger.debug("Set synchronous=NORMAL")
        
        # 64MB cache
        cursor.execute("PRAGMA cache_size=-64000")
        logger.debug("Set cache_size=-64000")
        
        # Temp tables in RAM
        cursor.execute("PRAGMA temp_store=MEMORY")
        logger.debug("Set temp_store=MEMORY")
        
        # WAL autocheckpoint every 1000 pages
        cursor.execute("PRAGMA wal_autocheckpoint=1000")
        logger.debug("Set wal_autocheckpoint=1000")
        
        # Enable foreign keys (even though we don't use them, good practice)
        cursor.execute("PRAGMA foreign_keys=ON")
        logger.debug("Set foreign_keys=ON")
        
        cursor.close()
    
    @contextmanager
    def transaction(self):
        """
        Context manager for explicit transactions.
        
        Usage:
            with db.transaction():
                cursor.execute(...)
                cursor.execute(...)
            # Commits on success, rolls back on exception
        """
        if self._connection is None:
            self.connect()
            
        cursor = self._connection.cursor()
        try:
            cursor.execute("BEGIN")
            yield cursor
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise
        finally:
            cursor.close()
    
    def execute(self, sql: str, parameters=None):
        """
        Execute a single SQL statement.
        
        Args:
            sql: SQL statement
            parameters: Optional parameters for parameterized query
            
        Returns:
            Cursor object
        """
        if self._connection is None:
            self.connect()
            
        cursor = self._connection.cursor()
        if parameters:
            cursor.execute(sql, parameters)
        else:
            cursor.execute(sql)
        return cursor
    
    def executemany(self, sql: str, parameters):
        """
        Execute a SQL statement with multiple parameter sets.
        
        Args:
            sql: SQL statement
            parameters: Sequence of parameter tuples
            
        Returns:
            Cursor object
        """
        if self._connection is None:
            self.connect()
            
        cursor = self._connection.cursor()
        cursor.executemany(sql, parameters)
        return cursor
    
    def commit(self):
        """Commit current transaction."""
        if self._connection is not None:
            self._connection.commit()
    
    def rollback(self):
        """Rollback current transaction."""
        if self._connection is not None:
            self._connection.rollback()
    
    def close(self):
        """Close database connection."""
        if self._connection is not None:
            # Run checkpoint before closing
            try:
                cursor = self._connection.cursor()
                cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                cursor.close()
                logger.debug("WAL checkpoint completed")
            except sqlite3.Error as e:
                logger.warning(f"Failed to checkpoint WAL: {e}")
            
            self._connection.close()
            self._connection = None
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
