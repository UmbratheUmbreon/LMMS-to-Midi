#!/usr/bin/python

"""
a standalone utility to convert mmp or mmpz files to midi files
(basically used to tinker with the mmp format)
authors: Mohamed Abdel Maksoud (mohamed at amaksoud.com), Alexis Archambault
maintainers: UmbratheUmbreon/BlueVapor1234
licence: GPL2
"""

import sys
import getopt
import zlib
import xml.etree.ElementTree as etree
from midiutil.MidiFile import MIDIFile
import decimal

# File constants
MMP_EXT = "mmp"
MMPZ_EXT = "mmpz"
MID_EXT = "mid"
DATA_LENGTH_OFFSET = 4

# Normalization constants
TME_DIV = 48
VOL_MULT = 2 # normalizes volume to be as loud as it is in LMMS
PAN_DIV = 1.5625
PAN_OFF = 64
PTC_DIV1 = 0.732421875 # normalizes -6000 to 6000 range of automation to -8192 to 8192 range of pitch wheel
PTC_DIV2 = 0.03333333333333333333333333333333 # normalizes -60 to 60 half step range of automation to -2 to 2 half step range of pitch wheel
NOT_OFF = 12 # fixes weird off by one octave issue

# Controller channel constants
PAN_CHNL = 10
VOL_CHNL = 7
BNK_CHNL = 0

# Misc. constants
MAX_VEL = 127
DEF_VOL = 100
DEF_PAN = 0

def parse_command_line():
    success = True

    try:
        opts, args = getopt.gnu_getopt(sys.argv[1:], "h", ["help"])
    except getopt.GetoptError:
        usage()
        success = False

    if success:
        if not opts:
            if not args:
                usage()
        else:
            for opt, arg in opts:
                if opt in ("-h", "--help"):
                    usage()
            
    if success:
        arg_count = len(args)
        can_parse = True
        if arg_count != 1:
            can_parse = False
        
        if can_parse:
            file_full_path_name = args[0]

    return file_full_path_name


def usage():
    print("Description:")
    print(" Converts .mmp/.mmpz LMMS project files to .mid Midi files")
    print("Type arguments as follows:")
    print(" mmp2midi.py projectpath")
    exit(0)


def read_input_file(input_file_path):
    mmp_ext = "." + MMP_EXT
    mmpz_ext = "." + MMPZ_EXT
    is_mmp_file = input_file_path.endswith(mmp_ext) \
        or input_file_path.endswith(mmp_ext.upper())
    if is_mmp_file:
        file_data = read_mmp_file(input_file_path)
    else:
        file_data = read_mmpz_file(input_file_path)
    return is_mmp_file, file_data
    
    
def read_mmp_file(file_path):
    """ Loads an uncompressed LMMS file """
    mmpz_file = open(file_path, mode='rb')
    file_data = mmpz_file.read()
    mmpz_file.close()
    return file_data


def read_mmpz_file(file_path):
    """ Loads a compressed LMMS file (4-byte header + Zip format) """
    mmpz_file = open(file_path, mode='rb')
    mmpz_file.seek(DATA_LENGTH_OFFSET)
    file_data = mmpz_file.read()
    mmpz_file.close()
    uncompressed_data = zlib.decompress(file_data)
    return uncompressed_data
    

def read_xml_tree(file_data):
    is_error = False
    root = None
    try:
        root = etree.fromstring(file_data)
    except Exception as ex:
        is_error = True
        print("Input file decoding error : " + str(ex))
    return root
    
    
def read_header(root):
    head = root.find('.//head').attrib
        
    # MidiFile does not seem to handle time signature.
    # How unfortunate...
    timesig_num = 4
    timesig_den = 4
    if "timesig_numerator" in head:
        timesig_num = int(head["timesig_numerator"])
        timesig_den= int(head["timesig_denominator"])

    bpm = 120.0
    if "bpm" in head:
        bpm = float(head['bpm'])
    else:
        bpm_tag = root.find(".//head//bpm")
        if bpm_tag is not None and 'value' in bpm_tag.attrib:
            bpm = float(bpm_tag.attrib["value"])
            
    print("numerator ", timesig_num, ", denominator", timesig_den, ", bpm", bpm)
    return timesig_num, timesig_den, bpm
         

def collect_tracks(root):
    """ Collects sensible tracks """
    tracks = []
    autotracks = []
    mixers = []

    # tracks
    for t in root.findall('song//track'):
        # print("testing track ", t.attrib)
        if t.find('instrumenttrack') is not None and \
            t.find('pattern/note') is not None:
            tracks.append(t)
        elif t.find('automationpattern') is not None:
            autotracks.append(t)

    # mixers
    for t in root.findall('song//fxchannel'):
        # print("testing track ", t.attrib)
        if t.find('fxchain') is not None:
            mixers.append(t)
    
    return tracks, autotracks, mixers


