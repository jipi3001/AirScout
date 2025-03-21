import time
import smbus
import sys
import pynmea2

BUS = None
address = 0x42

def connectBus():
    global BUS
    BUS = smbus.SMBus(1)

def parseResponse(gpsLine):
    gpsChars = ''.join(chr(c) for c in gpsLine)
    if gpsChars.startswith('$'):
        try:
            msg = pynmea2.parse(gpsChars)
            if isinstance(msg, pynmea2.types.talker.GGA) and msg.is_valid:
                return {
                    "latitude": msg.latitude,
                    "longitude": msg.longitude,
                    "num_sats": msg.num_sats
                }
        except pynmea2.ParseError:
            return None
    return None

def readGPS():
    """ Reads a single GPS response and returns the parsed data """
    c = None
    response = []
    try:
        while True:
            c = BUS.read_byte(address)
            if c == 255:
                return None
            elif c == 10:  # End of GPS sentence
                break
            else:
                response.append(c)
        return parseResponse(bytearray(response))
    except IOError:
        connectBus()
    except Exception:
        return None
    return None

# Main Execution

connectBus()  # Initialize GPS module

    

