from PyQt6.QtCore import QThread, pyqtSignal
from database import BeaconRepository

class BeaconUpdateWorker(QThread):
    """Background worker to update beacon statuses"""
    beacon_updated = pyqtSignal(list)

    def __init__(self, beacon_repository: BeaconRepository):
        super().__init__()
        self.beacon_repository = beacon_repository
        self._running = True  # Add running flag

    def run(self):
        import utils  # Import here to avoid circular imports
        from config import ServerConfig  # Import ServerConfig
        config = ServerConfig()  # Get timeout value
        
        while self._running:  # Use running flag
            try:
                # Mark timed out beacons BEFORE fetching all beacons
                self.beacon_repository.mark_timed_out_beacons(config.BEACON_TIMEOUT_MINUTES)
                
                # Then get updated beacon list
                beacons = self.beacon_repository.get_all_beacons()
                self.beacon_updated.emit([beacon.to_dict() for beacon in beacons])
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Error updating beacons: {e}")
            self.msleep(1000)  # 1 second delay

    def stop(self):  # Implement stop method
        self._running = False
        self.wait()  # Wait for the thread to finish