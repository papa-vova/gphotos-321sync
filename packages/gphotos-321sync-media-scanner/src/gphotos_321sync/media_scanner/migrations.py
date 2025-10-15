"""Database migration system for schema versioning."""

import logging
from pathlib import Path
from typing import Optional, List
import sqlite3

from .database import DatabaseConnection

logger = logging.getLogger(__name__)


class MigrationRunner:
    """
    Manages database schema migrations.
    
    Features:
    - Tracks schema version
    - Applies migrations in order
    - Idempotent (safe to run multiple times)
    - Transactional (all-or-nothing)
    """
    
    def __init__(self, db: DatabaseConnection, schema_dir: Path):
        """
        Initialize migration runner.
        
        Args:
            db: Database connection
            schema_dir: Directory containing migration SQL files
        """
        self.db = db
        self.schema_dir = schema_dir
        
    def get_current_version(self) -> int:
        """
        Get current schema version from database.
        
        Returns:
            Current version number (0 if schema_version table doesn't exist)
        """
        try:
            cursor = self.db.execute(
                "SELECT MAX(version) as version FROM schema_version"
            )
            row = cursor.fetchone()
            cursor.close()
            
            if row and row['version'] is not None:
                version = row['version']
                logger.debug(f"Current schema version: {version}")
                return version
            return 0
        except sqlite3.OperationalError:
            # schema_version table doesn't exist yet
            logger.debug("schema_version table not found, assuming version 0")
            return 0
    
    def _get_available_migrations(self) -> List[tuple[int, Path]]:
        """
        Get list of available migration files.
        
        Returns:
            List of (version, path) tuples sorted by version
        """
        migrations = []
        
        if not self.schema_dir.exists():
            logger.warning(f"Schema directory not found: {self.schema_dir}")
            return migrations
        
        # Find all SQL files matching pattern: NNN_*.sql
        for sql_file in self.schema_dir.glob("*.sql"):
            try:
                # Extract version number from filename (e.g., "001_initial_schema.sql" -> 1)
                version_str = sql_file.stem.split('_')[0]
                version = int(version_str)
                migrations.append((version, sql_file))
            except (ValueError, IndexError):
                logger.warning(f"Skipping invalid migration file: {sql_file.name}")
                continue
        
        # Sort by version number
        migrations.sort(key=lambda x: x[0])
        
        logger.debug(f"Found {len(migrations)} migration files")
        return migrations
    
    def apply_migrations(self, target_version: Optional[int] = None):
        """
        Apply pending migrations up to target version.
        
        Args:
            target_version: Version to migrate to (None = latest)
            
        Raises:
            sqlite3.Error: If migration fails
        """
        current_version = self.get_current_version()
        available_migrations = self._get_available_migrations()
        
        if not available_migrations:
            logger.info("No migrations found")
            return
        
        # Determine target version
        if target_version is None:
            target_version = max(v for v, _ in available_migrations)
        
        logger.info(f"Current version: {current_version}, Target version: {target_version}")
        
        # Filter migrations to apply
        pending_migrations = [
            (version, path) for version, path in available_migrations
            if current_version < version <= target_version
        ]
        
        if not pending_migrations:
            logger.info("No pending migrations")
            return
        
        logger.info(f"Applying {len(pending_migrations)} migration(s)")
        
        # Apply each migration in a transaction
        for version, migration_path in pending_migrations:
            self._apply_migration(version, migration_path)
        
        logger.info(f"Successfully migrated to version {target_version}")
    
    def _apply_migration(self, version: int, migration_path: Path):
        """
        Apply a single migration file.
        
        Args:
            version: Migration version number
            migration_path: Path to migration SQL file
            
        Raises:
            sqlite3.Error: If migration fails
        """
        logger.info(f"Applying migration {version}: {migration_path.name}")
        
        # Read migration SQL
        try:
            sql = migration_path.read_text(encoding='utf-8')
        except IOError as e:
            logger.error(f"Failed to read migration file: {e}")
            raise
        
        # Apply migration in a transaction
        try:
            with self.db.transaction() as cursor:
                # Execute migration SQL
                # Note: executescript doesn't support parameters, but migrations shouldn't need them
                cursor.executescript(sql)
                
                logger.debug(f"Migration {version} executed successfully")
                
        except sqlite3.Error as e:
            logger.error(f"Failed to apply migration {version}: {e}")
            raise
    
    def verify_schema(self) -> bool:
        """
        Verify that database schema matches expected version.
        
        Returns:
            True if schema is up to date, False otherwise
        """
        current_version = self.get_current_version()
        available_migrations = self._get_available_migrations()
        
        if not available_migrations:
            logger.warning("No migrations found, cannot verify schema")
            return False
        
        latest_version = max(v for v, _ in available_migrations)
        
        if current_version < latest_version:
            logger.warning(
                f"Schema out of date: current={current_version}, latest={latest_version}"
            )
            return False
        
        logger.info(f"Schema is up to date: version {current_version}")
        return True
    
    def reset_database(self):
        """
        Drop all tables and reset database.
        
        WARNING: This will delete all data!
        """
        logger.warning("Resetting database - all data will be lost!")
        
        # Get list of all tables
        cursor = self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row['name'] for row in cursor.fetchall()]
        cursor.close()
        
        # Drop all tables
        with self.db.transaction() as cursor:
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.debug(f"Dropped table: {table}")
        
        logger.info("Database reset complete")
