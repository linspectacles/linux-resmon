# linux_resmon
The Linux Resource Monitor, a python equivalent of the Windows Resource Monitor (resmon.exe) | Standalone applet for the Linspector Suite ecosystem.

Hello, world!

<b>First things first?</b>
I am NOT A PROGRAMMER. I simply had fun prompting Gemini to output all the python codes you will find in this repository.

<b>OK, now about the concept?</b>
I looked extensively for this, but I could not find a like-for-like equivalent of the Microsoft Windows Resource Monitor (resmon.exe) for Linux. All options I found were almost exclusively similar to the Task Manager or Process Monitor, but those did not interest me as I needed something graphical that could tell me disk usage (inc. rates) plus network usage (inc. outgoing IPs, etc.) and, for that purpose, not having to use too many separate TUIs like atop, etc. Also a thread that inspired me do this is an old reddit post that can be found here: https://www.reddit.com/r/linux/comments/knzzq/is_there_a_linux_equivalent_of_windows_7s/.

<img width="480" height="270" alt="Screenshot_20260730_110103" src="https://github.com/user-attachments/assets/4c208abe-039c-456d-a88d-0caa8352b2f6" />
<img width="480" height="270"alt="Screenshot_20260730_110116" src="https://github.com/user-attachments/assets/c9efc95b-ee68-49cc-91c7-2785dcf40196" />

<b>OK, so what did I do?</b>
As I have no coding experience, I asked Gemini to code this for me so it came up with the ".py" files you see. 

<b>OK, now tell me about the files?</b>
The files in the "Main" branch are the latest and greatest. The files in the "Archive" branch were previous versions. All the versions uploaded here represent the evolution of the concept, for you to have a look and audit, use and fork, and do as you well please (I think I put it under GPL3). All versions were tested only on Fedora 44 KDE. I did not test this on any other DEs or non-systemd systems. I did not test this on any Arch/Debian-derivative either. But because they are written in python, I believe they should work cross-platform.

<b>OK, how do I run this?</b>
1. Ensure you have the required dependencies: python3, python3-pyqt6 and python3-psutil (attention: Version 4 needs more!).
2. Download the python file(s) you wish.
3. Ensure you're on the same directory of the file or navigate to it.
4. On the terminal, launch it by typing "python3" + the name of the file you want to try.
4. Alternatively, you can grant "executable" permissions to the file and launch it via your file manager.
5. Have fun!

<strong>Current version: Version 23.</strong>
- Manually modified the headers to align with my other projects.
- Rest of the change log in the "Archive" branch (https://github.com/brunonlinespace/resmon.py/tree/archive).

<hr>
<p>I thought this was a fun little project so I decided to share it in case you find it fun/useful too. You can help me make it better, but I do not plan to spend much time on this project unless it really does take off. I have no clue about python (yet?). I am also new in GitHub so please be kind to me :-P</p>
