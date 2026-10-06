import argparse
import os, sys, glob
import tomllib

import Path

for dll_dir in glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "*", "bin")):
    os.add_dll_directory(dll_dir)
    os.environ["PATH"] = dll_dir + os.pathsep + os.environ["PATH"]

from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL
import pyaudiowpatch as pyaudio

folder = "transcripts"
os.makedirs(f"{folder}", exist_ok=True)

parser = argparse.ArgumentParser(
    prog="Politics_Transcript",
    description="Transcribes videos, livestreams or video files",
    epilog="For questions please contact contact@precinct-room.com"
)

parser.add_argument('-f', '--file')
parser.add_argument('-o', '--output')
parser.add_argument('-l', '--link')
parser.add_argument('-l', '--language')
parser.add_argument('-p', '--prompt')



args = parser.parse_args()

# Function converting the seconds from whisper into hours minutes and seconds

def convert_seconds(seconds):
    seconds = int(seconds)
    hour = seconds // 3600
    seconds = seconds % 3600
    minutes = seconds // 60
    seconds = seconds % 60
    timestamp = (f"{hour}:{minutes:02d}:{seconds:02d}")
    return timestamp

if args.language:
    language = args.language

else:
    language = 'de'


# Functions for using the terms

TERMS_FOLDER = Path(__file__).parent / "terms"


def load_terms(language):
    path = TERMS_FOLDER / f"{language}.toml"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return tomllib.load(f)


def build_prompt(language, topics, names):
    data = load_terms(language)
    if data is None:
        print(f"No term list found for '{language}', using names only.")
        return names or None

    parts = [data["base"]]

    if topics:
        for topic in topics.split(","):
            topic = topic.strip()
            if topic not in data["topics"]:
                available = ", ".join(data["topics"])
                parser.error(f"Unknown topic '{topic}'. Available: {available}")
            parts.append(data["topics"][topic])

    if names:
        parts.append(names + ".")

    prompt = " ".join(parts)
    if len(prompt.split()) > 150:
        print("Warning: prompt is very long, Whisper will cut off the beginning.")
    return prompt



# The transcribing model

def transcribe():
    model_size = "large-v3"

    print("Loading model...")
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    print("Model loaded. Transcribing....")
    segments, info = model.transcribe(args.file, beam_size=5, language=language)

    print("Waiting for first results...")

    name = args.output or "transcript"
    path = os.path.join(folder, f"{args.output}.txt")

    with open(path, "w", encoding="utf-8") as f:
        for segment in segments:
            start_time = convert_seconds(segment.start)
            end_time = convert_seconds(segment.end)
            line = f"[{start_time} -> {end_time}] {segment.text}"
            print(line)
            f.write(line + "\n")


transcribe()