def build_midi_file(timesig_num, timesig_den, bpm, tracks, autotracks, mixers):
    midif = MIDIFile(len(tracks), True, False, True)

    # 48 ticks per beat, beats are in bpm, so to convert to ticks per second you take ((bpm / 60) * 48)
    # ticks per second can be converted into a seconds amount by taking the inversion (1/tps) which gives you seconds per tick which, is just seconds
    # this seconds amount can then be used to calculate delay effect, by dividing the delay seconds by it and rounding which gives a defined tick delay
    spt = 1 / (bpm / 60 * 48)

    channel = 0
    print("%d tracks" %(len(tracks)))
    thistrack = 0
    for track in tracks:
        if int(track.attrib["muted"]) == 1:
            continue
        track_name = track.attrib["name"]
        tmp_channel = channel

        channelDelay = 0
        volmult = 1
        fxch = int(track.find('instrumenttrack').attrib['fxch'])
        # TODO: figure out mixer sending
        if len(mixers) > fxch:
            if fxch != 0 and 'volume' in mixers[fxch].attrib:
                volmult = float(mixers[fxch].attrib['volume']) # multiply in mixer volume if not master and if exists
            if mixers[fxch].find('fxchain') is not None:
                fxchain = mixers[fxch].find('fxchain')
                if 'numofeffects' in fxchain.attrib and 'enabled' in fxchain.attrib:
                    if int(fxchain.attrib['enabled']) == 1 and int(fxchain.attrib['numofeffects']) > 0:
                        for effect in fxchain.findall('effect'):
                            if effect.find('Delay') is not None:
                                channelDelay += float(effect.find('Delay').attrib['DelayTimeSamples'])

        if 'volume' in mixers[0].attrib:
            volmult *= float(mixers[0].attrib['volume']) # always includes master volume

        volmult *= VOL_MULT # normalization
        channelDelay = int(channelDelay / spt) # normalize delay to ticks

        isdrums = track.find('instrumenttrack/instrument').attrib['name'] == 'sf2player' and int(track.find('instrumenttrack/instrument/sf2player').attrib["bank"]) == 128
        if isdrums:
            channel = 9
        if track.find('instrumenttrack/instrument').attrib['name'] == 'sf2player':
            print("adding track", track_name, "on bank", track.find('instrumenttrack/instrument/sf2player').attrib["bank"], ", patch", track.find('instrumenttrack/instrument/sf2player').attrib["patch"], ", channel", channel)
        else:
            print("adding track", track_name, "on channel", channel)
        midif.addTrackName(thistrack, 0, track_name)
        # midif.addTimeSignature(thistrack, 0, timesig_num, timesig_den, timesig_den, 8)
        midif.addTempo(thistrack, 0, bpm)
        if track.find('instrumenttrack/instrument').attrib['name'] == 'sf2player':
            midif.addControllerEvent(thistrack, channel, 0, BNK_CHNL, int(track.find('instrumenttrack/instrument/sf2player').attrib["bank"]))
            midif.addProgramChange(thistrack, channel, 0, track.find('instrumenttrack/instrument/sf2player').attrib["patch"])
        else:
            midif.addProgramChange(thistrack, channel, 0, 0) # this is where instruments are set

        midif.addControllerEvent(thistrack, channel, 0, VOL_CHNL, normalize_vol(float(track.find('instrumenttrack').get('vol', DEF_VOL)) * volmult))
        midif.addControllerEvent(thistrack, channel, 0, PAN_CHNL, normalize_pan(float(track.find('instrumenttrack').get('pan', DEF_PAN))))
        for p in track.iter('pattern'):
            tstart = float(p.attrib['pos'])/TME_DIV
            for note in p.findall('note'):
                attr = dict([(k, float(v)) for (k,v) in note.attrib.items()])
                key = int(attr['key'] + NOT_OFF)
                dur = attr['len']/TME_DIV
                time = tstart + ((attr['pos'] + channelDelay)/TME_DIV)
                vol = attr['vol']
                if dur <= 0 or vol <= 0 or time < 0: continue
                #print(">> adding note key %d @ %0.2f for %0.2f" %(key, time, dur))
                assert(0 <= key <= MAX_VEL)
                assert(dur > 0)
                vol = min(vol, MAX_VEL)
                midif.addNote(track=thistrack, channel=channel,
                    pitch=key, time=time , duration=dur, volume=vol)
                
        # automation tracks here
        # to convert automation panning to midi panning, divide by PAN_DIV, then add PAN_OFF

        # TODO: use automation track indicator tags with ID matching instead of names for automation
        for autotrack in autotracks:
            if not track_name in autotrack.find('automationpattern').attrib['name']:
                continue
            for p in autotrack.iter('automationpattern'):
                tstart = float(p.attrib['pos'])/TME_DIV
                times = iter(p.findall('time'))
                for time in times:
                    attr = dict([(k, float(v)) for (k,v) in time.attrib.items()])
                    time = tstart + attr['pos']/TME_DIV
                    value = attr['value']
                    # TODO: fix pitch automation
                    if 'Panning' in p.attrib['name']:
                        midif.addControllerEvent(thistrack, channel, time, PAN_CHNL, normalize_pan(value))
                    elif 'Pitch' in p.attrib['name']:
                        # i hate you.
                        # why cant you just iterate normally
                        # if int(p.attrib['prog']) == 1 or int(p.attrib['prog']) == 2:
                        #     try:
                        #         print("Interpolating automation at ", time, " with value ", value)
                        #         interpolate_automation(thistrack, channel, time, value, tstart + float(next(times).attrib['pos'])/TME_DIV, float(next(times).attrib['value']), 'Pitch', midif)
                        #     except Exception as e:
                        #         print(f"Error interpolating {p.attrib['name']}: {e}")
                        #         midif.addPitchWheelEvent(thistrack, channel, time, normalize_pitch(value))
                        # else:
                            midif.addPitchWheelEvent(thistrack, channel, time, normalize_pitch(value))
                    elif 'Volume' in p.attrib['name']:
                        midif.addControllerEvent(thistrack, channel, time, VOL_CHNL, normalize_vol(value))
                    

        thistrack += 1
        
        if isdrums:
            channel = tmp_channel

        # increments channel - avoids drumkit channel (channel #9)
        channel += 1
        if channel == 9:
            channel = 10
        if channel == 16:
            channel = 0

    # BPM changes and shiz
    for autotrack in autotracks:
        if not "Tempo" in autotrack.find('automationpattern').attrib['name']:
            continue
        for p in autotrack.iter('automationpattern'):
            tstart = float(p.attrib['pos'])/TME_DIV
            for time in p.findall('time'):
                attr = dict([(k, float(v)) for (k,v) in time.attrib.items()])
                time = tstart + attr['pos']/TME_DIV
                value = attr['value']
                midif.addTempo(thistrack, time, float(value))
            
    return midif

