"""
Shared types for workflow execution to avoid circular imports
"""

from enum import Enum
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Optional


class ExecutionStatus(Enum):
    """Workflow execution status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


@dataclass
class ExecutionContext:
    """Context for workflow execution"""
    workflow_id: str
    beacon_id: str
    variables: Dict[str, Any]
    node_results: Dict[str, Any]
    execution_log: List[Dict[str, Any]]
    status: ExecutionStatus = ExecutionStatus.PENDING
    current_node_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None