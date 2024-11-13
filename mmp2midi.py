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
import math
import collections

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
PAN_CHNL = 10 # channel defined as "Coarse Panning", i.e. the panning left right or center
VOL_CHNL = 7 # channel defnied as "Coarse Volume", i.e. the overall volume
BNK_CHNL = 0 # channel defined as "Coarse Bank", i.e. the current soundfont bank
EXPR_CHNL = 11 # channel defined as "Coarse Expression", i.e. volume percentage of master

# Misc. constants
MAX_VEL = 127
MIN_VEL = 0
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
    
    # Default values for LMMS project
    timesig_num = 4
    timesig_den = 4
    if "timesig_numerator" in head:
        timesig_num = int(head["timesig_numerator"])
        timesig_den= int(head["timesig_denominator"])

    # Default values for LMMS project
    bpm = 140.0
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

        issf2 = track.find('instrumenttrack/instrument').attrib['name'] == 'sf2player'
        hasbank = issf2 and 'bank' in track.find('instrumenttrack/instrument/sf2player').attrib
        haspatch = issf2 and 'patch' in track.find('instrumenttrack/instrument/sf2player').attrib

        isdrums = issf2 and hasbank and int(track.find('instrumenttrack/instrument/sf2player').attrib["bank"]) == 128
        if isdrums:
            channel = 9
        if issf2:
            if hasbank:
                print("adding track", track_name, "on bank", track.find('instrumenttrack/instrument/sf2player').attrib["bank"], ", patch", track.find('instrumenttrack/instrument/sf2player').attrib["patch"], ", channel", channel)
            elif haspatch:
                print("adding track", track_name, "on bank 0, patch", track.find('instrumenttrack/instrument/sf2player').attrib["patch"], ", channel", channel)
            else:
                print("adding track", track_name, "on bank 0, patch 0, channel", channel)
        else:
            print("adding track", track_name, "on channel", channel)
        
        midif.addTrackName(thistrack, 0, track_name)
        midif.addTimeSignature(thistrack, 0, timesig_num, int(math.log(timesig_den, 2)), max(min(int(96 / timesig_den), 255), 0), 8) # cpt will desync for any note more precice than 32nd notes
        midif.addTempo(thistrack, 0, bpm)

        if issf2:
            if hasbank:
                midif.addControllerEvent(thistrack, channel, 0, BNK_CHNL, int(track.find('instrumenttrack/instrument/sf2player').attrib["bank"]))
            if haspatch:
                midif.addProgramChange(thistrack, channel, 0, int(track.find('instrumenttrack/instrument/sf2player').attrib["patch"]))
            else:
                midif.addProgramChange(thistrack, channel, 0, 0)
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
                vol = int(attr['vol'])
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
        # TODO: use expression commmands for volume control over master volume control, though this could potentially be adverse as it would not allow increasing volume over the master.
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
                    # TODO: add patch/bank automation
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
    timesigchangesnum = {}
    timesigchangesden = {}
    for autotrack in autotracks:
        for p in autotrack.iter('automationpattern'):
            tstart = float(p.attrib['pos'])/TME_DIV
            times = iter(p.findall('time'))
            for time in times:
                attr = dict([(k, float(v)) for (k,v) in time.attrib.items()])
                time = tstart + attr['pos']/TME_DIV
                value = attr['value']
                if "Tempo" in autotrack.find('automationpattern').attrib['name']:
                    midif.addTempo(thistrack, time, float(value))
                elif "Numerator" in autotrack.find('automationpattern').attrib['name']:
                    if time != 0:
                        timesigchangesnum[time] = int(value)
                elif "Denominator" in autotrack.find('automationpattern').attrib['name']:
                    if time != 0:
                        timesigchangesden[time] = int(value)
    
    # print(timesigchangesnum)
    # print(timesigchangesden)

    # numerators take priority, however the issue will arise that if there are more denominator changes than numerator, they will be omitted, however this is uncommon so this solution is acceptable for now
    for time in timesigchangesnum:
        timesig_num = timesigchangesnum[time]
        if time in timesigchangesden:
            timesig_den = timesigchangesden[time]
        midif.addTimeSignature(thistrack, time, timesig_num, int(math.log(timesig_den, 2)), max(min(int(96 / timesig_den), 255), 0), 8)

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
    return max(min(int((value / PAN_DIV) + PAN_OFF), MAX_VEL), MIN_VEL)

def normalize_vol(value):
    return max(min(int(value / PAN_DIV), MAX_VEL), MIN_VEL)

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


# TODO: add support for going through and converting every project file in a folder to midi, instead of manually doing each
if __name__ == '__main__':
    input_file_path = parse_command_line()
    is_mmp_file, file_data = read_input_file(input_file_path)
    root = read_xml_tree(file_data)
    if root is not None:
        timesig_num, timesig_den, bpm = read_header(root)
        tracks, autotracks, mixers = collect_tracks(root)
        midif = build_midi_file(timesig_num, timesig_den, bpm, tracks, autotracks, mixers)
        save_midi_file(midif, input_file_path, is_mmp_file)
