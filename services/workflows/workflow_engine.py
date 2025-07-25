from typing import Dict, List, Any, Optional, Callable
import re
import time
import asyncio
from datetime import datetime

from .workflow_service import Workflow, WorkflowNode, WorkflowConnection
from .execution_types import ExecutionStatus, ExecutionContext
from .condition_evaluator import ConditionEvaluator
from services import SchemaService
from database import BeaconRepository
from services.command_processor import CommandProcessor
from workers.workflow_execution_worker import WorkflowExecutionWorker


class WorkflowEngine:
    """Engine for executing workflows using background threads"""
    
    def __init__(self, workflow_service, schema_service: SchemaService, 
                 beacon_repository: BeaconRepository, command_processor: CommandProcessor):
        self.workflow_service = workflow_service
        self.schema_service = schema_service
        self.beacon_repository = beacon_repository
        self.command_processor = command_processor
        self.condition_evaluator = ConditionEvaluator()
        
        # Execution state
        self.active_executions: Dict[str, ExecutionContext] = {}
        self.execution_callbacks: Dict[str, List[Callable]] = {}
        
        # Worker thread management
        self.active_workers: Dict[str, WorkflowExecutionWorker] = {}
        
    def start_execution(self, workflow: Workflow, beacon_id: str) -> Optional[str]:
        """Start executing a workflow on a specific beacon using background thread"""
        try:
            # Validate workflow
            if not workflow:
                print(f"ERROR: Cannot execute null workflow")
                return None
                
            if not workflow.nodes:
                print(f"ERROR: Workflow {workflow.workflow_id} has no nodes")
                return None
                
            # Validate beacon exists and is online
            beacon = self.beacon_repository.get_beacon(beacon_id)
            if not beacon:
                print(f"ERROR: Beacon {beacon_id} not found")
                return None
                
            if beacon.status != 'online':
                print(f"ERROR: Beacon {beacon_id} is not online (status: {beacon.status})")
                return None
                
            # Create execution ID
            execution_id = f"exec_{workflow.workflow_id}_{int(time.time())}"
            
            # Create worker thread for this execution
            worker = WorkflowExecutionWorker(
                execution_id=execution_id,
                workflow=workflow,
                beacon_id=beacon_id,
                beacon_repository=self.beacon_repository,
                schema_service=self.schema_service
            )
            
            # Connect worker signals to our handlers
            worker.execution_started.connect(self._on_execution_started)
            worker.execution_completed.connect(self._on_execution_completed)
            worker.execution_failed.connect(self._on_execution_failed)
            worker.node_started.connect(self._on_node_started)
            worker.node_completed.connect(self._on_node_completed)
            worker.execution_progress.connect(self._on_execution_progress)
            worker.log_message.connect(self._on_log_message)
            
            # Store worker and start execution
            self.active_workers[execution_id] = worker
            worker.start()
            
            print(f"Started workflow execution in background thread: {execution_id}")
            return execution_id
            
        except Exception as e:
            error_msg = f"Failed to start execution: {str(e)}"
            print(f"ERROR: {error_msg}")
            return None
            
    def stop_execution(self, execution_id: str) -> bool:
        """Stop an active workflow execution"""
        try:
            # Request worker to stop
            if execution_id in self.active_workers:
                worker = self.active_workers[execution_id]
                worker.request_stop()
                
                # Wait for worker to finish (with timeout)
                if worker.wait(5000):  # 5 second timeout
                    print(f"Worker {execution_id} stopped successfully")
                else:
                    print(f"Worker {execution_id} did not stop within timeout, forcing termination")
                    worker.terminate()
                    worker.wait()  # Wait for termination
                
                # Clean up worker
                del self.active_workers[execution_id]
                
            # Update context if it exists
            if execution_id in self.active_executions:
                context = self.active_executions[execution_id]
                if context.status == ExecutionStatus.RUNNING:
                    context.status = ExecutionStatus.STOPPED
                    context.end_time = datetime.now()
                    self._notify_execution_callbacks(execution_id, context)
                
            return True
        except Exception as e:
            print(f"Error stopping execution {execution_id}: {str(e)}")
            return False
            
    def shutdown(self):
        """Shutdown the workflow engine and cleanup all active workers"""
        print(f"Shutting down workflow engine with {len(self.active_workers)} active workers")
        
        # Stop all active workers
        for execution_id in list(self.active_workers.keys()):
            print(f"Stopping worker: {execution_id}")
            self.stop_execution(execution_id)
            
        # Clear all state
        self.active_executions.clear()
        self.execution_callbacks.clear()
        self.active_workers.clear()
        
        print("Workflow engine shutdown completed")
        
    def get_execution_status(self, execution_id: str) -> Optional[ExecutionContext]:
        """Get the current status of a workflow execution"""
        return self.active_executions.get(execution_id)
        
    def register_execution_callback(self, execution_id: str, callback: Callable):
        """Register a callback for execution updates"""
        print(f"Registering callback for execution {execution_id}")
        if execution_id not in self.execution_callbacks:
            self.execution_callbacks[execution_id] = []
        self.execution_callbacks[execution_id].append(callback)
        print(f"Total callbacks for {execution_id}: {len(self.execution_callbacks[execution_id])}")
        
    # Signal handlers for worker thread communication
    
    def _on_execution_started(self, execution_id: str):
        """Handle execution started signal from worker"""
        print(f"Execution started: {execution_id}")
        
    def _on_execution_completed(self, execution_id: str, context: ExecutionContext):
        """Handle execution completed signal from worker"""
        print(f"Execution completed: {execution_id}")
        
        # Store context and notify callbacks
        self.active_executions[execution_id] = context
        self._notify_execution_callbacks(execution_id, context)
        
        # Clean up worker
        if execution_id in self.active_workers:
            del self.active_workers[execution_id]
            
    def _on_execution_failed(self, execution_id: str, error_message: str):
        """Handle execution failed signal from worker"""
        print(f"Execution failed: {execution_id} - {error_message}")
        
        # Create failed context if it doesn't exist
        if execution_id not in self.active_executions:
            self.active_executions[execution_id] = ExecutionContext(
                workflow_id="unknown",
                beacon_id="unknown", 
                variables={},
                node_results={},
                execution_log=[],
                status=ExecutionStatus.FAILED,
                end_time=datetime.now()
            )
        else:
            context = self.active_executions[execution_id]
            context.status = ExecutionStatus.FAILED
            context.end_time = datetime.now()
            
        self._notify_execution_callbacks(execution_id, self.active_executions[execution_id])
        
        # Clean up worker
        if execution_id in self.active_workers:
            del self.active_workers[execution_id]
            
    def _on_node_started(self, execution_id: str, node_id: str):
        """Handle node started signal from worker"""
        print(f"Node started: {execution_id}/{node_id}")
        
    def _on_node_completed(self, execution_id: str, node_id: str, result: dict):
        """Handle node completed signal from worker"""
        print(f"Node completed: {execution_id}/{node_id} - Status: {result.get('status', 'unknown')}")
        
    def _on_execution_progress(self, execution_id: str, context: ExecutionContext):
        """Handle execution progress signal from worker"""
        # Update stored context and notify callbacks
        self.active_executions[execution_id] = context
        self._notify_execution_callbacks(execution_id, context)
        
    def _on_log_message(self, execution_id: str, level: str, message: str):
        """Handle log message signal from worker"""
        print(f"[{execution_id}] {level.upper()}: {message}")
        
    # Essential utility methods for callback system
    
    def _log_execution(self, context: ExecutionContext, level: str, message: str):
        """Log an execution event"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'message': message,
            'node_id': context.current_node_id
        }
        context.execution_log.append(log_entry)
        
        # Print for immediate feedback
        print(f"[{context.workflow_id}] {level.upper()}: {message}")
        
    def _notify_execution_callbacks(self, execution_id: str, context: ExecutionContext):
        """Notify all registered callbacks about execution updates"""
        if execution_id in self.execution_callbacks:
            print(f"Found {len(self.execution_callbacks[execution_id])} callbacks to notify")
            for callback in self.execution_callbacks[execution_id]:
                try:
                    callback(context)
                except Exception as e:
                    print(f"Error in execution callback: {str(e)}")
        else:
            print(f"No callbacks registered for execution {execution_id}")