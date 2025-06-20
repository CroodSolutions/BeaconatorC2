from pathlib import Path

class DocumentationManager:
    def __init__(self):
        self.documentation_path = Path("documentation.md")
        self.section_cache = {}
        self._load_documentation()
        
    def _load_documentation(self):
        if not self.documentation_path.exists():
            return
            
        current_path = []
        current_content = []
        
        with open(self.documentation_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    if current_content:
                        current_content.append(line)
                    continue
                    
                if line.startswith('#'):
                    # Save previous section if it exists
                    if current_content and current_path:
                        section_key = '.'.join(current_path)
                        self.section_cache[section_key] = '\n'.join(current_content)
                    
                    # Count heading level and get section name
                    level = len(line) - len(line.lstrip('#'))
                    section_name = line[level:].strip()
                    
                    # Update path based on heading level
                    current_path = current_path[:level-1]
                    current_path.append(section_name)
                    
                    # Start new content collection
                    current_content = [line]
                else:
                    current_content.append(line)
            
            # Save the last section
            if current_content and current_path:
                section_key = '.'.join(current_path)
                self.section_cache[section_key] = '\n'.join(current_content)

    def get_section(self, section_name: str) -> str:
        if not section_name:
            return "Documentation not found"
            
        # For debugging
        #print("Available sections:", list(self.section_cache.keys()))
        #print("Requested section:", section_name)
        
        # Get the content for the requested section
        content = self.section_cache.get(section_name, "Documentation not found")
        
        # If found, also check for and append any subsections
        if content != "Documentation not found":
            for key, value in self.section_cache.items():
                if key.startswith(section_name + "."):
                    content += "\n\n" + value
                    
        return content