# BeaconatorC2

## --- Introduction ---

BeaconatorC2 was spawned out of several other research initiatives surrounding EDR evasion, LOLBINs, Escape to host flaws, and particularly scripting languages with portable interpreters like AutoIt and AutoHotkey. What we needed was a quick and easy process to setup beacons in restrictive or poorly documented languages and environments, such as WWB-COM, or AIX mainframes. We made BeaconatorC2 to fill that gap, providing a simple and modular communication standard and management application to support any type of beacon. This way, once we find new paths for execution, we can quickly build supported beacons for additional exploitation.

## --- Ethical Standards / Code of Conduct ---

This project has been started to help better test products, configurations, detection engineering, and overall security posture against a series of techniques that are being actively used in the wild by adversaries. We can only be successful at properly defending against evasive tactics, if we have the tools and resources to replicate the approaches being used by adversaries in an effective manner. Participation in this project and/or use of these tools implies good intent to use these tools ethically to help better protect/defend, as well as an intent to follow all applicable laws and standards associated with the industry. The views expressed as part of this project are the views of the individual contributors, and do not reflect the views of our employer(s) or any affiliated organization(s).  

## --- Instructions and Overview ---

### Getting Started
  Prerequisites

  - Python 3.8 or higher (Python 3.10+ recommended)
  - Git for cloning the repository
  - pip for installing Python packages

  Installation

  1. Clone the Repository

  git clone https://github.com/yourusername/BeaconatorC2.git
  cd BeaconatorC2

  2. Create a Virtual Environment (Recommended)

  Windows:
  python -m venv venv
  venv\Scripts\activate

  Linux/macOS:
  python3 -m venv venv
  source venv/bin/activate

  3. Install Required Packages

  pip install -r requirements.txt

  Note: On some Linux distributions, you may need to install additional system packages for PyQt6:
  #### Ubuntu/Debian
  sudo apt-get install python3-pyqt6 libgl1 libxcb-cursor0

  #### Fedora/RHEL
  sudo dnf install python3-pyqt6 mesa-libGL libxcb-cursor

  4. Run BeaconatorC2

  Windows:
  python BeaconatorC2-Manager.py

  Linux/macOS:
  python3 BeaconatorC2-Manager.py

  First Time Setup

  1. Launch the Application: The GUI will open with the main dashboard
  2. Configure Receivers: Navigate to the "Receivers" tab to set up your first receiver (TCP, HTTP,
  etc.)
  3. Deploy a Beacon: Use one of the example beacons in the beacons/ directory: `python beacons/simple_python_beacon.py --server 127.0.0.1 --port 5074`
  4. Assign Schema: When your beacon appears in the dashboard, rassign an appropriate
  schema (e.g., simple_python_beacon.yaml) in the beacon settings tab
  5. Execute Commands: Use the Command interface to interact with your beacon

  Quick Test

  To quickly verify your installation:

  1. Start BeaconatorC2-Manager
  2. Go to Receivers tab → Add New Receiver → TCP on port 5074
  3. In a separate terminal, run:
  python beacons/simple_python_beacon.py --server 127.0.0.1 --port 5074
  4. You should see the beacon appear in the main dashboard

  Optional: Metasploit Integration

  To enable Metasploit integration features:

  1. Install Metasploit Framework
  2. Start the RPC daemon:
`msf > load msgrpc ServerHost=127.0.0.1 ServerPort=55553 User=(user) Pass='(password)' SSL=false`
  3. Configure connection in BeaconatorC2 under the Metasploit tab

  Next Steps

  - Review the Architecture.md to understand the system design
  - Check the communication_standards.md for beacon protocol details
  - Explore the schemas/ directory to understand beacon capability definitions
  - See beacons/ for example beacon implementations in various languages

## --- How to Contribute ---

We welcome and encourage contributions, participation, and feedback - as long as all participation is legal and ethical in nature. Please develop new scripts, contribute ideas, improve the scripts that we have created. The goal of this project is to come up with a robust testing framework that is available to red/blue/purple teams for assessment purposes, with the hope that one day we can archive this project because improvements to detection logic make this attack vector irrelevant.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## --- Acknowledgments ---

Management interface for Beaconator created by [shammahwoods](https://github.com/shammahwoods) 

Key contributors, both directly and because we are using building blocks from prior work:

- 0xcc00 (for ntds_dump ideas)
- [christian-taillon](https://github.com/christian-taillon)
- [Duncan4264](https://github.com/Duncan4264)
- [flawdC0de](https://github.com/flawdC0de)
- [Kitsune-Sec](https://github.com/Kitsune-Sec)
- [AnuraTheAmphibian](https://github.com/AnuraTheAmphibian)
- Tomer Saban (inspiration for initial project)
- Matt Clark (MacOS research)
- Brandon Stevens (MacOS research)
- Daniel Addington (MacOS research)
- Jordan Mastel (RMM contributions, for interoperability)
- [BiniamGebrehiwot1](https://github.com/BiniamGebrehiwot1)
