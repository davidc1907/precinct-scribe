# Function converting the seconds from whisper into hours minutes and seconds

def convert_seconds(seconds):
    seconds = int(seconds)
    hour = seconds // 3600
    seconds = seconds % 3600
    minutes = seconds // 60
    seconds = seconds % 60
    timestamp = (f"{hour}:{minutes:02d}:{seconds:02d}")
    return timestamp