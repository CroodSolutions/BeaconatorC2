## ClickFix and Fake CAPTCHA

ClickFix attacks, often involving Fake CAPTCHA lures, have become one of the fastest growing vectors for initial access. As of the time of this writing, the overall awareness level surrounding ClickFix seems to remain relatively low, compared with other initial access vectors. We build on existing BeaconatorC2 capabilities, as we seek to make it easier and more practical to setup a ClickFix/Fake CAPTCHA demos and testing. Although, the initial focus is awareness demos and basic testing of detectability, hopefully this also provides a jumping off point for Read Teamers looking to include ClickFix in Social Engineering engagements.  

### Example Demo Video of ClickFix via BeaconatorC2

This video provides a simple proof-of-concept demo of combining web delivery with BeaconatorC2 for adversary emulation of ClickFix style attacks.  



https://github.com/user-attachments/assets/5044de63-9c52-46c4-8a2a-1a6314f84a8c



### Role of Fake CAPTCHA Delivery vs ClickFix and BeaconatorC2

Attacks involving ClickFix and Fake CAPTCHA typically involve a few key elements:
 - Delivery Mechanism: For real attacks it is usually either an email/chat, compromised legitimate web site, or a sponsored advertisement.
 - A viable payload and C2 framework.
 - The web delivery mechanism to serve up the payload to the clipboard.
 - Social Engineering language and visuals rendered to convince the user to run the payload.
 - Convincing follow-on experience so the end user does not suspect anything. 


Note: Sponsoring malicious advertisements (Malvertizing) is not appropriate for red team engagements to test ClickFix attacks, because they may catch unintended victims or exceed the scope of authorized testing. We do not recommend Malvertizing vectors for penetration tests, unless you come up with some sort of iron clad scoping mechanism beyond what we have thought of so far. For simulation, maybe something could be done with host files or on-prem DNS to simulate the real experience? This could have some risks though, so buyer beware.  

## Testing / Adversary Emulation of ClickFix

### Link to ClickFix and Fake CAPTCHA Project

As mentioned above, BeaconatorC2 and the payloads provided here, should provide a viable foundation to get up and running quickly with a ClickFix style payloads. However, the delivery of these payloads via a website and the simulation of the type of user experience that would not set off (human) red flags could be considered another matter entirely. As such, we have setup a secondary repo for the Fake CAPTCHA, web delivery, and other elements required for successful adversary emulation of ClickFix style attack vectors.  

### Testing on Windows

For the SE aspect of ClickFix and Fake CAPTCHA, refer to the supplemental repo for payload delivery. That said, the [simple_cmd-oneline_clickfix.txt](https://github.com/CroodSolutions/BeaconatorC2/blob/main/beacons/ClickFix_Testing/simple_cmd-oneline_clickfix.txt) should provide a workable payload to test with as a jumping off point.


### Testing on MacOS

For the SE aspect of ClickFix and Fake CAPTCHA, refer to the supplemental repo for payload delivery. That said, the [zsh_oneliner_beacon.sh](https://github.com/CroodSolutions/BeaconatorC2/blob/main/beacons/zsh_oneliner_beacon.sh) and instructions should provide a workable payload as a foundation.  

### Testing on Linux

For the SE aspect of ClickFix and Fake CAPTCHA, refer to the supplemental repo for payload delivery. That said, the [bash_oneliner_beacon.sh](https://github.com/CroodSolutions/BeaconatorC2/blob/main/beacons/bash_oneliner_beacon.sh) and instructions should provide a workable payload as a foundation.  

## Legal and Ethical Note

These tools and resources are created for organizations looking to test and improve their security posture, elevate awareness, or for red teams helping companies with these goals. Use these resources only legally, ethically, under well-scoped testing agreements, and in alignment with all applicable laws and standards.  
