import argparse
import os, sys, glob
import tomllib
from pathlib import Path
import ctranslate2

import site

if sys.platform == "win32":
    search_paths = site.getsitepackages() + [site.getusersitepackages()]
    for sp in search_paths:
        for dll_dir in glob.glob(os.path.join(sp, "nvidia", "*", "bin")):
            os.add_dll_directory(dll_dir)
            os.environ["PATH"] = dll_dir + os.pathsep + os.environ["PATH"]

from faster_whisper import WhisperModel
from yt_dlp import YoutubeDL
from livestream import list_devices, transcribe_system_audio, transcribe_livestream
from utils import convert_seconds, parse_time

folder = "transcripts"
os.makedirs(f"{folder}", exist_ok=True)

parser = argparse.ArgumentParser(
    prog="Politics_Transcript",
    description="Transcribes videos, livestreams or video files",
    epilog="For questions please contact contact@precinct-room.com"
)


parser.add_argument('-o', '--output')

parser.add_argument('--cpu', action='store_true', help='Run on the CPU instead of the GPU')
parser.add_argument('-m', '--model', help='Whisper model, e.g. small, medium, turbo, large-v3')
parser.add_argument('-s', '--language')
parser.add_argument('-t', '--topics')
parser.add_argument('-n', '--names')
parser.add_argument('--start', help='Set start point e.g. 1:42:00')
parser.add_argument('--end', help='Set end point e.g. 1:50:00')
parser.add_argument('-q', '--quiet', action='store_true', help='Do not print the transcribed text into the console')

source_group = parser.add_mutually_exclusive_group(required=True)
source_group.add_argument('-f', '--file')
source_group.add_argument('-l', '--link')
source_group.add_argument('-a', '--audio', action='store_true', help='Record System Audio')
source_group.add_argument('--list-devices', action='store_true', help='List audio devices and exit')

parser.add_argument('--device', type=int, help='Device Number from --list-devices')

args = parser.parse_args()


if args.list_devices:
    list_devices()
    raise SystemExit

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

def get_link_info(url):
    with YoutubeDL({"format": "bestaudio/best", "quiet": True}) as ydl:
        return ydl.extract_info(url, download=False)

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
    if args.cpu or ctranslate2.get_cuda_device_count() == 0:
        device = "cpu"
        compute_type = "int8"
        model_size = "small"
    else:
        device = "cuda"
        compute_type = "float16"
        model_size = "large-v3"

    if args.model:
        model_size = args.model

    print(f"Loading model {model_size} on {device}...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)

    name = args.output or "transcript"
    path = os.path.join(folder, f"{name}.txt")

    if args.audio:
        transcribe_system_audio(model, args.device, language, prompt, path, quiet=args.quiet)
        return

    if args.link:
        info = get_link_info(args.link)
        if info.get("is_live"):
            transcribe_livestream(model, info, language, prompt, path, quiet=args.quiet)
            return

    source = args.file or download_audio(args.link)

    print("Model loaded. Transcribing....")

    clip = "0"
    if args.start or args.end:
        if args.start:
            start = parse_time(args.start)
        else:
            start = 0

        if args.end:
            clip = [start, parse_time(args.end)]
        else:
            clip = [start]

    segments, info = model.transcribe(
        source,
        beam_size=5,
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
        condition_on_previous_text=False,
        clip_timestamps=clip
    )

    print("Waiting for first results...")

    with open(path, "w", encoding="utf-8") as f:
        for segment in segments:
            start_time = convert_seconds(segment.start)
            end_time = convert_seconds(segment.end)
            line = f"[{start_time} -> {end_time}] {segment.text}"
            f.write(line + "\n")
            f.flush()
            if args.quiet:
                percent = segment.end / info.duration * 100
                status = f"{end_time} / {convert_seconds(info.duration)} ({percent:.0f} %)"
                print(f"\r{status:<40}", end="", flush=True)
            else:
                print(line)

    if args.quiet:
        print()
    print(f"Saved to {path}")


transcribe()
