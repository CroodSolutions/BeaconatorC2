"""
Trigger Service for Workflow Automation

Monitors system events and automatically triggers workflows based on configured conditions.
Supports multiple trigger types: manual, beacon connection, status changes, scheduled.
"""

import re
import ipaddress
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QThread
from PyQt6.QtCore import pyqtSlot

from database import BeaconRepository
from services.workflows.workflow_service import WorkflowService
from services.workflows.workflow_engine import WorkflowEngine


class TriggerType(Enum):
    """Types of workflow triggers"""
    MANUAL = "manual"
    BEACON_CONNECTION = "beacon_connection"
    BEACON_STATUS = "beacon_status"
    SCHEDULED = "scheduled"
    EVENT_CHAIN = "event_chain"


@dataclass
class TriggerConfig:
    """Configuration for a workflow trigger"""
    trigger_type: TriggerType
    enabled: bool = True
    filters: Dict[str, Any] = field(default_factory=dict)
    schedule: Dict[str, Any] = field(default_factory=dict)
    last_triggered: Optional[datetime] = None
    trigger_count: int = 0
    
    def matches_beacon(self, beacon_info: Dict[str, Any]) -> bool:
        """Check if a beacon matches this trigger's filters"""
        if not self.enabled or self.trigger_type != TriggerType.BEACON_CONNECTION:
            return False
            
        filters = self.filters
        
        # Check CIDR ranges
        if 'cidr_ranges' in filters and filters['cidr_ranges']:
            # Check if wildcard "*" is present - if so, skip IP filtering (match all IPs)
            cidr_ranges = filters['cidr_ranges']
            if '*' in cidr_ranges:
                pass  # Wildcard matches all IPs, skip CIDR filtering
            else:
                beacon_ip = beacon_info.get('ip_address', '')
                if beacon_ip:
                    try:
                        ip = ipaddress.ip_address(beacon_ip)
                        matched = False
                        for cidr in cidr_ranges:
                            if cidr.strip():  # Skip empty entries
                                if ip in ipaddress.ip_network(cidr):
                                    matched = True
                                    break
                        if not matched:
                            return False
                    except:
                        pass  # Invalid IP, skip CIDR check
        
        # Check computer name pattern
        if 'beacon_pattern' in filters and filters['beacon_pattern']:
            pattern = filters['beacon_pattern']
            computer_name = beacon_info.get('computer_name', '')
            if pattern != '*' and not re.match(pattern, computer_name):
                return False
        
        # Check receiver types
        if 'receiver_types' in filters and filters['receiver_types']:
            receiver_type = beacon_info.get('receiver_type', '')
            if receiver_type not in filters['receiver_types']:
                return False
        
        # Check exclude patterns
        if 'exclude_patterns' in filters and filters['exclude_patterns']:
            computer_name = beacon_info.get('computer_name', '')
            for exclude in filters['exclude_patterns']:
                if re.match(exclude, computer_name):
                    return False
        
        return True


class TriggerMonitor(QThread):
    """Background thread for monitoring trigger conditions"""
    
    trigger_activated = pyqtSignal(str, str, dict)  # workflow_id, trigger_id, context
    
    def __init__(self, trigger_service):
        super().__init__()
        self.trigger_service = trigger_service
        self._running = False
        self._check_interval = 1000  # milliseconds
        
    def run(self):
        """Monitor trigger conditions in background"""
        self._running = True
        while self._running:
            try:
                self.trigger_service.check_scheduled_triggers()
            except Exception as e:
                print(f"Error checking triggers: {e}")
            self.msleep(self._check_interval)
    
    def stop(self):
        """Stop monitoring"""
        self._running = False
        self.wait()


