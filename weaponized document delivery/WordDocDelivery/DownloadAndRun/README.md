# Summary 

This is a red team testing script for a weaponized document delivery of any AutoRMM, AutoPwnKey, or Beaconator payload that can be delivered as an executable. Minimal adaptation of this script could make it work for MSI or other file types. The document opens causing the ThisDocument script launch Module1 'Retrieve File' that in turn downloads a file from a staging location, writes it to disk, and then runs it with the silent flag. 

# Setup Steps
 - Create your lure document - should include some pretext for clicking "Enable Content" for realistic testing (save as .docm). 
 - Stage your payload in accordance with the appropriate testing framework for your testing (e.g., AutoRMM, AutoPwnKey, or Beaconator).
 - Payload should be staged with an absolute link the script can reach (sometimes there are http pages you need to click through, so use debug to get through these to the real link). 
 - Launch VBA Editor via the Developer tab or ALT+F11.
 - Paste Normal_ThisDocument.txt under Normal > Microsoft Word Objects > ThisDocument.
 - Then, paste Module1_RetrieveFile.txt into Normal > Modules > Module1.
 - Save/close VBA editor.
 - Save doc.
 - Test your scenario.

# Key points
 - Large install files take time to download and launch, making it fine for purple team testing, but could cause some sporadic abandoned deliveries for red team engagements.
 - This approach works best for red teams when the delivery payload is small or there is a pretext to make the user expect the document to take time to load. 
 - Macro enabled documents are considered sus by many security products, and sandboxing solutions seem to catch this with ease, so milage may vary.
 - Combining tactics, such as delivering the document via vmdk, password protected zip, or other creative means may help red teams.  

# Ethical Considerations 

These tools are made to help raise awarness about some serious security gaps adversaries are exploiting in the wild, by providing penetration testing / red team resources. Use of these tools assume an ethical blue/purple/red team scenario where you are using these tools to ethically test your security posture and controls. We do not support or endorse malicious or criminal use of assessment, security, or administrative tools.


# Example / Demo

Note: No audio / lots of load time, so feel free to time travel.  :)

https://github.com/user-attachments/assets/f06517a2-9842-499c-b350-7bf44c06f955

