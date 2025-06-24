import yaml
from pathlib import Path
from typing import Union, List
from database import AgentRepository
from utils import literal, literal_presenter

# Add YAML representer
yaml.add_representer(literal, literal_presenter)

class ModuleHandler:
    """Handles module execution"""
    def __init__(self, agent_repository: AgentRepository):
        self.agent_repository = agent_repository

    def execute_winget_ps(self, agent_id: str, powershell_script: Union[str, List[str]], config):
        """ Create Winget config YAML for PowerShell script execution"""

        filepath = Path(config.FILES_FOLDER) / f"{agent_id}_config.yaml"

        if isinstance(powershell_script, list):
            powershell_script = '\n'.join(powershell_script)

            # Create the configuration structure
        base_string = {
            "properties": {
                "resources": [
                    {
                        "resource": "PSDscResources/Script",
                        "id": "myAppConfig",
                        "directives": {
                            "description": "Run Powershell Command",
                            "allowPrerelease": True
                        },
                        "settings": {
                            "GetScript": literal("#\"state\""),
                            "TestScript": literal("return $false"),
                            "SetScript": literal(powershell_script)
                        }
                    }
                ],
                "configurationVersion": "0.2.0"
            }
        }

        yaml_content = yaml.dump(base_string, 
                default_flow_style=False,
                sort_keys=False,
                width=float("inf"),
                allow_unicode=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(yaml_content)