import argparse
import os, sys, glob
import tomllib
from pathlib import Path

if sys.platform == "win32":
    for dll_dir in glob.glob(os.path.join(sys.prefix, "Lib", "site-packages", "nvidia", "*", "bin")):
        os.add_dll_directory(dll_dir)
        os.environ["PATH"] = dll_dir + os.pathsep + os.environ["PATH"]

from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL
from livestream import convert_seconds

folder = "transcripts"
os.makedirs(f"{folder}", exist_ok=True)

parser = argparse.ArgumentParser(
    prog="Politics_Transcript",
    description="Transcribes videos, livestreams or video files",
    epilog="For questions please contact contact@precinct-room.com"
)


parser.add_argument('-o', '--output')

parser.add_argument('-s', '--language')
parser.add_argument('-t', '--topics')
parser.add_argument('-n', '--names')

source_group = parser.add_mutually_exclusive_group(required=True)
source_group.add_argument('-f', '--file')
source_group.add_argument('-l', '--link')

args = parser.parse_args()

if args.file and not os.path.isfile(args.file):
    parser.error(f"File not found: {args.file}")

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

prompt = build_prompt(language, args.topics, args.names)

def download_audio(url):
    download_folder = "downloads"
    os.makedirs(download_folder, exist_ok=True)

    options = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(download_folder, "%(title)s.%(ext)s"),
        "quiet": True,
    }

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        print(f"Downloaded: {info['title']}")
        return ydl.prepare_filename(info)

# The transcribing model

def transcribe():
    model_size = "large-v3"

    print("Loading model...")
    model = WhisperModel(model_size, device="cuda", compute_type="float16")

    source = args.file or download_audio(args.link)

    print("Model loaded. Transcribing....")

    segments, info = model.transcribe(
        source,
        beam_size=5,
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
        condition_on_previous_text=False
    )

    print("Waiting for first results...")

    name = args.output or "transcript"
    path = os.path.join(folder, f"{name}.txt")

    with open(path, "w", encoding="utf-8") as f:
        for segment in segments:
            start_time = convert_seconds(segment.start)
            end_time = convert_seconds(segment.end)
            line = f"[{start_time} -> {end_time}] {segment.text}"
            print(line)
            f.write(line + "\n")


transcribe()