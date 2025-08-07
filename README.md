# BeaconatorC2

## --- Introduction ---



## --- Ethical Standards / Code of Conduct ---

This project has been started to help better test products, configurations, detection engineering, and overall security posture against a series of techniques that are being actively used in the wild by adversaries. We can only be successful at properly defending against evasive tactics, if we have the tools and resources to replicate the approaches being used by adversaries in an effective manner. Participation in this project and/or use of these tools implies good intent to use these tools ethically to help better protect/defend, as well as an intent to follow all applicable laws and standards associated with the industry. The views expressed as part of this project are the views of the individual contributors, and do not reflect the views of our employer(s) or any affiliated organization(s).  

## --- Instructions and Overview ---

This framework is structured with hierarchical folders, organized around relevant phases of MITRE ATT&CK. The agent and server provided in initial access, allow for the deployment of most other modules and phases. For red teams operating in the scope of an engagement, you may want to use this as part of a more stealthy approach; such as using AutoPwnKey for initial access to drop some other beacon, then possibly deploy other evasive AHK payloads later managed via AutoPwnKey C2. For blue/purple teams it is far easier - just adapt and run these things and see if your AV/EDR or other tools detect them.  If they do not, open a ticket with your vendors and help raise awareness. If they do catch these tactics right away, also share that and help share successes related to security vendors who are doing a good job of covering these use cases. Sometimes as defenders it seems like the deck is stacked against us. By aligning exploit and evasion research with control refinement and detection engineering, we can both find gaps and also opportunities to better protect and respond.  
## --- How to Contribute ---

We welcome and encourage contributions, participation, and feedback - as long as all participation is legal and ethical in nature. Please develop new scripts, contribute ideas, improve the scripts that we have created. The goal of this project is to come up with a robust testing framework that is available to red/blue/purple teams for assessment purposes, with the hope that one day we can archive this project because improvements to detection logic make this attack vector irrelevant.

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## --- Acknowledgments ---

Key contributors, both directly and because we are using building blocks from prior work:

- [shammahwoods](https://github.com/shammahwoods) 
- [BiniamGebrehiwot1](https://github.com/BiniamGebrehiwot1)
- Jordan Mastel
- lolrmm.io
- [christian-taillon](https://github.com/christian-taillon)
- [Duncan4264](https://github.com/Duncan4264)
- [flawdC0de](https://github.com/flawdC0de)
- [Kitsune-Sec](https://github.com/Kitsune-Sec)
- [AnuraTheAmphibian](https://github.com/AnuraTheAmphibian)
- Tomer Saban
- Matt Clark
- Brandon Stevens
- Daniel Addington
