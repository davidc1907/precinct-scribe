import numpy as np
from utils import convert_seconds

WHISPER_RATE = 16000
HALLUCINATIONS = [
    "Untertitelung des ZDF",
    "Untertitel im Auftrag des ZDF",
    "Untertitel der Amara.org-Community",
]

def to_whisper_format(raw_bytes, channels, rate):
    audio = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32768.0

    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)

    if rate != WHISPER_RATE:
        new_length = int(len(audio) * WHISPER_RATE / rate)
        audio = np.interp(
            np.linspace(0, len(audio), new_length, endpoint=False),
            np.arange(len(audio)),
            audio,
        )

    return audio.astype(np.float32)

def write_segments(segments, f, offset=0.0, quiet=False):
    for segment in segments:
        skip = False
        for phrase in HALLUCINATIONS:
            if phrase in segment.text:
                skip = True
        if skip:
            continue
        start_time = convert_seconds(offset + segment.start)
        end_time = convert_seconds(offset + segment.end)
        line=f"[{start_time} -> {end_time}] {segment.text}"
        if not quiet:
            print(line)
        f.write(line + "\n")
        f.flush()

def transcribe_array(model, audio, language, prompt, f, offset, quiet=False):
    try:
        segments, _ = model.transcribe(
            audio,
            language=language,
            initial_prompt=prompt,
            vad_filter=True,
            condition_on_previous_text=False,
            word_timestamps=True,
            hallucination_silence_threshold=2.0
        )
        segments = list(segments)

    except IndexError:
        segments, _ = model.transcribe(
            audio,
            language=language,
            initial_prompt=prompt,
            vad_filter=True,
            condition_on_previous_text=False
        )
        segments = list(segments)

    write_segments(segments, f, offset, quiet)


def transcribe_bytes(model, raw_bytes, channels, rate, language, prompt, f, offset, quiet=False):
    audio = to_whisper_format(raw_bytes, channels, rate)
    transcribe_array(model, audio, language, prompt, f, offset, quiet)


def list_devices():
    import pyaudiowpatch as pyaudio

    with pyaudio.PyAudio() as p:
        default = p.get_default_wasapi_loopback()
        for device in p.get_loopback_device_info_generator():
            if (device["index"] == default["index"]):
                marker = " (default)"

            else:
                marker = ""

            print(f"Device {device['index']}: {device['name']}{marker}")


def get_loopback_device(p, device_index):
    if device_index is not None:
        try:
            return p.get_device_info_by_index(device_index)

        except IOError:
            print(f"Device {device_index} not found. Try searching for the device by using --list-devices")
            raise SystemExit(1)

    try:
        return p.get_default_wasapi_loopback()

    except OSError:
        print("WASAPI is not available on this system")
        raise SystemExit(1)

    except LookupError:
        print("No default loopback device found. Try searching for the device by using --list-devices")
        raise SystemExit(1)


def transcribe_system_audio(model, device_index, language, prompt, path, batch_seconds=30, quiet=False):
    import queue
    import pyaudiowpatch as pyaudio

    audio_queue = queue.Queue()

    def callback(in_data, frame_count, time_info, status):
        audio_queue.put(in_data)
        return(in_data, pyaudio.paContinue)

    with pyaudio.PyAudio() as p:
        device = get_loopback_device(p, device_index)
        channels = device["maxInputChannels"]
        rate = int(device["defaultSampleRate"])

        bytes_per_second = rate * channels * 2
        batch_bytes = bytes_per_second * batch_seconds

        print(f"Recording from: {device['name']}")
        print("Press Ctrl + C to stop")

        with open(path, "w", encoding="utf-8") as f, \
            p.open(format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                frames_per_buffer=1024,
                input=True,
                input_device_index=device['index'],
                stream_callback=callback) as stream:

            pending_audio = bytearray()
            offset = 0.0
            batch_number = 0

            try:
                while True:
                    try:
                        pending_audio += audio_queue.get(timeout=0.5)

                    except queue.Empty:
                        continue

                    if len(pending_audio) >= batch_bytes:
                        transcribe_bytes(model, bytes(pending_audio), channels, rate, language, prompt, f, offset, quiet)
                        offset += len(pending_audio) / bytes_per_second
                        batch_number += 1
                        if quiet:
                            status = f"Chunk {batch_number} done {convert_seconds(offset)}"
                            print(f"\r{status:<40}", end="", flush=True)

                        pending_audio = bytearray()

            except KeyboardInterrupt:
                print()
                print("\n Stopping. Transcribing the rest...")
                stream.stop_stream()
                while not audio_queue.empty():
                    pending_audio += audio_queue.get()

                if pending_audio:
                    transcribe_bytes(model, bytes(pending_audio), channels, rate, language, prompt, f, offset, quiet)

    print(f"Saved to {path}")

def transcribe_livestream(model, info, language, prompt, path, chunk_seconds=30, quiet=False):
    import av
    chunk_number = 0

    stream_url = info["url"]

    headers = info.get("http_headers") or {}
    header_text = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    if header_text:
        options = {"headers": header_text}
    else:
        options = {}

    print(f"Live stream: {info.get('title', '')}")
    print("Press Ctrl + c to stop")

    container = av.open(stream_url, options=options)
    resampler = av.AudioResampler(format="flt", layout="mono", rate=WHISPER_RATE)

    pending_frames = []
    pending_samples = 0
    offset = 0.0
    batch_samples = WHISPER_RATE * chunk_seconds

    with open(path, "w", encoding="utf-8") as f:
        try:
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    samples = out.to_ndarray().reshape(-1)
                    pending_frames.append(samples)
                    pending_samples += len(samples)

                if pending_samples >= batch_samples:
                    audio = np.concatenate(pending_frames).astype(np.float32)
                    transcribe_array(model, audio, language, prompt, f, offset, quiet)
                    offset += pending_samples / WHISPER_RATE
                    chunk_number += 1
                    if quiet:
                        status = f"Batch {chunk_number} done ({convert_seconds(offset)})"
                        print(f"\r{status:<40}", end="", flush=True)
                    pending_frames = []
                    pending_samples = 0

        except KeyboardInterrupt:
            print()
            print("\n Stopping. Transcribing the rest...")

        finally:
            container.close()

        if pending_frames:
            audio = np.concatenate(pending_frames).astype(np.float32)
            transcribe_array(model, audio, language, prompt, f, offset, quiet)

        print(f"Saved to {path}")
