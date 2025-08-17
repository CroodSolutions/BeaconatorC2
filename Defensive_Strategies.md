As we look to the natural conclusions of this work, one thing that stands out is the fact that beacon after beacon; RMM after RMM, evades EDR. This comes down to a very difficult philisophical question of, what seperates a good agent from a bad agent? Is the job we expect EDR to do even feasible? I think not, which calls app control and other technologies to centerstage.  

The observation by @bohops that app control flaws are not taken seriously had me wracking my brain all day. After all, we all know that app control is arguably the most important line of defense against malware, since evading and subverting EDR has basically now been commoditized. Why is it not being taken seriously?

I am reminded of Eli Goldratt's work on the 'Theory of Constraints' (TOC) that he started popularizing with his 1984 book, The Goal. As long as the greatest bottleneck to securing an endpoint is EDR protection, App Control will not be the number one focus.  

Of course, since we know that EDR does not work reliably, we have a strange incongruence where the market recognizes it as the leading constraint/issue, while in reality other stopgap technologies are determining the difference between success and failure behind the scenes (App Control, FW, NDR, SWG, and so on). Of all of these, app control seems to be the most essential.  

So that we can properly shift our perspective to what is about to be our next constraint, app control, we need to realize a few things about EDR. To quote Goldratt again (2005), EDR is "necessary, but not sufficient" meaning that we need EDR, but it will in no way on its own accomplish what we expect of it.

Fundamentally, what we expect of EDR may actually be impossible. As mentioned previously, how can you tell what is bad, when the overlap can be substantial? They say one person's trash is another's treasure; one person's EDR or RMM is another person's RAT. If you allow programs to run, and these programs can establish a net socket, post some info, receive some info, and execute commands - you may have a RAT. Even if it has a valid certificate and trusted pedigree, malware is in the eye of the beholder. 

We need to level up. We need to continue our focus on AV/EDR to make sure we deploy, support, maintain, and improve it. However, we also need to recognize that these solutions will basically always fail to detect new threats in the end, and plan accordingly. This means the new baseline standard we should all be striving for on endpoints will be app control (+host fw), and all attention and effort should directed in that direction.

This means that when someone finds a way around an application control product, we should consider it a P1 issue, because it is one of our final lines of defense. And, if you are not using it, do not worry - soon you will be. 

Credit/contributors (direct and indirect): Shammahwoods, bohops, NathanMcNulty,0xBoku, BushidoToken, Christian Taillon, Cameron Kownack, James Biddle, Cyrus Duncan (and many others/see repo readme.md).
