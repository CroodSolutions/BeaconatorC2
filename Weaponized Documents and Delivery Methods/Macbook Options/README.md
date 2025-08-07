An interesting implication of RMM abuse is that Apple introduces several obstacles to delivering malware to MacBook devices, when compared to Windows. Is RMM a cheatcode to get around a few of these barriers?

For Microsoft Windows, you can simply create something malicious, and if it is not detected as bad and if application control is not in place, it will run. Of course, there is userland vs. admin and Mark-of-the-Web/UAC to contend with there. Still, the bar to get some sort of code to run is often quite low. 

For weaponized office documents they seem to run in a sandbox on MacBook, and moving a docm removes the "This Document" trigger that runs on-open; moreover, all of the really interesting MacScript command capabilities have been deprecated within VBA (I was able to run calc, but VBA could not download a file from the web, establish a network connection, or run anything). 

There is a trick still in Word where you can press Command+Fn+F9 and a set of braces will occur in the word doc, and then you can type MACROBUTTON in the braces followed by the macro you want to run, then press Fn+F9 again. An inconspicuous string of text called 'Run Automation' will appear, which with an appropriate lure may induce a user trigger the macro, but again - there is nothing that interesting that I could find to trigger. MS Excel was a little more promising, with the ability to add a button to trigger a macro, but have not tested that much yet, since I could not find very much that can be done from the macros without a new sandbox escape. 

It is easy enough to create malicious sh scripts, apps, or DMGs and they will run just fine on the host they are created on. Move the App or DMG to another host without signing and registering it, and it is untrusted and labeled as potential malware right away. Languages such as Go and Python also work, but most scenarios with Go/Python/sh require chmod +x, followed by ./ from terminal. Having to run from terminal with multiple steps is not the easiest Social Engineering bar for a red teamer, compared with Windows where you can open a document and at worst maybe get a UAC prompt.

Simply put, Apple has taken several steps for MacOS that make it harder to deliver malware to hosts, compared with Microsoft Windows, all things considered.

This is where RMM is interesting. Since these tools have a valid cert and are trusted as legitimate software that people expect to seamlessly deploy from a customer tenant, installing RMM tools seems like a lower bar to reach than malware. It is like a RAT with a trust hierarchy established and maintained by the Remote Management tool vendor.   

Since many RMM tools provide a DMG or PKG with a valid cert and everything you need to install / deploy on MacOS, there is little need to do much else.

That said, just for fun we have provided a .sh script that will reach out to a URL, download a file, and run it on MacOS. If an admin password is required, the user receives a prompt. Short of chmod +x and then running from terminal, here are steps that probably could make it more portable, but only assuming you have a valid code signing certificate and register your version of the script with apple:
 - Update the script to include your download link (remember you may want to use F12/network to find the real download link).
 - Launch Automator on a MacBook:
 - Select New Document.
 - Select Application.
 - Select Utilities and Run Shell Script.
 - Paste in the script from this repo (DownloadAndInstall.sh).
 - Go to File, Export, and select a valid code signing certificate.
 - Register your application with Apple (have read about this process, but have not tested this step yet).
 - Deliver as Application.

Note that this process should work for a wide range of payload types, assuming properly signed and registered/approved. For code signing Apple applications, you need a $99 developer subscription + following the process to create a code signing certificate and then register your application. 
(again, a lot I do not know about the registration aspect, since still testing that part)

Footnote: It was possible to use VBA to extract a hidden payload from the document and write it to disk with a filename and extention of choice, but since I could not figure out a good way to run it from VBA, it seemed irrelevant unless combined with a way to escape the sandbox and run something.

Key point: Only use red team tools or ideas in the scope of ethical and legal testing to improve defensive posture.
