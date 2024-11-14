Utility that converts LMMS files to Midi files.

Example project and exported midi can be found in the repository.

Requirements
---------------
- Python 3.12+ with xml and midiutil packages installed.
- mmp2midi.py script included in repository.
- .mmpz or .mmp LMMS project file.

Usage
---------------
1. Open command prompt and navigate to the folder where mmp2midi.py is located.
2. Type `python mmp2midi.py ` and then include the path to the project file, or folder with project files you wish to convert.
3. Open the folder with the project file and find your output midi file(s).

Known Issues
---------------
- Automation interpolation is not supported, and will only sound correct when using constant mode in LMMS automation.
- FX channel sending is not supported.
- Effects, excluding the Delay effect, are not supported.
- Beat/Bassline tracks are not supported.
- Sample tracks are not supported.
- Tracks of types besides Soundfont Player are not supported.
- Time signatures with denominators that are not powers of 2 are not supported.
- Time signature automation will ignore denominator only changes.
- Automation events occuring at the same time will have what would be percieved in the LMMS editor as a "previous" event overriding the "next" event.

Acknowledgements
---------------
Original script found here: https://github.com/mohamed--abdel-maksoud/mmp2midi/tree/master
