from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, 
                            QPushButton, QTextEdit, QLabel, QComboBox, QTreeWidget, 
                            QTreeWidgetItem, QStackedWidget, QSplitter, QSpinBox, 
                            QGridLayout, QMessageBox, QFileDialog, QToolTip)
from PyQt6.QtCore import pyqtSignal, Qt, QPoint
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QStyle
from database import AgentRepository
from services import ModuleHandler
from utils import FontManager, logger
from ..widgets import OutputDisplay
from .documentation_panel import DocumentationPanel
import utils

class CommandWidget(QWidget):
    """Widget for sending commands and modules to agents"""
    def __init__(self, agent_repository: AgentRepository, module_handler: ModuleHandler = None, doc_panel: DocumentationPanel = None):
        super().__init__()
        self.agent_repository = agent_repository
        self.module_handler = module_handler
        self.doc_panel = doc_panel
        self.current_agent_id = None
        FontManager().add_relative_font_widget(self, 0)
        self.font_manager = FontManager()
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        # Create horizontal split for top section
        top_section = QHBoxLayout()
        
        # Left side - Command navigation tree
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderHidden(True)
        self.nav_tree.setMinimumWidth(200)
        self.nav_tree.currentItemChanged.connect(self.on_nav_changed)
        
        # Set up command categories
        categories = {
            "Basic Commands": [
                "Command Execution",
                "WinGet PS Execution"
            ],
            "Discovery": [
                "Basic Recon",
                "Discover PII",
                "Enumerate DCs",
                "Domain Trusts",
                "Domain Admins",
                "Unconstrained Delegation",
                "Active User Membership",
                "Port Scanner"
            ],
            "Evasion": [
                "Deny Outbound Firewall",
                "Host File URL Block",
                "Unhook NTDLL"
            ],
            "Privilege Escalation": [
                "CMSTP UAC Bypass",
                "Run As User",
            ],
            "Persistence": [
                "Add Admin User",
                "Add Startup to Registry",
                "Add Scheduled Task"
            ],
            "Lateral Movement": [
                "Install MSI",
                "RDP Connection",
            ],
            "Impact": [
                "Encrypt Files",
                "Decrypt Files",
            ]
        }
        
        # Populate tree
        for category, commands in categories.items():
            cat_item = QTreeWidgetItem([category])
            for cmd in commands:
                cmd_item = QTreeWidgetItem([cmd])
                cat_item.addChild(cmd_item)
            self.nav_tree.addTopLevelItem(cat_item)
        
        # Right side of top section - Command interface stack
        self.cmd_stack = QStackedWidget()
        
        # Add different execution interfaces
        self.setup_command_prompt()
        self.setup_WinGetPS_script()
        self.setup_BasicRecon()
        self.setup_DiscoverPII()
        self.setup_EnumerateDCs()
        self.setup_DomainTrustRecon()
        self.setup_IdentifyDomainAdmins()
        self.setup_CheckUnconstrainedDelegation()
        self.setup_ActiveUserMembership()
        self.setup_PortScanner()
        self.setup_DenyOutboundFirewall()
        self.setup_HostFileURLBlock()
        self.setup_UnhookNTDLL()
        self.setup_CMSTP_UAC_Bypass()
        self.setup_RunAsUser()
        self.setup_AddAdminUser()
        self.setup_AddScriptToRegistry()
        self.setup_CreateScheduledTask()
        self.setup_InstallMSI()
        self.setup_RDPConnect()
        self.setup_EncryptDirectory()
        self.setup_DecryptDirectory()
        
        # Add nav_tree and cmd_stack to top section
        top_section.addWidget(self.nav_tree)
        top_section.addWidget(self.cmd_stack)
        
        # Create widget for top section
        top_widget = QWidget()
        top_widget.setLayout(top_section)
        
        # Output display (bottom section)
        self.output_display = OutputDisplay(self.agent_repository)
        
        # Create splitter to divide top and bottom sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(top_widget)
        splitter.addWidget(self.output_display)
        
        # Set initial sizes 
        splitter.setSizes([480, 520])
        
        # Add splitter to main layout
        main_layout.addWidget(splitter)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        self.setLayout(main_layout)

    def setup_command_prompt(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        self.cmd_input = QTextEdit()  
        self.cmd_input.setPlaceholderText("Enter command...")
        self.cmd_input.setMinimumHeight(100)
        self.send_btn = QPushButton("Queue Command")
        self.send_btn.clicked.connect(self.send_command) 

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(self.cmd_input)
        layout.addWidget(self.send_btn)
        layout.addWidget(docs_button)
        widget.setLayout(layout)
        
        self.cmd_stack.addWidget(widget)

    def send_command(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = self.cmd_input.toPlainText().strip()
        if not command:
            return

        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Command queued!")
            self.cmd_input.clear()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to send command: {str(e)}")

    def setup_WinGetPS_script(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Add toolbar for common operations
        toolbar = QHBoxLayout()
        load_btn = QPushButton("Load Script")
        save_btn = QPushButton("Save Script")
        clear_btn = QPushButton("Clear")
        
        # Load button functionality
        load_btn.clicked.connect(lambda: QFileDialog.getOpenFileName(
            self, "Load PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0] and open(QFileDialog.getOpenFileName(
            self, "Load PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0], 'r', encoding='utf-8').read() 
        and self.script_editor.setText(open(QFileDialog.getOpenFileName(
            self, "Load PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0], 'r', encoding='utf-8').read()))
        
        # Save button functionality
        save_btn.clicked.connect(lambda: QFileDialog.getSaveFileName(
            self, "Save PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0] and open(QFileDialog.getSaveFileName(
            self, "Save PowerShell Script", "", 
            "PowerShell Scripts (*.ps1);;All Files (*.*)"
        )[0], 'w', encoding='utf-8').write(self.script_editor.toPlainText()))
        
        # Clear button functionality
        clear_btn.clicked.connect(lambda: QMessageBox.question(
            self, "Clear Script", "Are you sure you want to clear the script editor?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes and self.script_editor.clear())
        
        toolbar.addWidget(load_btn)
        toolbar.addWidget(save_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        

        self.script_editor = QTextEdit()
        self.script_editor.setPlaceholderText("Enter PowerShell script...")
        default_text = ("""
$logFile = "C:\\Temp\\log.txt";
$host = Get-Host;
Set-Content $logFile $host;
$proc = Get-ExecutionPolicy;
Add-Content $logFile -Value $proc;""")
        self.script_editor.setText(default_text.strip())

        run_btn = QPushButton("Run Script")
        run_btn.clicked.connect(self.send_WinGetPS) 

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel) 
        
        layout.addLayout(toolbar)
        layout.addWidget(self.script_editor)
        layout.addWidget(run_btn)
        layout.addWidget(docs_button)
        widget.setLayout(layout)
        
        self.cmd_stack.addWidget(widget)

    def send_WinGetPS(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        script = self.script_editor.toPlainText().strip()
        command = "execute_module|ExecuteWinGetPS"

        try:
            self.module_handler.execute_winget_ps(self.current_agent_id, script)
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Script queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_BasicRecon(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module performs basic reconnaissance by executing SystemInfo and arp -a")
        explanation.setWordWrap(True)  # Allows text to wrap naturally
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create the button
        recon_btn = QPushButton("Queue Module")
        recon_btn.clicked.connect(self.send_BasicRecon)  

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add widgets to layout
        layout.addWidget(explanation)
        layout.addWidget(recon_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_BasicRecon(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|BasicRecon"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_DiscoverPII(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module recursively scans text files in a directory to identify potential PII (such as phone numbers, SSNs, and dates)")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # Directory Path input
        dir_label = QLabel("Directory Path:")
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Enter directory path...")
        self.dir_input.setToolTip(
            "Enter the directory path as it appears on the target system\n"
            "Example: C:\\Users\\Administrator\\Documents\\"
        )
        
        # Context Length input
        context_label = QLabel("Context Length:")
        self.context_input = QSpinBox()
        self.context_input.setRange(1, 1000)
        self.context_input.setValue(30)  # Default value
        
        # Add parameters to grid layout
        param_layout.addWidget(dir_label, 0, 0)
        param_layout.addWidget(self.dir_input, 0, 1)
        param_layout.addWidget(context_label, 1, 0)
        param_layout.addWidget(self.context_input, 1, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        recon_btn = QPushButton("Queue Module")
        recon_btn.clicked.connect(self.send_DiscoverPII)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(recon_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_DiscoverPII(self):  
        dir_path = self.dir_input.text()
        context_length = self.context_input.value()     
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|DiscoverPII|{dir_path},{context_length}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}") 

    def setup_PortScanner(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module performs TCP port scanning by attempting socket connections to specified IP addresses and ports")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # IP input
        ip_label = QLabel("Target IPs: ")
        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("192.168.1.1")
        self.ip_input.setToolTip(
            "You can also specify in CIDR Notation"
            "Example: 192.168.1.1/24"
        )
        
        # Port input
        port_label = QLabel("Ports: ")
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("20-25,53,80")
        self.port_input.setToolTip(
            "Accepts ranges specified with a dash, or comma separated values"
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(ip_label, 0, 0)
        param_layout.addWidget(self.ip_input, 0, 1)
        param_layout.addWidget(port_label, 1, 0)
        param_layout.addWidget(self.port_input, 1, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        scanner_btn = QPushButton("Queue Module")
        scanner_btn.clicked.connect(self.send_PortScanner)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(scanner_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_PortScanner(self):  
        ips = self.ip_input.text()
        ports = self.port_input.text()     
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|PortScanner|{ips}%2C{ports}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")     

    def setup_DenyOutboundFirewall(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module blocks outbound traffic through netsh for targeted executable names found in Program Files")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # IP input
        targetfile_label = QLabel("Target File Names: ")
        self.targetfile_input = QTextEdit()
        self.targetfile_input.setPlaceholderText("csfalconservice, sentinelone, cylancesvc, SEDservice")
        self.targetfile_input.setToolTip(
            "Not case sensitive, comma separated list only."
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(targetfile_label, 0, 0)
        param_layout.addWidget(self.targetfile_input, 1, 0)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        targetfile_btn = QPushButton("Queue Module")
        targetfile_btn.clicked.connect(self.send_DenyOutboundFirewall)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(targetfile_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_DenyOutboundFirewall(self):  
        param1 = self.targetfile_input.toPlainText().strip() 
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|DenyOutboundFirewall|{param1}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")       

    def setup_HostFileURLBlock(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module blocks outbound traffic through the host file by setting target URL IPs to 127.0.0.1")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        # IP input
        targetURL_label = QLabel("Target URLs: ")
        self.targetURL_input = QTextEdit()
        self.targetURL_input.setPlaceholderText("example1.com, example2.com")
        self.targetURL_input.setToolTip(
            "Not case sensitive, comma separated list only."
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(targetURL_label, 0, 0)
        param_layout.addWidget(self.targetURL_input, 1, 0)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        targetURL_btn = QPushButton("Queue Module")
        targetURL_btn.clicked.connect(self.send_HostFileURLBlock)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(targetURL_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_HostFileURLBlock(self):  
        param1 = self.targetURL_input.toPlainText().strip() 
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|HostFileURLBlock|{param1}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")  

    def setup_RunAsUser(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module re-launches the agent as the specified user")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        param1_label = QLabel("Username: ")
        self.param1_input = QLineEdit()
        self.param1_input.setPlaceholderText("Administrator")
        
        param2_label = QLabel("Password: ")
        self.param2_input = QLineEdit()
        self.param2_input.setPlaceholderText("hunter2")
        
        # Add parameters to grid layout
        param_layout.addWidget(param1_label, 0, 0)
        param_layout.addWidget(self.param1_input, 0, 1)
        param_layout.addWidget(param2_label, 1, 0)
        param_layout.addWidget(self.param2_input, 1, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_RunAsUser)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_RunAsUser(self):  
        username = self.param1_input.text()
        password = self.param2_input.text()     
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|RunAsUser|{username},{password}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")     

    def setup_AddAdminUser(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module creates the specified user and adds them to the Local Administrators group")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        adminusername_label = QLabel("Username: ")
        self.adminusername_input = QLineEdit()
        self.adminusername_input.setPlaceholderText("TestUser")
        
        adminpassword_label = QLabel("Password: ")
        self.adminpassword_input = QLineEdit()
        self.adminpassword_input.setPlaceholderText("P@ssw0rd123!")

        adminfullname_label = QLabel("Full Name: ")
        self.adminfullname_input = QLineEdit()
        self.adminfullname_input.setPlaceholderText("John Hacker")
        
        # Add parameters to grid layout
        param_layout.addWidget(adminusername_label, 0, 0)
        param_layout.addWidget(self.adminusername_input, 0, 1)
        param_layout.addWidget(adminpassword_label, 1, 0)
        param_layout.addWidget(self.adminpassword_input, 1, 1)
        param_layout.addWidget(adminfullname_label, 2, 0)
        param_layout.addWidget(self.adminfullname_input, 2, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_AddAdminUser)

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_AddAdminUser(self):  
        username = self.adminusername_input.text()
        password = self.adminpassword_input.text()    
        fullname = self.adminfullname_input.text()
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|AddAdminUser|{username},{password},{fullname}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_AddScriptToRegistry(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module adds the agent script to the user's CurrentVersion\\Run registry")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                font-size: 16pt;
                padding: 2px;
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        regvalue_label = QLabel("Key Name: ")
        self.regvalue_input = QLineEdit()
        self.regvalue_input.setPlaceholderText("StartUp")
        self.regvalue_input.setToolTip(
            "This is just the name of the entry that will be created."
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(regvalue_label, 0, 0)
        param_layout.addWidget(self.regvalue_input, 0, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_AddScriptToRegistry)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_AddScriptToRegistry(self):  
        regvalue = self.regvalue_input.text()

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|AddScriptToRegistry|{regvalue}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_CreateScheduledTask(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module adds a recurring scheduled task. With inputs empty, it will add task to launch the agent.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        taskname_label = QLabel("Task Name: ")
        self.taskname_input = QLineEdit()
        self.taskname_input.setPlaceholderText("ScheduledTask")
        
        action_label = QLabel("Action: ")
        self.action_input = QLineEdit()
        self.action_input.setPlaceholderText('"App.exe" /param1')

        delay_label = QLabel("Delay (Hours): ")
        self.delay_input = QSpinBox()
        self.delay_input.setToolTip(
            "The task will execute every 24hrs after the delay"
        )
        self.delay_input.setRange(1, 1000)
        
        # Add parameters to grid layout
        param_layout.addWidget(taskname_label, 0, 0)
        param_layout.addWidget(self.taskname_input, 0, 1)
        param_layout.addWidget(action_label, 1, 0)
        param_layout.addWidget(self.action_input, 1, 1)
        param_layout.addWidget(delay_label, 2, 0)
        param_layout.addWidget(self.delay_input, 2, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_CreateScheduledTask)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_CreateScheduledTask(self):  
        taskname = self.taskname_input.text()
        action = self.action_input.text()    
        delay = self.delay_input.value()
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|CreateScheduledTask|{taskname},{action},{delay}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_InstallMSI(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module attempts to download and silently install the specified MSI file. Installs PuTTY by default.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        URL_label = QLabel("Download URL: ")
        self.URL_input = QLineEdit()
        self.URL_input.setPlaceholderText("https://the.earth.li/~sgtatham/putty/latest/w64/putty-64bit-0.82-installer.msi")
        
        downloadpath_label = QLabel("Download Path: ")
        self.downloadpath_input = QLineEdit()
        self.downloadpath_input.setPlaceholderText("putty-install.msi")

        installdir_label = QLabel("Install Directory: ")
        self.installdir_input = QLineEdit()
        self.installdir_input.setPlaceholderText("C:\\Users\\user1\\AppData\\Local")
        
        # Add parameters to grid layout
        param_layout.addWidget(URL_label, 0, 0)
        param_layout.addWidget(self.URL_input, 0, 1)
        param_layout.addWidget(downloadpath_label, 1, 0)
        param_layout.addWidget(self.downloadpath_input, 1, 1)
        param_layout.addWidget(installdir_label, 2, 0)
        param_layout.addWidget(self.installdir_input, 2, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_InstallMSI)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_InstallMSI(self):  
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        
        params = [param for param in [
            self.URL_input.text(),
            self.downloadpath_input.text(),
            self.installdir_input.text()
        ] if param]
        
        command = f"execute_module|InstallMSI|{','.join(params)}"

        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_RDPConnect(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module connects to a host via RDP and installs the agent")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        hostname_label = QLabel("Hostname/IP: ")
        self.hostname_input = QLineEdit()
        self.hostname_input.setPlaceholderText("192.168.124.125")
        
        username_label = QLabel("Username: ")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Administrator")

        password_label = QLabel("Password: ")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("hunter2")

        domain_label = QLabel("Domain: ")
        self.domain_input = QLineEdit()
        self.domain_input.setPlaceholderText("lab.local")
        self.domain_input.setToolTip(
            "This parameter is optional"
        )

        serverIP_label = QLabel("C2 Server IP: ")
        self.serverIP_input = QLineEdit()
        self.serverIP_input.setPlaceholderText("192.168.124.22")
        self.serverIP_input.setToolTip(
            "This is the IP you want the new agent to connect to"
        )
        
        # Add parameters to grid layout
        param_layout.addWidget(hostname_label, 0, 0)
        param_layout.addWidget(self.hostname_input, 0, 1)
        param_layout.addWidget(username_label, 1, 0)
        param_layout.addWidget(self.username_input, 1, 1)
        param_layout.addWidget(password_label, 2, 0)
        param_layout.addWidget(self.password_input, 2, 1)
        param_layout.addWidget(domain_label, 3, 0)
        param_layout.addWidget(self.domain_input, 3, 1)
        param_layout.addWidget(serverIP_label, 4, 0)
        param_layout.addWidget(self.serverIP_input, 4, 1)
        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_RDPConnect)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_RDPConnect(self):  
        hostname = self.hostname_input.text()
        username = self.username_input.text()    
        password = self.password_input.text()
        domain = self.domain_input.text()
        serverIP = self.serverIP_input.text()

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|RDPConnect|{hostname},{username},{password},{serverIP},{domain}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_EncryptDirectory(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module encrypts the target directory with the specified password")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        directory_label = QLabel("Directory: ")
        self.directory_input = QLineEdit()
        self.directory_input.setPlaceholderText("C:\\Users\\Administrator\\Documents")
        self.directory_input.setToolTip(
            "Enter the full file path as it appears on the target system"
        )
        
        encryptpassword_label = QLabel("Password: ")
        self.encryptpassword_input = QLineEdit()
        self.encryptpassword_input.setPlaceholderText("P@ssw0rd123!")
        
        # Add parameters to grid layout
        param_layout.addWidget(directory_label, 0, 0)
        param_layout.addWidget(self.directory_input, 0, 1)
        param_layout.addWidget(encryptpassword_label, 1, 0)
        param_layout.addWidget(self.encryptpassword_input, 1, 1)

        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_EncryptDirectory)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_EncryptDirectory(self):  
        directory = self.directory_input.text()
        password = self.encryptpassword_input.text()    

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|EncryptDirectory|{directory},{password}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_DecryptDirectory(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module decrypts the target directory with the specified password")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        decrypt_directory_label = QLabel("Directory: ")
        self.decrypt_directory_input = QLineEdit()
        self.decrypt_directory_input.setPlaceholderText("C:\\Users\\Administrator\\Documents")
        self.decrypt_directory_input.setToolTip(
            "Enter the full file path as it appears on the target system\n"
        )
        
        decryptpassword_label = QLabel("Password: ")
        self.decryptpassword_input = QLineEdit()
        self.decryptpassword_input.setPlaceholderText("P@ssw0rd123!")
        
        # Add parameters to grid layout
        param_layout.addWidget(decrypt_directory_label, 0, 0)
        param_layout.addWidget(self.decrypt_directory_input, 0, 1)
        param_layout.addWidget(decryptpassword_label, 1, 0)
        param_layout.addWidget(self.decryptpassword_input, 1, 1)

        
        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_DecryptDirectory)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_DecryptDirectory(self):  
        directory = self.decrypt_directory_input.text()
        password = self.decryptpassword_input.text()    

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|DecryptDirectory|{directory},{password}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_UnhookNTDLL(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module will attempt to unhook NTDLL by restoring a clean version from sys32")
        explanation.setWordWrap(True)  # Allows text to wrap naturally
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create the button
        UnhookNTDLL_btn = QPushButton("Queue Module")
        UnhookNTDLL_btn.clicked.connect(self.send_UnhookNTDLL)  

        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add widgets to layout
        layout.addWidget(explanation)
        layout.addWidget(UnhookNTDLL_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_UnhookNTDLL(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|UnhookNTDLL"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_DomainTrustRecon(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module enumerates trusted domains in the current Active Directory environment")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_DomainTrustRecon)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_DomainTrustRecon(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|DomainTrustRecon"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_EnumerateDCs(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module identifies all Domain Controllers in the current domain")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_EnumerateDCs)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_EnumerateDCs(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|EnumerateDCs"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_IdentifyDomainAdmins(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module enumerates all members of the Domain Admins group, providing visibility into high-privilege account holders in the domain.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_IdentifyDomainAdmins)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_IdentifyDomainAdmins(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|IdentifyDomainAdmins"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_CheckUnconstrainedDelegation(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module identifies computers with unconstrained delegation enabled, which could represent potential security vulnerabilities in the domain.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_CheckUnconstrainedDelegation)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_CheckUnconstrainedDelegation(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|CheckUnconstrainedDelegation"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_ActiveUserMembership(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        explanation = QLabel("This module enumerates all group memberships for the currently active user, providing a comprehensive view of the user's permissions and access levels within the domain.")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)
        self.font_manager.add_relative_font_widget(explanation, 2)
        
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_ActiveUserMembership)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        layout.addWidget(explanation)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)

    def send_ActiveUserMembership(self):
        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return
        command = "execute_module|ActiveUserMembership"
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")

    def setup_CMSTP_UAC_Bypass(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # Create and style the explanation label
        explanation = QLabel("This module uses CMSTP to auto accept UAC prompt and launch command elevated")
        explanation.setWordWrap(True)
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_style = self.styleSheet()
        explanation.setStyleSheet(base_style + """
            QLabel {
                border: 1px solid #000000;
                background-color: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #424242, stop:1 #303030); 
            }
        """)

        self.font_manager.add_relative_font_widget(explanation, 2)
        
        # Create parameter inputs
        param_widget = QWidget()
        param_layout = QGridLayout() 
        
        command_label = QLabel("Command: ")
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText("calc.exe")
        
        # Add parameters to grid layout
        param_layout.addWidget(command_label, 0, 0)
        param_layout.addWidget(self.command_input, 0, 1)

        param_widget.setLayout(param_layout)
        
        # Create the button
        module_btn = QPushButton("Queue Module")
        module_btn.clicked.connect(self.send_CMSTP_UAC_Bypass)
        
        docs_button = QPushButton(" Show Documentation ")
        docs_button.setIcon(QIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView)))
        docs_button.clicked.connect(self.doc_panel.toggle_panel)
        
        # Add all widgets to main layout
        layout.addWidget(explanation)
        layout.addWidget(param_widget)
        layout.addWidget(module_btn)
        layout.addWidget(docs_button)
        
        widget.setLayout(layout)
        self.cmd_stack.addWidget(widget)  

    def send_CMSTP_UAC_Bypass(self):  
        command = self.command_input.text()  

        if not self.current_agent_id:
            QMessageBox.warning(self, "Warning", "No agent selected!")
            return

        command = (f"execute_module|CMSTP_UAC_Bypass|{command}")
        try:
            self.agent_repository.update_agent_command(self.current_agent_id, command)
            self.show_tooltip(self.cmd_input, self.send_btn, "Module queued!")
        except Exception as e:
            import traceback
            logger.log_message(f"Error on line {traceback.extract_tb(e.__traceback__)[-1].lineno}")
            QMessageBox.warning(self, "Error", f"Failed to send: {str(e)}")


    def on_nav_changed(self, current, previous):
        if not current:
            return
                
        # Map tree items to stack indices
        command_map = {
            "Command Execution": 0,
            "WinGet PS Execution": 1,
            "Basic Recon": 2,
            "Discover PII": 3,
            "Enumerate DCs": 4,
            "Domain Trusts": 5,
            "Domain Admins": 6,
            "Unconstrained Delegation": 7,
            "Active User Membership": 8,
            "Port Scanner": 9,
            "Deny Outbound Firewall": 10,
            "Host File URL Block": 11,
            "Unhook NTDLL": 12,
            "CMSTP UAC Bypass": 13,
            "Run As User": 14,
            "Add Admin User": 15,
            "Add Startup to Registry": 16,
            "Add Scheduled Task": 17,
            "Install MSI": 18,
            "RDP Connection": 19,
            "Encrypt Files": 20,
            "Decrypt Files": 21,
        }
        
        command_name = current.text(0)
        if command_name in command_map:
            self.cmd_stack.setCurrentIndex(command_map[command_name])
            
            # Get the full path from root to current item
            path_parts = []
            item = current
            while item:
                path_parts.insert(0, item.text(0))
                item = item.parent()
                
            # Construct the documentation path
            doc_section = '.'.join(['Agents', 'Modules'] + path_parts)
            print(f"Looking for documentation section: {doc_section}")
            self.doc_panel.set_content(doc_section)

    def show_tooltip(self, widget, anchor_widget=None, message="Done!"):
        # Append tooltip styling
        self.setStyleSheet(self.styleSheet() + """
            QToolTip {
                color: #90EE90;               
                border: 1px solid #2E8B57;  
                padding: 5px;
            }
        """)
        
        # Get metrics to calculate text width
        font_metrics = widget.fontMetrics()
        text_width = font_metrics.horizontalAdvance(message)
        
        # If anchor_widget provided, position above its center
        if anchor_widget:
            anchor_rect = anchor_widget.rect()
            anchor_pos = anchor_widget.mapToGlobal(QPoint(
                anchor_rect.center().x() - (text_width // 2),
                anchor_rect.top()
            ))
        else:
            # Default positioning above the target widget
            anchor_pos = widget.mapToGlobal(widget.rect().topLeft())
        
        # Show tooltip with increased vertical offset
        QToolTip.showText(
            QPoint(anchor_pos.x(), anchor_pos.y() - 50),
            message,
            widget,
            widget.rect(),
            30000
        )

    def set_agent(self, agent_id: str):
        """Switch to monitoring a different agent"""
        self.current_agent_id = agent_id
        self.output_display.set_agent(agent_id)

    def cleanup(self):
        """Cleanup resources before widget destruction"""
        self.output_display.cleanup()