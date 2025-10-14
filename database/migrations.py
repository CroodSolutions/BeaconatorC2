from sqlalchemy import create_engine, inspect, text
from typing import List
import logging

class DatabaseMigration:
    """Handles database schema migrations"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')

    def get_table_columns(self, table_name: str) -> List[str]:
        """Get list of column names for a table"""
        inspector = inspect(self.engine)
        columns = inspector.get_columns(table_name)
        return [col['name'] for col in columns]

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists"""
        inspector = inspect(self.engine)
        return table_name in inspector.get_table_names()

    def apply_migrations(self):
        """Apply all necessary database migrations"""
        migrations_applied = []

        # Check if beacon table exists
        if not self.table_exists('beacon'):
            # Table doesn't exist yet, create_all will handle it
            return migrations_applied

        # Get current columns
        columns = self.get_table_columns('beacon')

        # Migration 1: Add ip_address column if it doesn't exist
        if 'ip_address' not in columns:
            self._add_ip_address_column()
            migrations_applied.append('add_ip_address_to_beacon')

        # Migration 2: Add last_executed_command column if it doesn't exist
        if 'last_executed_command' not in columns:
            self._add_last_executed_command_column()
            migrations_applied.append('add_last_executed_command_to_beacon')

        # Migration 3: Create beacon_metadata table if it doesn't exist
        if not self.table_exists('beacon_metadata'):
            self._create_beacon_metadata_table()
            migrations_applied.append('create_beacon_metadata_table')

        return migrations_applied

    def _add_ip_address_column(self):
        """Add ip_address column to beacon table"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text('ALTER TABLE beacon ADD COLUMN ip_address VARCHAR(45)'))
                conn.commit()
                logging.info("Migration applied: Added ip_address column to beacon table")
        except Exception as e:
            logging.error(f"Failed to add ip_address column: {e}")
            raise

    def _add_last_executed_command_column(self):
        """Add last_executed_command column to beacon table"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text('ALTER TABLE beacon ADD COLUMN last_executed_command VARCHAR(200)'))
                conn.commit()
                logging.info("Migration applied: Added last_executed_command column to beacon table")
        except Exception as e:
            logging.error(f"Failed to add last_executed_command column: {e}")
            raise

    def _create_beacon_metadata_table(self):
        """Create beacon_metadata table"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text('''
                    CREATE TABLE beacon_metadata (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        beacon_id VARCHAR(80) NOT NULL,
                        key VARCHAR(100) NOT NULL,
                        value VARCHAR(500) NOT NULL,
                        source_command VARCHAR(200),
                        collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (beacon_id) REFERENCES beacon(beacon_id) ON DELETE CASCADE
                    )
                '''))
                # Create indexes
                conn.execute(text('CREATE INDEX idx_beacon_metadata_beacon_id ON beacon_metadata(beacon_id)'))
                conn.execute(text('CREATE INDEX idx_beacon_metadata_key ON beacon_metadata(key)'))
                conn.execute(text('CREATE INDEX idx_beacon_key ON beacon_metadata(beacon_id, key)'))
                conn.commit()
                logging.info("Migration applied: Created beacon_metadata table with indexes")
        except Exception as e:
            logging.error(f"Failed to create beacon_metadata table: {e}")
            raise

def apply_database_migrations(db_path: str) -> List[str]:
    """
    Apply all database migrations

    Args:
        db_path: Path to the SQLite database file

    Returns:
        List of migration names that were applied
    """
    migration = DatabaseMigration(db_path)
    return migration.apply_migrations()