def interpolate_automation(thistrack, channel, initialtime, initialvalue, nexttime, nextvalue, type, midif):
    # print("247: ", type)
    if 'Panning' in type:
        iterrange = range(start=int(initialtime), stop=int(nexttime-1))
        increment = (nextvalue - initialvalue) / len(iterrange)
        for i in iterrange:
            midif.addControllerEvent(thistrack, channel, initialtime, PAN_CHNL, normalize_pan(initialvalue))
            initialvalue += increment
    elif 'Pitch' in type:
        # print("a: ", initialtime, nexttime-1)
        l = 0
        for a in drange(initialtime, nexttime-1, '0.01'):
            l += 1
        if l == 0:
            l = 1
        increment = (nextvalue - initialvalue) / l
        for i in drange(initialtime, nexttime-1, '0.01'):
            # print("b: ", i)
            midif.addPitchWheelEvent(thistrack, channel, i, normalize_pitch(initialvalue))
            initialvalue += increment
    elif 'Volume' in type:
        iterrange = range(start=int(initialtime), stop=int(nexttime-1))
        increment = (nextvalue - initialvalue) / len(iterrange)
        for i in iterrange:
            midif.addControllerEvent(thistrack, channel, initialtime, VOL_CHNL, normalize_vol(initialvalue))
            initialvalue += increment

def normalize_pitch(value):
    # print("c: ", value)
    # print("d: ", int((value / PTC_DIV1) / PTC_DIV2))
    return max(-8192, min(8192, int((value / PTC_DIV1) / PTC_DIV2)))

def normalize_pan(value):
    return max(min(int((value / PAN_DIV) + PAN_OFF), 127), 0)

def normalize_vol(value):
    return max(min(int(value / PAN_DIV), 127), 0)

def drange(x, y, jump):
  while x < y:
    yield float(x)
    x += float(decimal.Decimal(jump))

def save_midi_file(midif, input_file_path, is_mmp_file):
    mmp_ext = "." + MMP_EXT
    mmpz_ext = "." + MMPZ_EXT
    midi_ext = "." + MID_EXT
    if is_mmp_file:
        foutname = input_file_path.replace(mmp_ext, '') + midi_ext
    else:
        foutname = input_file_path.replace(mmpz_ext, '') + midi_ext
    with open(foutname, 'wb') as f: 
        midif.writeFile(f)
    print("MIDI file written to %s"%foutname)


if __name__ == '__main__':
    input_file_path = parse_command_line()
    is_mmp_file, file_data = read_input_file(input_file_path)
    root = read_xml_tree(file_data)
    if root is not None:
        timesig_num, timesig_den, bpm = read_header(root)
        tracks, autotracks, mixers = collect_tracks(root)
        midif = build_midi_file(timesig_num, timesig_den, bpm, tracks, autotracks, mixers)
        save_midi_file(midif, input_file_path, is_mmp_file)
