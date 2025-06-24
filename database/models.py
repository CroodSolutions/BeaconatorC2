from sqlalchemy import String, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from typing import Optional, Dict, Any

class Base(DeclarativeBase):
    """SQLAlchemy Base class for all models"""
    pass

class Agent(Base):
    """Agent database model"""
    __tablename__ = 'agent'
    
    id: Mapped[int] = mapped_column(primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    computer_name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(80), nullable=False, default='online')
    last_checkin: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    pending_command: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    output_file: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    last_response: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    schema_file: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)  # Beacon schema file location

    def to_dict(self) -> Dict[str, Any]:
        """Convert agent to dictionary representation"""
        return {
            'agent_id': self.agent_id,
            'computer_name': self.computer_name,
            'status': self.status,
            'last_checkin': self.last_checkin.strftime("%Y-%m-%d %H:%M:%S %z")
        }