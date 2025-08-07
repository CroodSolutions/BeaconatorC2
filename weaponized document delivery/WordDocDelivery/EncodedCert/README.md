# Summary 

This set of scripts is to deliver an executable as a certutil encoded payload, within appended text at the end of a Word Document, and then execute that payload. If using it with and AutoRMM payload, note that size could be a factor, as the larger install files will just error out. Of course, if you compile an executable from any of the scripts provided here and embed that, it should be small enough and would usually work.  

# Setup Steps
 - Create your lure document (should include some pretext for clicking "Enable Content" for realistic testing (save as .docm). 
 - Use certutil -encode to create a certfile using your desired executable (certutil -encode YourExe DesiredOutputName.pem).
 - Launch VBA Editor via the Developer tab or ALT+F11.
 - Paste LaunchText.txt under Normal > Microsoft Word Objects > ThisDocument.
 - Then, paste Delivery.txt into Normal > Modules > Module1.
 - Save/close VBA editor.
 - Save doc.
 - Test your scenario.

# Key points
 - This will only support small payloads, so an AutoIT/AHK compiled exe from AutoRMM will be fine, and some of the more reasonable sized RMM direct EXEs could work also (exactl limites not well defined).
 - Macro enabled documents are considered sus by many security products, and sandboxing solutions seem to catch this with ease, so milage may vary.

# Ethical Considerations 

These tools are made to help raise awarness about some serious security gaps adversaries are exploiting in the wild, by providing penetration testing / red team resources. Use of these tools assume an ethical blue/purple/red team scenario where you are using these tools to ethically test your security posture and controls. We do not support or endorse malicious or criminal use of assessment, security, or administrative tools.
