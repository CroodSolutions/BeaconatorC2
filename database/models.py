from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import DateTime, String, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """SQLAlchemy Base class for all models"""
    pass

class Beacon(Base):
    """Beacon database model"""
    __tablename__ = 'beacon'

    id: Mapped[int] = mapped_column(primary_key=True)
    beacon_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    computer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, default='online')
    last_checkin: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    pending_command: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_executed_command: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Track last executed command for parsing
    output_file: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_response: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    schema_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # Beacon schema file location
    receiver_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # ID of receiver beacon connected through
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IP address of beacon connection

    def to_dict(self) -> Dict[str, Any]:
        """Convert beacon to dictionary representation"""
        return {
            'beacon_id': self.beacon_id,
            'computer_name': self.computer_name,
            'status': self.status,
            'last_checkin': self.last_checkin.strftime("%Y-%m-%d %H:%M:%S %z"),
            'ip_address': self.ip_address
        }


class BeaconMetadata(Base):
    """Stores parsed metadata from beacon command outputs"""
    __tablename__ = 'beacon_metadata'

    id: Mapped[int] = mapped_column(primary_key=True)
    beacon_id: Mapped[str] = mapped_column(String(80), ForeignKey('beacon.beacon_id', ondelete='CASCADE'), nullable=False, index=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    source_command: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

    # Composite index for fast lookups
    __table_args__ = (
        Index('idx_beacon_key', 'beacon_id', 'key'),
    )