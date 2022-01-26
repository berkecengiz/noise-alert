from array import array
from struct import pack
from sys import byteorder
import copy
import pyaudio
import wave
import smtplib
import ssl
import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

THRESHOLD = 500  # audio levels not normalised. needs adjustmens
CHUNK_SIZE = 1024
SILENT_CHUNKS = 5 * 44100 / 1024  # about 5sec
FORMAT = pyaudio.paInt16
FRAME_MAX_VALUE = 2 ** 15 - 1
NORMALIZE_MINUS_ONE_dB = 10 ** (-1.0 / 20)
RATE = 44100
CHANNELS = 1
TRIM_APPEND = RATE / 4


def is_silent(data_chunk):
    """Returns 'True' if below the 'silent' threshold"""
    return max(data_chunk) < THRESHOLD


def normalize(data_all):
    """Amplify the volume out to max -1dB"""
    # MAXIMUM = 16384
    normalize_factor = (float(NORMALIZE_MINUS_ONE_dB * FRAME_MAX_VALUE)
                        / max(abs(i) for i in data_all))

    r = array('h')
    for i in data_all:
        r.append(int(i * normalize_factor))
    return r


def trim(data_all):
    _from = 0
    _to = len(data_all) - 1
    for i, b in enumerate(data_all):
        if abs(b) > THRESHOLD:
            _from = max(0, i - TRIM_APPEND)
            break

    for i, b in enumerate(reversed(data_all)):
        if abs(b) > THRESHOLD:
            _to = min(len(data_all) - 1, len(data_all) - 1 - i + TRIM_APPEND)
            break

    return copy.deepcopy(data_all[int(_from):(int(_to) + 1)])


def record():
    """Record a word or words from the microphone and
    return the data as an array of signed shorts."""

    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE,
                    input=True, output=True, frames_per_buffer=CHUNK_SIZE)

    silent_chunks = 0
    audio_started = False
    data_all = array('h')

    while True:
        # little endian, signed short
        data_chunk = array('h', stream.read(CHUNK_SIZE))
        if byteorder == 'big':
            data_chunk.byteswap()
        data_all.extend(data_chunk)

        silent = is_silent(data_chunk)

        if audio_started:
            if silent:
                silent_chunks += 1
                if silent_chunks > SILENT_CHUNKS:
                    break
            else:
                silent_chunks = 0
        elif not silent:
            audio_started = True

    sample_width = p.get_sample_size(FORMAT)
    stream.stop_stream()
    stream.close()
    p.terminate()

    # we trim before normalize as threshhold applies to un-normalized wave (as well as is_silent() function)
    data_all = trim(data_all)
    data_all = normalize(data_all)
    return sample_width, data_all


def record_to_file(path):
    "Records from the microphone and outputs the resulting data to 'path'"
    sample_width, data = record()
    data = pack('<' + ('h' * len(data)), *data)

    wave_file = wave.open(path, 'wb')
    wave_file.setnchannels(CHANNELS)
    wave_file.setsampwidth(sample_width)
    wave_file.setframerate(RATE)
    wave_file.writeframes(data)
    wave_file.close()


def send_mail(path):

    file = open('mails.txt', 'r')
    data = file.readlines()
    for mail in data:
        fromaddr = 'bottest757@gmail.com'  # Change your mail here
        password = 'qwerty123#'  # Your mails password
        toaddr = mail.strip()
        msg = MIMEMultipart()
        msg['From'] = fromaddr

        msg['To'] = toaddr
        msg['Subject'] = "Noise Detected: " + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")

        body = " Somebody is in your home making some noise!" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + \
            "Do you want to call 911? You can find the audio evidience in the attachments."


        msg.attach(MIMEText(body, 'plain')) 
        filename = path
        attachment = open(path, "rb")
        p = MIMEBase('application', 'octet-stream')
        p.set_payload((attachment).read())

        encoders.encode_base64(p)

        p.add_header('Content-Disposition',
             "attachment; filename= %s" % filename)

        msg.attach(p)
        port = 587
        smtpserver = smtplib.SMTP("smtp.gmail.com", port)
        smtpserver.ehlo()
        smtpserver.starttls()
        smtpserver.ehlo()
        smtpserver.login(fromaddr, password)
        smtpserver.sendmail(fromaddr, toaddr, msg.as_string())
        print(f'Sent to {toaddr} succesfully!')


if __name__ == '__main__':
    print("Program starting in silence and it will start recording when somebody make a noise in your room!")
    record_to_file('alert.wav')
    print("Alert - noise written to alert.wav")
    send_mail('alert.wav')
