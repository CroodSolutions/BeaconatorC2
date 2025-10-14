"""
Metasploit Process Manager

Handles automatic startup, monitoring, and shutdown of Metasploit RPC daemon
"""

import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import utils
from config import ServerConfig


@dataclass
class MetasploitStatus:
    """Represents the current status of Metasploit RPC"""
    is_running: bool = False
    is_managed: bool = False  # Whether we started it
    process_id: Optional[int] = None
    version: Optional[str] = None
    connection_status: str = "Disconnected"
    last_check: Optional[float] = None


class MetasploitManager:
    """Manages Metasploit RPC daemon lifecycle"""
    
    def __init__(self, config: ServerConfig = None):
        self.config = config or ServerConfig()
        self._process: Optional[subprocess.Popen] = None
        self._status = MetasploitStatus()
        self._health_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._lock = threading.Lock()
        self._metasploit_service = None
        
    @property
    def status(self) -> MetasploitStatus:
        """Get current Metasploit status"""
        return self._status
    
    @property
    def metasploit_service(self):
        """Get MetasploitService instance"""
        if self._metasploit_service is None:
            from .metasploit_service import MetasploitService
            self._metasploit_service = MetasploitService(self.config)
        return self._metasploit_service
    
    def is_rpc_available(self) -> bool:
        """Check if Metasploit RPC is responding"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2.0)
                result = sock.connect_ex((self.config.MSF_RPC_HOST, self.config.MSF_RPC_PORT))
                return result == 0
        except Exception:
            return False
    
    def find_metasploit_installation(self) -> Tuple[bool, str]:
        """Find Metasploit installation and return path info"""
        try:
            # Try to find msfrpcd
            daemon_path = self.config.MSF_DAEMON_PATH
            if not os.path.isabs(daemon_path):
                # Try to find in PATH
                found_path = shutil.which(daemon_path)
                if found_path:
                    daemon_path = found_path
                else:
                    # More detailed error message with installation instructions
                    return False, (
                        f"Metasploit Framework not found. '{daemon_path}' is not available in PATH.\n\n"
                        "To install Metasploit Framework:\n"
                        "• On Kali Linux: sudo apt update && sudo apt install metasploit-framework\n"
                        "• On Ubuntu/Debian: Follow https://docs.metasploit.com/docs/using-metasploit/getting-started/nightly-installers.html\n"
                        "• On other systems: Visit https://metasploit.com/download\n\n"
                        "After installation, verify with: which msfrpcd"
                    )
            
            # Test if executable exists and is executable
            if not os.path.isfile(daemon_path):
                return False, f"msfrpcd not found at: {daemon_path}. Please verify Metasploit installation."
                
            if not os.access(daemon_path, os.X_OK):
                return False, f"msfrpcd not executable: {daemon_path}. Check file permissions."
            
            # Additional check: verify msfconsole is also available (full installation)
            if not shutil.which('msfconsole'):
                return False, (
                    f"msfrpcd found at {daemon_path}, but msfconsole is missing.\n"
                    "This indicates an incomplete Metasploit installation.\n"
                    "Please reinstall Metasploit Framework completely."
                )
            
            return True, daemon_path
            
        except Exception as e:
            return False, f"Error checking Metasploit installation: {str(e)}"
    
    def start_rpc_daemon(self) -> Tuple[bool, str]:
        """Start Metasploit RPC daemon with enhanced diagnostics"""
        if not self.config.MSF_ENABLED:
            return False, "Metasploit integration is disabled"
            
        if not self.config.MSF_AUTO_START:
            return False, "Auto-start is disabled"
        
        with self._lock:
            # Check if already running
            if self.is_rpc_available():
                self._status.is_running = True
                self._status.is_managed = False
                self._status.connection_status = "Connected (External)"
                if utils.logger:
                    utils.logger.log_message("Metasploit RPC already running")
                return True, "Metasploit RPC already running"
            
            # Find Metasploit installation
            found, path_or_error = self.find_metasploit_installation()
            if not found:
                if utils.logger:
                    utils.logger.log_message(f"Metasploit installation check failed: {path_or_error}")
                return False, path_or_error
            
            daemon_path = path_or_error
            
            try:
                if utils.logger:
                    utils.logger.log_message(f"Starting Metasploit RPC daemon: {daemon_path}")
                
                # Build command arguments
                cmd = [
                    daemon_path,
                    '-U', self.config.MSF_RPC_USER,
                    '-P', self.config.MSF_RPC_PASS,
                    '-p', str(self.config.MSF_RPC_PORT),
                    '-a', self.config.MSF_RPC_HOST
                ]
                
                if not self.config.MSF_RPC_SSL:
                    cmd.append('-n')  # Disable SSL
                
                cmd.extend(['-f'])  # Run in foreground for better process control
                
                if utils.logger:
                    utils.logger.log_message(f"RPC command: {' '.join(cmd)}")
                
                # Start the process
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    text=True,
                    start_new_session=True  # Create new process group for clean shutdown
                )
                
                if utils.logger:
                    utils.logger.log_message(f"Metasploit RPC process started (PID: {self._process.pid})")
                
                # Wait for RPC to become available
                start_time = time.time()
                timeout = self.config.MSF_STARTUP_TIMEOUT
                last_check_time = 0
                
                while time.time() - start_time < timeout:
                    current_time = time.time()
                    
                    # Log progress every 5 seconds
                    if current_time - last_check_time >= 5:
                        elapsed = current_time - start_time
                        if utils.logger:
                            utils.logger.log_message(f"Waiting for RPC to become available... ({elapsed:.1f}s/{timeout}s)")
                        last_check_time = current_time
                    
                    if self.is_rpc_available():
                        self._status.is_running = True
                        self._status.is_managed = True
                        self._status.process_id = self._process.pid
                        self._status.connection_status = "Connected (Managed)"
                        
                        if utils.logger:
                            utils.logger.log_message(f"Metasploit RPC started successfully (PID: {self._process.pid})")
                        
                        # Start health monitoring
                        self._start_health_monitoring()
                        
                        return True, f"Metasploit RPC started (PID: {self._process.pid})"
                    
                    # Check if process died
                    if self._process.poll() is not None:
                        try:
                            stdout, stderr = self._process.communicate(timeout=2)
                        except subprocess.TimeoutExpired:
                            stdout, stderr = "Process timeout", "Process timeout"
                        
                        error_msg = f"Metasploit RPC process died. Exit code: {self._process.returncode}"
                        if stdout and stdout.strip():
                            error_msg += f"\nStdout: {stdout.strip()}"
                        if stderr and stderr.strip():
                            error_msg += f"\nStderr: {stderr.strip()}"
                            
                        if utils.logger:
                            utils.logger.log_message(error_msg)
                        return False, error_msg
                    
                    time.sleep(0.5)
                
                # Timeout reached - get process output for debugging
                if self._process and self._process.poll() is None:
                    # Process is still running but RPC not available
                    try:
                        # Send SIGTERM to get output
                        self._process.terminate()
                        stdout, stderr = self._process.communicate(timeout=3)
                    except:
                        stdout, stderr = "Could not get process output", "Could not get process output"
                        
                    error_msg = f"Timeout waiting for Metasploit RPC to start ({timeout}s). Process was running but RPC not available."
                    if stdout and stdout.strip():
                        error_msg += f"\nProcess stdout: {stdout.strip()}"
                    if stderr and stderr.strip():
                        error_msg += f"\nProcess stderr: {stderr.strip()}"
                else:
                    error_msg = f"Timeout waiting for Metasploit RPC to start ({timeout}s). Process already terminated."
                
                self._kill_process()
                if utils.logger:
                    utils.logger.log_message(error_msg)
                return False, error_msg
                
            except Exception as e:
                if self._process:
                    self._kill_process()
                error_msg = f"Error starting Metasploit RPC: {str(e)}"
                if utils.logger:
                    utils.logger.log_message(error_msg)
                return False, error_msg
    
    def stop_rpc_daemon(self) -> Tuple[bool, str]:
        """Stop Metasploit RPC daemon if we started it"""
        with self._lock:
            if not self._status.is_managed or not self._process:
                if self._status.is_running:
                    return True, "Metasploit RPC running but not managed by us"
                else:
                    return True, "Metasploit RPC not running"
            
            try:
                if utils.logger:
                    utils.logger.log_message(f"Stopping Metasploit RPC daemon (PID: {self._process.pid})")
                
                # Stop health monitoring
                self._shutdown_event.set()
                if self._health_thread and self._health_thread.is_alive():
                    self._health_thread.join(timeout=2.0)
                
                # Graceful shutdown
                if self._process.poll() is None:
                    try:
                        # Send SIGTERM first
                        if sys.platform != "win32":
                            os.killpg(os.getpgid(self._process.pid), signal.SIGTERM)
                        else:
                            self._process.terminate()
                        
                        # Wait for graceful shutdown
                        try:
                            self._process.wait(timeout=5.0)
                        except subprocess.TimeoutExpired:
                            # Force kill if needed
                            if utils.logger:
                                utils.logger.log_message("Force killing Metasploit RPC daemon")
                            self._kill_process()
                            
                    except ProcessLookupError:
                        # Process already dead
                        pass
                
                self._reset_status()
                
                if utils.logger:
                    utils.logger.log_message("Metasploit RPC daemon stopped")
                
                return True, "Metasploit RPC stopped"
                
            except Exception as e:
                return False, f"Error stopping Metasploit RPC: {str(e)}"
    
    def _kill_process(self):
        """Force kill the Metasploit process"""
        if self._process and self._process.poll() is None:
            try:
                if sys.platform != "win32":
                    os.killpg(os.getpgid(self._process.pid), signal.SIGKILL)
                else:
                    self._process.kill()
                self._process.wait(timeout=2.0)
            except Exception:
                pass
        self._process = None
    
    def _reset_status(self):
        """Reset status to default"""
        self._status = MetasploitStatus()
        self._process = None
    
    def _start_health_monitoring(self):
        """Start background health monitoring thread"""
        if self._health_thread and self._health_thread.is_alive():
            return
            
        self._shutdown_event.clear()
        self._health_thread = threading.Thread(
            target=self._health_monitor_worker,
            daemon=True,
            name="MetasploitHealthMonitor"
        )
        self._health_thread.start()
    
    def _health_monitor_worker(self):
        """Background worker for health monitoring"""
        while not self._shutdown_event.is_set():
            try:
                # Check if our managed process is still alive
                if self._status.is_managed and self._process:
                    if self._process.poll() is not None:
                        # Process died
                        if utils.logger:
                            utils.logger.log_message("Metasploit RPC daemon process died unexpectedly")
                        self._reset_status()
                        break
                
                # Check RPC availability
                if self.is_rpc_available():
                    self._status.is_running = True
                    self._status.last_check = time.time()
                    if self._status.is_managed:
                        self._status.connection_status = "Connected (Managed)"
                    else:
                        self._status.connection_status = "Connected (External)"
                else:
                    if self._status.is_running:
                        if utils.logger:
                            utils.logger.log_message("Lost connection to Metasploit RPC")
                    self._status.is_running = False
                    self._status.connection_status = "Disconnected"
                
                # Sleep for next check
                self._shutdown_event.wait(self.config.MSF_HEALTH_CHECK_INTERVAL)
                
            except Exception as e:
                if utils.logger:
                    utils.logger.log_message(f"Error in Metasploit health monitor: {str(e)}")
                self._shutdown_event.wait(10)  # Wait before retrying
    
    def get_status_info(self) -> dict:
        """Get detailed status information for UI display"""
        status_info = {
            'enabled': self.config.MSF_ENABLED,
            'auto_start': self.config.MSF_AUTO_START,
            'is_running': self._status.is_running,
            'is_managed': self._status.is_managed,
            'process_id': self._status.process_id,
            'connection_status': self._status.connection_status,
            'rpc_host': self.config.MSF_RPC_HOST,
            'rpc_port': self.config.MSF_RPC_PORT,
            'last_check': self._status.last_check
        }
        
        # Add installation info
        found, path_or_error = self.find_metasploit_installation()
        status_info['installation_found'] = found
        status_info['installation_path'] = path_or_error if found else None
        status_info['installation_error'] = path_or_error if not found else None
        
        return status_info
    
    def test_connection(self) -> Tuple[bool, str]:
        """Test connection to Metasploit RPC"""
        if not self.config.MSF_ENABLED:
            return False, "Metasploit integration is disabled"
        
        try:
            from .metasploit_service import MetasploitService
            msf_service = MetasploitService(self.config)
            return msf_service.test_connection()
        except Exception as e:
            return False, f"Connection test failed: {str(e)}"
    
    def initialize(self) -> Tuple[bool, str]:
        """Initialize Metasploit integration (called at startup)"""
        if not self.config.MSF_ENABLED:
            return True, "Metasploit integration is disabled"
        
        if utils.logger:
            utils.logger.log_message("Initializing Metasploit integration...")
        
        # First check if Metasploit is installed
        found, path_or_error = self.find_metasploit_installation()
        if not found:
            error_msg = f"Metasploit integration disabled - {path_or_error}"
            if utils.logger:
                utils.logger.log_message(error_msg)
            return False, error_msg
        
        # Check if already running
        if self.is_rpc_available():
            self._status.is_running = True
            self._status.is_managed = False
            self._status.connection_status = "Connected (External)"
            self._start_health_monitoring()
            
            if utils.logger:
                utils.logger.log_message("Found existing Metasploit RPC service")
            return True, "Using existing Metasploit RPC service"
        
        # Try to start if auto-start is enabled
        if self.config.MSF_AUTO_START:
            return self.start_rpc_daemon()
        else:
            return True, "Auto-start disabled - Metasploit RPC not started"
    
    def shutdown(self):
        """Shutdown Metasploit manager (called at application exit)"""
        if utils.logger:
            utils.logger.log_message("Shutting down Metasploit manager...")
        
        self._shutdown_event.set()
        
        # Stop health monitoring
        if self._health_thread and self._health_thread.is_alive():
            self._health_thread.join(timeout=3.0)
        
        # Stop RPC daemon if we manage it and auto-stop is enabled
        if self.config.MSF_AUTO_STOP and self._status.is_managed:
            self.stop_rpc_daemon()
        
        if utils.logger:
            utils.logger.log_message("Metasploit manager shutdown complete")