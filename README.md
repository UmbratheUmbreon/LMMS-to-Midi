Utility that converts LMMS files to Midi files.

Example project and exported midi can be found in the repository.

Requirements
---------------
- Python 3.12+ with xml and midiutil packages installed.
- Modified MidiFile.py script included in repository.
- mmp2midi.py script included in repository.
- .mmpz or .mmp LMMS project file.

Usage
---------------
1. Open command prompt and navigate to the folder where mmp2midi.py is located.
2. Type `python mmp2midi.py ` and then include the path to the project file.
3. Open the folder with the project file and find your output midi file.

Known Issues
---------------
- Automation interpolation is not supported, and will only sound correct when using constant mode in LMMS automation.
- Drum patches besides patch 0 are not supported.
- FX channel sending is not supported.
- Effects, excluding the Delay effect, are not supported.
- Beat/Bassline tracks are not supported.
- Sample tracks are not supported.
- Tracks of types besides Soundfont Player are not supported.

Acknowledgements
---------------
Original script found here: https://github.com/mohamed--abdel-maksoud/mmp2midi/tree/master
