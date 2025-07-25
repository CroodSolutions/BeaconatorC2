from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path

from services import SchemaService
from database import BeaconRepository
from services.command_processor import CommandProcessor


@dataclass
class WorkflowNode:
    """Represents a node in a workflow"""
    node_id: str
    node_type: str
    position: Dict[str, float]
    module_info: Dict[str, Any] = field(default_factory=dict)
    parameters: Dict[str, Any] = field(default_factory=dict)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    
    
@dataclass
class WorkflowConnection:
    """Represents a connection between two nodes"""
    connection_id: str
    source_node_id: str
    target_node_id: str
    condition: Optional[Dict[str, Any]] = None
    connection_type: Optional[str] = None  # Store connection type for branching


@dataclass
class Workflow:
    """Represents a complete workflow"""
    workflow_id: str
    name: str
    description: str
    nodes: List[WorkflowNode] = field(default_factory=list)
    connections: List[WorkflowConnection] = field(default_factory=list)
    variables: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    modified_at: datetime = field(default_factory=datetime.now)


class WorkflowService:
    """Service for managing and executing workflows"""
    
    def __init__(self, schema_service: SchemaService, beacon_repository: BeaconRepository, 
                 command_processor: CommandProcessor):
        self.schema_service = schema_service
        self.beacon_repository = beacon_repository
        self.command_processor = command_processor
        self.workflows_dir = Path("workflows")
        self.workflows_dir.mkdir(exist_ok=True)
        
    def create_workflow(self, name: str, description: str = "") -> Workflow:
        """Create a new workflow"""
        workflow_id = f"workflow_{int(datetime.now().timestamp())}"
        return Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description
        )
        
    def save_workflow(self, workflow: Workflow) -> bool:
        """Save a workflow to disk"""
        try:
            workflow.modified_at = datetime.now()
            
            # Convert to dictionary for JSON serialization
            workflow_data = {
                'workflow_id': workflow.workflow_id,
                'name': workflow.name,
                'description': workflow.description,
                'nodes': [self._node_to_dict(node) for node in workflow.nodes],
                'connections': [self._connection_to_dict(conn) for conn in workflow.connections],
                'variables': workflow.variables,
                'created_at': workflow.created_at.isoformat(),
                'modified_at': workflow.modified_at.isoformat()
            }
            
            # Save to file
            workflow_file = self.workflows_dir / f"{workflow.workflow_id}.json"
            with open(workflow_file, 'w') as f:
                json.dump(workflow_data, f, indent=2)
                
            return True
            
        except Exception as e:
            print(f"Error saving workflow: {e}")
            return False
            
    def load_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Load a workflow from disk"""
        try:
            workflow_file = self.workflows_dir / f"{workflow_id}.json"
            
            if not workflow_file.exists():
                return None
                
            with open(workflow_file, 'r') as f:
                data = json.load(f)
                
            # Convert back to workflow object
            workflow = Workflow(
                workflow_id=data['workflow_id'],
                name=data['name'],
                description=data['description'],
                nodes=[self._dict_to_node(node_data) for node_data in data.get('nodes', [])],
                connections=[self._dict_to_connection(conn_data) for conn_data in data.get('connections', [])],
                variables=data.get('variables', {}),
                created_at=datetime.fromisoformat(data.get('created_at', datetime.now().isoformat())),
                modified_at=datetime.fromisoformat(data.get('modified_at', datetime.now().isoformat()))
            )
            
            return workflow
            
        except Exception as e:
            print(f"Error loading workflow: {e}")
            return None
            
    def list_workflows(self) -> List[Dict[str, Any]]:
        """List all available workflows"""
        workflows = []
        
        for workflow_file in self.workflows_dir.glob("*.json"):
            try:
                with open(workflow_file, 'r') as f:
                    data = json.load(f)
                    
                workflows.append({
                    'workflow_id': data['workflow_id'],
                    'name': data['name'],
                    'description': data['description'],
                    'created_at': data.get('created_at'),
                    'modified_at': data.get('modified_at'),
                    'node_count': len(data.get('nodes', [])),
                    'connection_count': len(data.get('connections', []))
                })
                
            except Exception:
                continue
                
        return sorted(workflows, key=lambda x: x['modified_at'], reverse=True)
        
    def delete_workflow(self, workflow_id: str) -> bool:
        """Delete a workflow"""
        try:
            workflow_file = self.workflows_dir / f"{workflow_id}.json"
            if workflow_file.exists():
                workflow_file.unlink()
                return True
            return False
        except Exception:
            return False
            
    def _node_to_dict(self, node: WorkflowNode) -> Dict[str, Any]:
        """Convert a WorkflowNode to dictionary"""
        return {
            'node_id': node.node_id,
            'node_type': node.node_type,
            'position': node.position,
            'module_info': node.module_info,
            'parameters': node.parameters,
            'conditions': node.conditions
        }
        
    def _dict_to_node(self, data: Dict[str, Any]) -> WorkflowNode:
        """Convert dictionary to WorkflowNode"""
        return WorkflowNode(
            node_id=data['node_id'],
            node_type=data['node_type'],
            position=data['position'],
            module_info=data.get('module_info', {}),
            parameters=data.get('parameters', {}),
            conditions=data.get('conditions', [])
        )
        
    def _connection_to_dict(self, connection: WorkflowConnection) -> Dict[str, Any]:
        """Convert a WorkflowConnection to dictionary"""
        return {
            'connection_id': connection.connection_id,
            'source_node_id': connection.source_node_id,
            'target_node_id': connection.target_node_id,
            'condition': connection.condition
        }
        
    def _dict_to_connection(self, data: Dict[str, Any]) -> WorkflowConnection:
        """Convert dictionary to WorkflowConnection"""
        return WorkflowConnection(
            connection_id=data['connection_id'],
            source_node_id=data['source_node_id'],
            target_node_id=data['target_node_id'],
            condition=data.get('condition')
        )