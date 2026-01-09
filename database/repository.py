from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QObject, pyqtSignal
from sqlalchemy.orm import Session

import utils
from .models import Beacon, BeaconMetadata

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

    def update_beacon_status(self, beacon_id: str, status: str, computer_name: Optional[str] = None, receiver_id: Optional[str] = None, ip_address: Optional[str] = None):
        previous_status = None
        with self._get_session() as session:
            beacon = session.query(Beacon).filter_by(beacon_id=beacon_id).first()
            if not beacon:
                beacon = Beacon(
                    beacon_id=beacon_id,
                    computer_name=computer_name or "Unknown",
                    status=status,
                    last_checkin=datetime.now(),
                    receiver_id=receiver_id,
                    ip_address=ip_address
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
                if ip_address:
                    beacon.ip_address = ip_address
            session.commit()

            # Emit signal if status actually changed
            if previous_status != status:
                beacon_info = {
                    'beacon_id': beacon_id,
                    'computer_name': beacon.computer_name,
                    'status': status,
                    'previous_status': previous_status,
                    'receiver_id': beacon.receiver_id,
                    'ip_address': beacon.ip_address
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
                    'receiver_id': beacon.receiver_id,
                    'ip_address': beacon.ip_address
                }
                self.beacon_status_changed.emit(beacon_info)
                print(f"[TRIGGER DEBUG] Emitted beacon_status_changed signal (timeout): {beacon.beacon_id} ({beacon.computer_name}) {previous_status} -> offline")
            session.commit()

    def delete_beacon(self, beacon_id: str) -> bool:
        """
        Delete a beacon and all associated data from the database.
        This includes:
        - The beacon record itself
        - All associated BeaconMetadata records

        Returns True if beacon was found and deleted, False if beacon wasn't found.
        """
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                # Delete all associated metadata first
                session.query(BeaconMetadata).filter_by(beacon_id=beacon_id).delete()
                # Delete the beacon record
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

    def update_last_executed_command(self, beacon_id: str, command: str) -> bool:
        """Update the last executed command for a beacon (used for output parsing)"""
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                beacon.last_executed_command = command
                session.commit()
                return True
            return False

    def get_last_executed_command(self, beacon_id: str) -> Optional[str]:
        """Get the last executed command for a beacon"""
        with self._get_session() as session:
            if beacon := session.query(Beacon).filter_by(beacon_id=beacon_id).first():
                return beacon.last_executed_command
            return None

    def store_beacon_metadata(self, beacon_id: str, metadata: List[Tuple[str, str]], source_command: Optional[str] = None):
        """
        Store metadata for a beacon

        Args:
            beacon_id: The beacon ID
            metadata: List of (key, value) tuples
            source_command: Optional command that produced this metadata
        """
        with self._get_session() as session:
            for key, value in metadata:
                # Check if metadata already exists for this beacon and key
                existing = session.query(BeaconMetadata).filter_by(
                    beacon_id=beacon_id,
                    key=key
                ).first()

                if existing:
                    # Update existing metadata
                    existing.value = value
                    existing.source_command = source_command
                    existing.collected_at = datetime.now()
                else:
                    # Create new metadata entry
                    metadata_entry = BeaconMetadata(
                        beacon_id=beacon_id,
                        key=key,
                        value=value,
                        source_command=source_command,
                        collected_at=datetime.now()
                    )
                    session.add(metadata_entry)

            session.commit()

    def get_beacon_metadata(self, beacon_id: str, key: Optional[str] = None) -> Dict[str, str]:
        """
        Get metadata for a beacon, optionally filtered by key

        Args:
            beacon_id: The beacon ID
            key: Optional specific key to retrieve

        Returns:
            Dictionary of key-value pairs
        """
        with self._get_session() as session:
            query = session.query(BeaconMetadata).filter_by(beacon_id=beacon_id)

            if key:
                query = query.filter_by(key=key)

            results = query.all()
            return {item.key: item.value for item in results}

    def get_beacon_metadata_with_details(self, beacon_id: str) -> List[Dict[str, any]]:
        """
        Get metadata for a beacon with full details (timestamp, source command)

        Args:
            beacon_id: The beacon ID

        Returns:
            List of dictionaries with metadata details
        """
        with self._get_session() as session:
            results = session.query(BeaconMetadata).filter_by(beacon_id=beacon_id).all()
            return [{
                'key': item.key,
                'value': item.value,
                'source_command': item.source_command,
                'collected_at': item.collected_at
            } for item in results]

    def delete_beacon_metadata(self, beacon_id: str, key: Optional[str] = None) -> bool:
        """
        Delete metadata for a beacon

        Args:
            beacon_id: The beacon ID
            key: Optional specific key to delete (if None, deletes all metadata for beacon)

        Returns:
            True if metadata was deleted
        """
        with self._get_session() as session:
            query = session.query(BeaconMetadata).filter_by(beacon_id=beacon_id)

            if key:
                query = query.filter_by(key=key)

            deleted_count = query.delete()
            session.commit()
            return deleted_count > 0

    def search_beacons_by_metadata(self, metadata_filter: Dict[str, str]) -> List[Beacon]:
        """
        Search for beacons that match specific metadata criteria

        Args:
            metadata_filter: Dictionary of key-value pairs to match

        Returns:
            List of beacons matching all criteria
        """
        with self._get_session() as session:
            query = session.query(Beacon)

            for key, value in metadata_filter.items():
                # Join with metadata table for each filter
                query = query.join(BeaconMetadata, Beacon.beacon_id == BeaconMetadata.beacon_id).filter(
                    BeaconMetadata.key == key,
                    BeaconMetadata.value == value
                )

            return query.all()