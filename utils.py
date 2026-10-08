WHISPER_RATE = 16000

#Function converting the seconds from whisper into a timestamp

def convert_seconds(seconds):
    seconds = int(seconds)
    hour = seconds // 3600
    seconds = seconds % 3600
    minutes = seconds // 60
    seconds = seconds % 60
    timestamp = (f"{hour}:{minutes:02d}:{seconds:02d}")
    return timestamp

#Function parsing the timestamp from the '--start' and '--end' parameters into seconds
def parse_time(text):
    seconds = 0
    for part in text.split(":"):
        seconds = seconds * 60 + float(part)
    return seconds