class TriggerService(QObject):
    """Service for managing and executing workflow triggers"""
    
    # Signals
    workflow_triggered = pyqtSignal(str, dict)  # workflow_id, context
    trigger_registered = pyqtSignal(str, str)  # workflow_id, trigger_id
    trigger_removed = pyqtSignal(str, str)  # workflow_id, trigger_id
    
    def __init__(self, beacon_repository: BeaconRepository, 
                 workflow_service: WorkflowService,
                 workflow_engine: WorkflowEngine):
        super().__init__()
        self.beacon_repository = beacon_repository
        self.workflow_service = workflow_service
        self.workflow_engine = workflow_engine
        
        # Active triggers: workflow_id -> {trigger_node_id -> TriggerConfig}
        self.active_triggers: Dict[str, Dict[str, TriggerConfig]] = {}
        
        # Recent beacon connections to avoid duplicate triggers
        self._recent_beacons: Set[str] = set()
        self._beacon_timeout = timedelta(minutes=5)
        self._beacon_timestamps: Dict[str, datetime] = {}
        
        # Monitor thread
        self._monitor_thread = None
        
        # Schedule timer for periodic checks
        self._schedule_timer = QTimer()
        self._schedule_timer.timeout.connect(self.check_scheduled_triggers)
        self._schedule_timer.start(60000)  # Check every minute
        
    def start_monitoring(self):
        """Start background monitoring for triggers"""
        if not self._monitor_thread:
            self._monitor_thread = TriggerMonitor(self)
            self._monitor_thread.trigger_activated.connect(self._on_trigger_activated)
            self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop background monitoring"""
        if self._monitor_thread:
            self._monitor_thread.stop()
            self._monitor_thread = None
        self._schedule_timer.stop()
    
    def register_trigger(self, workflow_id: str, trigger_node_id: str, 
                         trigger_config: Dict[str, Any]):
        """Register a trigger for a workflow"""
        # Convert dict to TriggerConfig
        config = TriggerConfig(
            trigger_type=TriggerType(trigger_config.get('trigger_type', 'manual')),
            enabled=trigger_config.get('enabled', True),
            filters=trigger_config.get('filters', {}),
            schedule=trigger_config.get('schedule', {})
        )
        
        # Store trigger
        if workflow_id not in self.active_triggers:
            self.active_triggers[workflow_id] = {}
        self.active_triggers[workflow_id][trigger_node_id] = config
        
        self.trigger_registered.emit(workflow_id, trigger_node_id)
        
    def remove_trigger(self, workflow_id: str, trigger_node_id: str):
        """Remove a trigger"""
        if workflow_id in self.active_triggers:
            if trigger_node_id in self.active_triggers[workflow_id]:
                del self.active_triggers[workflow_id][trigger_node_id]
                self.trigger_removed.emit(workflow_id, trigger_node_id)
                
                # Clean up empty workflow entries
                if not self.active_triggers[workflow_id]:
                    del self.active_triggers[workflow_id]
    
    def evaluate_beacon_event(self, beacon_info: Dict[str, Any], event_type: str = 'connection'):
        """Evaluate if a beacon event should trigger any workflows"""
        beacon_id = beacon_info.get('beacon_id', '')
        computer_name = beacon_info.get('computer_name', 'Unknown')
        
        print(f"[TRIGGER DEBUG] Evaluating beacon event - Type: {event_type}, Beacon: {beacon_id}, Computer: {computer_name}")
        print(f"[TRIGGER DEBUG] Beacon info: {beacon_info}")
        print(f"[TRIGGER DEBUG] Active triggers count: {len(self.active_triggers)}")
        
        # Check if this beacon was recently processed (only for connections)
        if event_type == 'connection':
            if beacon_id in self._recent_beacons:
                # Check if enough time has passed
                if beacon_id in self._beacon_timestamps:
                    time_diff = datetime.now() - self._beacon_timestamps[beacon_id]
                    if time_diff < self._beacon_timeout:
                        print(f"[TRIGGER DEBUG] Skipping duplicate trigger - Last seen {time_diff.seconds} seconds ago")
                        return  # Skip duplicate trigger
            
            # Mark beacon as processed
            self._recent_beacons.add(beacon_id)
            self._beacon_timestamps[beacon_id] = datetime.now()
        
        # Check all active triggers
        triggers_checked = 0
        triggers_matched = 0
        
        for workflow_id, triggers in self.active_triggers.items():
            for trigger_id, config in triggers.items():
                triggers_checked += 1
                print(f"[TRIGGER DEBUG] Checking trigger {trigger_id} in workflow {workflow_id}")
                print(f"[TRIGGER DEBUG]   - Type: {config.trigger_type.value}, Enabled: {config.enabled}")
                
                # Check if this trigger is for the right event type
                if event_type == 'status' and config.trigger_type == TriggerType.BEACON_STATUS:
                    print(f"[TRIGGER DEBUG]   - This is a status change trigger, checking filters...")
                    if config.enabled and self.matches_status_change(beacon_info, config):
                        triggers_matched += 1
                        print(f"[TRIGGER DEBUG]   - MATCH! Triggering workflow {workflow_id}")
                        
                        # Trigger the workflow
                        context = {
                            'trigger_type': 'beacon_status',
                            'beacon_id': beacon_id,
                            'computer_name': computer_name,
                            'beacon_info': beacon_info,
                            'event_type': event_type,
                            'timestamp': datetime.now().isoformat()
                        }
                        self._execute_workflow(workflow_id, context)
                        
                        # Update trigger stats
                        config.last_triggered = datetime.now()
                        config.trigger_count += 1
                    else:
                        print(f"[TRIGGER DEBUG]   - No match for status trigger")
                        
                elif event_type == 'connection' and config.trigger_type == TriggerType.BEACON_CONNECTION:
                    print(f"[TRIGGER DEBUG]   - This is a connection trigger, checking filters...")
                    if config.enabled and config.matches_beacon(beacon_info):
                        triggers_matched += 1
                        print(f"[TRIGGER DEBUG]   - MATCH! Triggering workflow {workflow_id}")
                        
                        # Trigger the workflow
                        context = {
                            'trigger_type': 'beacon_connection',
                            'beacon_id': beacon_id,
                            'computer_name': computer_name,
                            'beacon_info': beacon_info,
                            'timestamp': datetime.now().isoformat()
                        }
                        self._execute_workflow(workflow_id, context)
                        
                        # Update trigger stats
                        config.last_triggered = datetime.now()
                        config.trigger_count += 1
                    else:
                        print(f"[TRIGGER DEBUG]   - No match for connection trigger")
                else:
                    print(f"[TRIGGER DEBUG]   - Trigger type {config.trigger_type.value} doesn't match event type {event_type}")
        
        print(f"[TRIGGER DEBUG] Evaluation complete - Checked: {triggers_checked}, Matched: {triggers_matched}")
    
    def matches_status_change(self, beacon_info: Dict[str, Any], config: TriggerConfig) -> bool:
        """Check if a beacon status change matches trigger filters"""
        filters = config.filters
        
        # Get status info
        status = beacon_info.get('status', '')
        computer_name = beacon_info.get('computer_name', '')
        
        print(f"[TRIGGER DEBUG] Checking status change - Status: {status}, Computer: {computer_name}")
        
        # Check status type filter
        if 'status_type' in filters:
            expected_status = filters['status_type']
            if expected_status != 'any' and expected_status != status:
                print(f"[TRIGGER DEBUG]   - Status mismatch: expected {expected_status}, got {status}")
                return False
        
        # Check computer name pattern
        if 'beacon_pattern' in filters and filters['beacon_pattern']:
            pattern = filters['beacon_pattern']
            if pattern != '*' and not re.match(pattern, computer_name):
                print(f"[TRIGGER DEBUG]   - Pattern mismatch: {computer_name} doesn't match {pattern}")
                return False
        
        print(f"[TRIGGER DEBUG]   - Status change matches filters!")
        return True
    
    def check_scheduled_triggers(self):
        """Check for scheduled triggers that need to run"""
        now = datetime.now()
        
        for workflow_id, triggers in self.active_triggers.items():
            for trigger_id, config in triggers.items():
                if config.trigger_type == TriggerType.SCHEDULED and config.enabled:
                    schedule = config.schedule
                    
                    # Check interval-based schedule
                    if schedule.get('type') == 'interval':
                        interval_minutes = schedule.get('interval_minutes', 60)
                        interval = timedelta(minutes=interval_minutes)
                        
                        if config.last_triggered is None or \
                           (now - config.last_triggered) >= interval:
                            # Trigger the workflow
                            context = {
                                'trigger_type': 'scheduled',
                                'schedule_type': 'interval',
                                'interval_minutes': interval_minutes,
                                'timestamp': now.isoformat()
                            }
                            self._execute_workflow(workflow_id, context)
                            
                            # Update trigger stats
                            config.last_triggered = now
                            config.trigger_count += 1
                    
                    # TODO: Add cron-based scheduling support
    
    @pyqtSlot(str, str, dict)
    def _on_trigger_activated(self, workflow_id: str, trigger_id: str, context: dict):
        """Handle trigger activation from monitor thread"""
        self._execute_workflow(workflow_id, context)
    
    def _execute_workflow(self, workflow_id: str, trigger_context: Dict[str, Any]):
        """Execute a workflow with the given trigger context"""
        print(f"[TRIGGER DEBUG] Executing workflow {workflow_id}")
        print(f"[TRIGGER DEBUG] Trigger context: {trigger_context}")
        
        try:
            # Load the workflow
            workflow = self.workflow_service.load_workflow(workflow_id)
            if not workflow:
                print(f"[TRIGGER DEBUG] ERROR: Workflow {workflow_id} not found")
                return
            
            print(f"[TRIGGER DEBUG] Loaded workflow: {workflow.name}")
            
            # Find trigger node and inject context
            trigger_node_found = False
            for node in workflow.nodes if hasattr(workflow, 'nodes') else []:
                if node.node_type in ['trigger', 'start']:
                    trigger_node_found = True
                    if not hasattr(node, 'parameters'):
                        node.parameters = {}
                    node.parameters['trigger_context'] = trigger_context
                    print(f"[TRIGGER DEBUG] Injected context into trigger node {node.node_id}")
                    break
            
            if not trigger_node_found:
                print(f"[TRIGGER DEBUG] WARNING: No trigger/start node found in workflow")
            
            # Emit signal for execution
            print(f"[TRIGGER DEBUG] Emitting workflow_triggered signal")
            self.workflow_triggered.emit(workflow_id, trigger_context)
            
            # Start workflow execution via engine
            print(f"[TRIGGER DEBUG] Starting workflow execution via engine")
            execution_id = self.workflow_engine.start_execution(
                workflow,
                beacon_id=trigger_context.get('beacon_id'),
                canvas_variables={'trigger_context': trigger_context}
            )
            print(f"[TRIGGER DEBUG] Workflow execution started with ID: {execution_id}")
            
        except Exception as e:
            print(f"[TRIGGER DEBUG] ERROR executing workflow {workflow_id}: {e}")
            import traceback
            traceback.print_exc()
    
    def get_trigger_stats(self, workflow_id: str, trigger_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific trigger"""
        if workflow_id in self.active_triggers:
            if trigger_id in self.active_triggers[workflow_id]:
                config = self.active_triggers[workflow_id][trigger_id]
                return {
                    'enabled': config.enabled,
                    'trigger_type': config.trigger_type.value,
                    'last_triggered': config.last_triggered.isoformat() if config.last_triggered else None,
                    'trigger_count': config.trigger_count
                }
        return None
    
    def cleanup_old_beacons(self):
        """Clean up old beacon entries to prevent memory growth"""
        now = datetime.now()
        to_remove = []
        
        for beacon_id, timestamp in self._beacon_timestamps.items():
            if now - timestamp > self._beacon_timeout * 2:  # Double timeout for cleanup
                to_remove.append(beacon_id)
        
        for beacon_id in to_remove:
            self._recent_beacons.discard(beacon_id)
            del self._beacon_timestamps[beacon_id]