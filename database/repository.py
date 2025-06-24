from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
from .models import Agent

class AgentRepository:
    """Repository pattern for Agent database operations with proper session management"""
    def __init__(self, session_factory):
        """Initialize with session factory instead of single session"""
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """Get a new session for each operation"""
        return self.session_factory()

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        with self._get_session() as session:
            return session.query(Agent).filter_by(agent_id=agent_id).first()

    def update_agent_status(self, agent_id: str, status: str, computer_name: Optional[str] = None):
        with self._get_session() as session:
            agent = session.query(Agent).filter_by(agent_id=agent_id).first()
            if not agent:
                agent = Agent(
                    agent_id=agent_id,
                    computer_name=computer_name or "Unknown",
                    status=status,
                    last_checkin=datetime.now()
                )
                session.add(agent)
            else:
                agent.status = status
                agent.last_checkin = datetime.now()
                if computer_name:
                    agent.computer_name = computer_name
            session.commit()

    def update_agent_command(self, agent_id: str, command: Optional[str]):
        import utils  # Import here to avoid circular imports
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                agent.pending_command = command
                session.commit()
                if not command == None and utils.logger:
                    utils.logger.log_message(f"Command Scheduled: {agent_id} - {command}")

    def update_agent_response(self, agent_id: str, response: str):
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                agent.last_response = response
                session.commit()

    def get_all_agents(self) -> List[Agent]:
        with self._get_session() as session:
            return session.query(Agent).all()

    def mark_timed_out_agents(self, timeout_minutes: int):
        with self._get_session() as session:
            timeout = datetime.now() - timedelta(minutes=timeout_minutes)
            agents = session.query(Agent).filter(
                Agent.status == 'online',
                Agent.last_checkin < timeout
            ).all()
            for agent in agents:
                agent.status = 'offline'
            session.commit()

    def delete_agent(self, agent_id: str) -> bool:
        """
        Delete an agent from the database.
        Returns True if agent was found and deleted, False if agent wasn't found.
        """
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                session.delete(agent)
                session.commit()
                return True
            return False
    
    def update_beacon_schema(self, agent_id: str, schema_file: Optional[str]) -> bool:
        """Update a beacon's associated schema file"""
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                agent.schema_file = schema_file
                session.commit()
                return True
            return False
    
    def get_beacon_schema(self, agent_id: str) -> Optional[str]:
        """Get a beacon's associated schema file"""
        with self._get_session() as session:
            if agent := session.query(Agent).filter_by(agent_id=agent_id).first():
                return agent.schema_file
            return None