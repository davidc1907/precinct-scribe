import argparse
import glob
import os
import site
import sys
import tomllib
from pathlib import Path

import ctranslate2

# The CUDA libraries from pip have to be found before faster_whisper is imported.
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

TERMS_FOLDER = Path(__file__).parent / "terms"
TRANSCRIPTS_FOLDER = "transcripts"
DOWNLOADS_FOLDER = "downloads"
DEFAULT_LANGUAGE = "de"


# ---------- term lists ----------

def load_terms(language):
    path = TERMS_FOLDER / f"{language}.toml"
    if not path.exists():
        return None
    with open(path, "rb") as f:
        return tomllib.load(f)


def available_topics(language):
    data = load_terms(language)
    if data is None:
        return []
    return list(data.get("topics", {}))


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
                raise ValueError(f"Unknown topic '{topic}'. Available: {available}")
            parts.append(data["topics"][topic])

    if names:
        parts.append(names + ".")

    prompt = " ".join(parts)
    if len(prompt.split()) > 150:
        print("Warning: prompt is very long, Whisper will cut off the beginning.")
    return prompt


# ---------- model and files ----------

def load_model(cpu=False, model_name=None):
    if cpu or ctranslate2.get_cuda_device_count() == 0:
        device = "cpu"
        compute_type = "int8"
        model_size = "small"
    else:
        device = "cuda"
        compute_type = "float16"
        model_size = "large-v3"

    if model_name:
        model_size = model_name

    print(f"Loading model {model_size} on {device}...")
    model = WhisperModel(model_size, device=device, compute_type=compute_type)
    print("Model loaded.")
    return model


def transcript_path(name):
    os.makedirs(TRANSCRIPTS_FOLDER, exist_ok=True)
    return os.path.join(TRANSCRIPTS_FOLDER, f"{name}.txt")


def get_link_info(url):
    with YoutubeDL({"format": "bestaudio/best", "quiet": True}) as ydl:
        return ydl.extract_info(url, download=False)


def download_audio(url, on_progress=None):
    """on_progress is called with the yt-dlp progress dict, e.g. by the GUI."""
    os.makedirs(DOWNLOADS_FOLDER, exist_ok=True)

    options = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(DOWNLOADS_FOLDER, "%(title)s.%(ext)s"),
        "quiet": True,
    }

    if on_progress is not None:
        options["progress_hooks"] = [on_progress]
        options["noprogress"] = True

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        print(f"Downloaded: {info['title']}")
        return ydl.prepare_filename(info)


# ---------- transcription ----------

def transcribe_file(model, source, path, language, prompt, start=None, end=None,
                    quiet=False, on_line=None, stop=None):
    """Transcribes a local file. start and end are in seconds or None."""
    clip = "0"
    if start is not None or end is not None:
        if start is None:
            start = 0

        if end is not None:
            clip = [start, end]
        else:
            clip = [start]

    print("Transcribing...")
    segments, info = model.transcribe(
        source,
        beam_size=5,
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
        condition_on_previous_text=False,
        clip_timestamps=clip,
    )

    print("Waiting for first results...")

    with open(path, "w", encoding="utf-8") as f:
        for segment in segments:
            if stop is not None and stop.is_set():
                print("\nStopped.")
                break

            start_time = convert_seconds(segment.start)
            end_time = convert_seconds(segment.end)
            line = f"[{start_time} -> {end_time}] {segment.text.strip()}"
            f.write(line + "\n")
            f.flush()

            if on_line is not None:
                on_line(line)

            if quiet:
                percent = segment.end / info.duration * 100
                status = f"{end_time} / {convert_seconds(info.duration)} ({percent:.0f} %)"
                print(f"\r{status:<40}", end="", flush=True)
            else:
                print(line)

    if quiet:
        print()
    print(f"Saved to {path}")


def transcribe_link(model, url, path, language, prompt, start=None, end=None,
                    quiet=False, on_line=None, stop=None):
    """Transcribes a link. Live streams are detected automatically."""
    info = get_link_info(url)

    if info.get("is_live"):
        transcribe_livestream(model, info, language, prompt, path, quiet=quiet, on_line=on_line, stop=stop)
        return

    source = download_audio(url)
    transcribe_file(model, source, path, language, prompt, start, end, quiet, on_line, stop)


# ---------- command line ----------

def build_parser():
    parser = argparse.ArgumentParser(
        prog="scribe",
        description="Transcribes political speeches from files, links, live streams and the system audio.",
        epilog="For questions please contact contact@precinct-room.com",
    )

    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("-f", "--file", help="Transcribe a local video or audio file")
    source_group.add_argument("-l", "--link", help="Transcribe a link, live streams are detected automatically")
    source_group.add_argument("-a", "--audio", action="store_true", help="Record and transcribe the system audio (Windows)")
    source_group.add_argument("--list-devices", action="store_true", help="List audio devices and exit")

    parser.add_argument("-o", "--output", help="Name of the transcript, saved as transcripts/NAME.txt")
    parser.add_argument("-s", "--language", help="Language of the audio, e.g. de or en (default: de)")
    parser.add_argument("-t", "--topics", help="Comma separated topics from the term list, e.g. bundestag")
    parser.add_argument("-n", "--names", help='Names and terms in the recording, e.g. "Friedrich Merz, Lars Klingbeil"')
    parser.add_argument("--start", help="Start point, e.g. 1:42:00 (files and links only)")
    parser.add_argument("--end", help="End point, e.g. 1:50:00 (files and links only)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Show the progress instead of the text")
    parser.add_argument("--device", type=int, help="Device number for -a, see --list-devices")
    parser.add_argument("--cpu", action="store_true", help="Run on the CPU instead of the GPU")
    parser.add_argument("-m", "--model", help="Whisper model, e.g. small, medium, turbo, large-v3")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.list_devices:
        list_devices()
        return

    if args.file and not os.path.isfile(args.file):
        parser.error(f"File not found: {args.file}")

    if args.language:
        language = args.language
    else:
        language = DEFAULT_LANGUAGE

    try:
        prompt = build_prompt(language, args.topics, args.names)
    except ValueError as error:
        parser.error(str(error))

    start = None
    if args.start:
        start = parse_time(args.start)

    end = None
    if args.end:
        end = parse_time(args.end)

    if args.output:
        name = args.output
    else:
        name = "transcript"
    path = transcript_path(name)

    model = load_model(args.cpu, args.model)

    try:
        if args.audio:
            transcribe_system_audio(model, args.device, language, prompt, path, quiet=args.quiet)
        elif args.link:
            transcribe_link(model, args.link, path, language, prompt, start, end, quiet=args.quiet)
        else:
            transcribe_file(model, args.file, path, language, prompt, start, end, quiet=args.quiet)

    except RuntimeError as error:
        print(error)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
