from datetime import datetime, timedelta
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal
from sqlalchemy.orm import Session

import utils
from .models import Beacon

class BeaconRepository(QObject):
    """Repository pattern for Beacon database operations with proper session management"""
    
    # Signals
    beacon_status_changed = pyqtSignal(dict)  # Emits beacon info dict when status changes
    
    def __init__(self, session_factory):
        """Initialize with session factory instead of single session"""
        super().__init__()
        self.session_factory = session_factory

    def _get_session(self) -> Session:
        """Get a new session for each operation"""
        return self.session_factory()

    def get_beacon(self, beacon_id: str) -> Optional[Beacon]:
        with self._get_session() as session:
            return session.query(Beacon).filter_by(beacon_id=beacon_id).first()

    def update_beacon_status(self, beacon_id: str, status: str, computer_name: Optional[str] = None, receiver_id: Optional[str] = None):
        previous_status = None
        with self._get_session() as session:
            beacon = session.query(Beacon).filter_by(beacon_id=beacon_id).first()
            if not beacon:
                beacon = Beacon(
                    beacon_id=beacon_id,
                    computer_name=computer_name or "Unknown",
                    status=status,
                    last_checkin=datetime.now(),
                    receiver_id=receiver_id
                )
                session.add(beacon)
            else:
                previous_status = beacon.status
                beacon.status = status
                beacon.last_checkin = datetime.now()
                if computer_name:
                    beacon.computer_name = computer_name
                if receiver_id:
                    beacon.receiver_id = receiver_id
            session.commit()
            
            # Emit signal if status actually changed
            if previous_status != status:
                beacon_info = {
                    'beacon_id': beacon_id,
                    'computer_name': beacon.computer_name,
                    'status': status,
                    'previous_status': previous_status,
                    'receiver_id': beacon.receiver_id
                }
                self.beacon_status_changed.emit(beacon_info)
                print(f"[TRIGGER DEBUG] Emitted beacon_status_changed signal: {beacon_id} ({beacon.computer_name}) {previous_status} -> {status}")

    def update_beacon_command(self, beacon_id: str, command: Optional[str]):
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                beacon.pending_command = command
                session.commit()
                if not command == None and utils.logger:
                    utils.logger.log_message(f"Command Scheduled: {beacon_id} - {command}")

    def update_beacon_response(self, beacon_id: str, response: str):
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                beacon.last_response = response
                session.commit()

    def get_all_beacons(self) -> List[Beacon]:
        with self._get_session() as session:
            return session.query(Beacon).all()
    
    def get_online_beacons_count(self) -> int:
        """Get count of beacons with online status"""
        with self._get_session() as session:
            return session.query(Beacon).filter_by(status='online').count()

    def mark_timed_out_beacons(self, timeout_minutes: int):
        with self._get_session() as session:
            timeout = datetime.now() - timedelta(minutes=timeout_minutes)
            beacons = session.query(Beacon).filter(
                Beacon.status == 'online',
                Beacon.last_checkin < timeout
            ).all()
            for beacon in beacons:
                previous_status = beacon.status
                beacon.status = 'offline'
                # Emit signal for each beacon that timed out
                beacon_info = {
                    'beacon_id': beacon.beacon_id,
                    'computer_name': beacon.computer_name,
                    'status': 'offline',
                    'previous_status': previous_status,
                    'receiver_id': beacon.receiver_id
                }
                self.beacon_status_changed.emit(beacon_info)
                print(f"[TRIGGER DEBUG] Emitted beacon_status_changed signal (timeout): {beacon.beacon_id} ({beacon.computer_name}) {previous_status} -> offline")
            session.commit()

    def delete_beacon(self, beacon_id: str) -> bool:
        """
        Delete a beacon from the database.
        Returns True if beacon was found and deleted, False if beacon wasn't found.
        """
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                session.delete(beacon)
                session.commit()
                return True
            return False
    
    def update_beacon_schema(self, beacon_id: str, schema_file: Optional[str]) -> bool:
        """Update a beacon's associated schema file"""
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                beacon.schema_file = schema_file
                session.commit()
                return True
            return False
    
    def get_beacon_schema(self, beacon_id: str) -> Optional[str]:
        """Get a beacon's associated schema file"""
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                return beacon.schema_file
            return None

    def get_online_beacons_count_by_receiver(self, receiver_id: str) -> int:
        """Get count of online beacons for a specific receiver"""
        with self._get_session() as session:
            return session.query(Beacon).filter_by(status='online', receiver_id=receiver_id).count()