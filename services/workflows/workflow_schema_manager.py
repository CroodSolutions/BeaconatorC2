from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass, field
from PyQt6.QtCore import QObject, pyqtSignal

from services import SchemaService


@dataclass
class WorkflowSchemaInfo:
    """Information about a schema available for workflow use"""
    schema_file: str
    schema_name: str
    beacon_type: str
    version: str
    description: str
    supported_platforms: List[str] = field(default_factory=list)
    module_count: int = 0
    category_count: int = 0
    is_active: bool = False


class WorkflowSchemaManager(QObject):
    """Manages schema selection and availability for workflows"""
    
    # Signals
    schema_selection_changed = pyqtSignal(list)  # Emits list of active schema files
    schema_added = pyqtSignal(str)  # Emits schema_file when added
    schema_removed = pyqtSignal(str)  # Emits schema_file when removed
    
    def __init__(self, schema_service: SchemaService = None):
        super().__init__()
        self.schema_service = schema_service or SchemaService()
        
        # Track available and active schemas
        self.available_schemas: Dict[str, WorkflowSchemaInfo] = {}
        self.active_schema_files: Set[str] = set()
        
        # Load available schemas
        self._discover_available_schemas()
        
    def _discover_available_schemas(self):
        """Discover all available schemas and populate schema info"""
        try:
            schema_files = self.schema_service.list_available_schemas()
            
            for schema_file in schema_files:
                try:
                    schema = self.schema_service.load_schema(schema_file)
                    if not schema:
                        continue
                        
                    # Count modules and categories
                    module_count = 0
                    category_count = len(schema.categories)
                    
                    for category in schema.categories.values():
                        module_count += len(category.modules)
                    
                    # Create schema info
                    schema_info = WorkflowSchemaInfo(
                        schema_file=schema_file,
                        schema_name=schema_file.replace('.yaml', '').replace('_', ' ').title(),
                        beacon_type=schema.beacon_info.beacon_type,
                        version=schema.beacon_info.version,
                        description=schema.beacon_info.description,
                        supported_platforms=schema.beacon_info.supported_platforms,
                        module_count=module_count,
                        category_count=category_count,
                        is_active=False
                    )
                    
                    self.available_schemas[schema_file] = schema_info
                    
                except Exception as e:
                    print(f"Error loading schema info for {schema_file}: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error discovering schemas: {e}")
    
    def get_available_schemas(self) -> List[WorkflowSchemaInfo]:
        """Get list of all available schemas"""
        return list(self.available_schemas.values())
    
    def get_active_schemas(self) -> List[WorkflowSchemaInfo]:
        """Get list of currently active schemas"""
        return [schema for schema in self.available_schemas.values() if schema.is_active]
    
    def get_active_schema_files(self) -> List[str]:
        """Get list of active schema file names"""
        return list(self.active_schema_files)
    
    def is_schema_active(self, schema_file: str) -> bool:
        """Check if a schema is currently active"""
        return schema_file in self.active_schema_files
    
    def add_schema_to_workflow(self, schema_file: str) -> bool:
        """Add a schema to the current workflow"""
        if schema_file not in self.available_schemas:
            print(f"Schema {schema_file} not available")
            return False
        
        if schema_file not in self.active_schema_files:
            self.active_schema_files.add(schema_file)
            self.available_schemas[schema_file].is_active = True
            
            # Emit signals
            self.schema_added.emit(schema_file)
            self.schema_selection_changed.emit(self.get_active_schema_files())
            
            print(f"Added schema {schema_file} to workflow")
            return True
        
        return False
    
    def remove_schema_from_workflow(self, schema_file: str) -> bool:
        """Remove a schema from the current workflow"""
        if schema_file in self.active_schema_files:
            self.active_schema_files.remove(schema_file)
            if schema_file in self.available_schemas:
                self.available_schemas[schema_file].is_active = False
            
            # Emit signals
            self.schema_removed.emit(schema_file)
            self.schema_selection_changed.emit(self.get_active_schema_files())
            
            print(f"Removed schema {schema_file} from workflow")
            return True
        
        return False
    
    def toggle_schema(self, schema_file: str) -> bool:
        """Toggle a schema's active state"""
        if self.is_schema_active(schema_file):
            return self.remove_schema_from_workflow(schema_file)
        else:
            return self.add_schema_to_workflow(schema_file)
    
    def set_active_schemas(self, schema_files: List[str]):
        """Set the complete list of active schemas"""
        # Clear current selection
        self.clear_all_schemas()
        
        # Add each schema
        for schema_file in schema_files:
            if schema_file in self.available_schemas:
                self.active_schema_files.add(schema_file)
                self.available_schemas[schema_file].is_active = True
        
        # Emit single signal for batch change
        self.schema_selection_changed.emit(self.get_active_schema_files())
        print(f"Set active schemas: {schema_files}")
    
    def clear_all_schemas(self):
        """Remove all schemas from the current workflow"""
        if self.active_schema_files:
            # Mark all as inactive
            for schema_file in self.active_schema_files:
                if schema_file in self.available_schemas:
                    self.available_schemas[schema_file].is_active = False
            
            self.active_schema_files.clear()
            self.schema_selection_changed.emit([])
            print("Cleared all active schemas")
    
    def get_schema_info(self, schema_file: str) -> Optional[WorkflowSchemaInfo]:
        """Get detailed information about a specific schema"""
        return self.available_schemas.get(schema_file)
    
    def get_schema_modules_count(self, schema_file: str) -> int:
        """Get the number of modules in a schema"""
        schema_info = self.get_schema_info(schema_file)
        return schema_info.module_count if schema_info else 0
    
    def get_workflow_summary(self) -> Dict[str, Any]:
        """Get a summary of the current workflow schema configuration"""
        active_schemas = self.get_active_schemas()
        
        total_modules = sum(schema.module_count for schema in active_schemas)
        total_categories = sum(schema.category_count for schema in active_schemas)
        beacon_types = list(set(schema.beacon_type for schema in active_schemas))
        
        return {
            "active_schema_count": len(active_schemas),
            "total_modules": total_modules,
            "total_categories": total_categories,
            "beacon_types": beacon_types,
            "active_schemas": [schema.schema_file for schema in active_schemas]
        }
    
    def refresh_schemas(self):
        """Refresh the list of available schemas"""
        # Store current selection
        current_active = self.get_active_schema_files()
        
        # Clear and rediscover
        self.available_schemas.clear()
        self.active_schema_files.clear()
        self._discover_available_schemas()
        
        # Restore selection for schemas that still exist
        restored_schemas = []
        for schema_file in current_active:
            if schema_file in self.available_schemas:
                self.active_schema_files.add(schema_file)
                self.available_schemas[schema_file].is_active = True
                restored_schemas.append(schema_file)
        
        if restored_schemas:
            self.schema_selection_changed.emit(restored_schemas)
            print(f"Refreshed schemas, restored: {restored_schemas}")
    
    def validate_schema_selection(self) -> List[str]:
        """Validate current schema selection and return any warnings"""
        warnings = []
        
        if not self.active_schema_files:
            warnings.append("No schemas selected - workflows will only have control flow nodes")
        
        # Check for schema compatibility issues
        beacon_types = set()
        for schema_file in self.active_schema_files:
            schema_info = self.get_schema_info(schema_file)
            if schema_info:
                beacon_types.add(schema_info.beacon_type)
        
        if len(beacon_types) > 3:
            warnings.append(f"Many beacon types selected ({len(beacon_types)}) - consider limiting for workflow clarity")
        
        return warnings
    
    def export_schema_config(self) -> Dict[str, Any]:
        """Export current schema configuration for saving with workflow"""
        return {
            "format_version": "1.0",
            "active_schemas": list(self.active_schema_files),
            "schema_info": {
                schema_file: {
                    "beacon_type": info.beacon_type,
                    "version": info.version,
                    "module_count": info.module_count
                }
                for schema_file, info in self.available_schemas.items()
                if schema_file in self.active_schema_files
            }
        }
    
    def import_schema_config(self, config: Dict[str, Any]) -> bool:
        """Import schema configuration from saved workflow"""
        try:
            if config.get("format_version") != "1.0":
                print("Unsupported schema config format")
                return False
            
            active_schemas = config.get("active_schemas", [])
            
            # Validate that all schemas are still available
            missing_schemas = []
            for schema_file in active_schemas:
                if schema_file not in self.available_schemas:
                    missing_schemas.append(schema_file)
            
            if missing_schemas:
                print(f"Warning: Missing schemas: {missing_schemas}")
                # Filter out missing schemas
                active_schemas = [s for s in active_schemas if s not in missing_schemas]
            
            # Set the active schemas
            self.set_active_schemas(active_schemas)
            
            return True
            
        except Exception as e:
            print(f"Error importing schema config: {e}")
            return False