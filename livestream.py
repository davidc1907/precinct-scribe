import numpy as np
from streaming import StreamingTranscriber
from utils import WHISPER_RATE


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


def transcribe_system_audio(model, device_index, language, prompt, path, quiet=False):
    import queue
    import pyaudiowpatch as pyaudio

    audio_queue = queue.Queue()

    def callback(in_data, frame_count, time_info, status):
        audio_queue.put(in_data)
        return (in_data, pyaudio.paContinue)

    with pyaudio.PyAudio() as p:
        device = get_loopback_device(p, device_index)
        channels = device["maxInputChannels"]
        rate = int(device["defaultSampleRate"])

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

            transcriber = StreamingTranscriber(model, language, prompt, f, quiet)

            try:
                while True:
                    try:
                        data = audio_queue.get(timeout=0.5)

                    except queue.Empty:
                        continue

                    chunks = [data]
                    while not audio_queue.empty():
                        chunks.append(audio_queue.get_nowait())

                    samples = to_whisper_format(b"".join(chunks), channels, rate)
                    transcriber.add_audio(samples)

            except KeyboardInterrupt:
                print("\nStopping. Transcribing the rest...")
                stream.stop_stream()

                chunks = []
                while not audio_queue.empty():
                    chunks.append(audio_queue.get_nowait())

                if chunks:
                    samples = to_whisper_format(b"".join(chunks), channels, rate)
                    transcriber.add_audio(samples)

                transcriber.finish()

    print(f"Saved to {path}")


def transcribe_livestream(model, info, language, prompt, path, quiet=False):
    import av
    import queue
    import threading

    stream_url = info["url"]

    headers = info.get("http_headers") or {}
    header_text = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    if header_text:
        options = {"headers": header_text}
    else:
        options = {}

    print(f"Live stream: {info.get('title', '')}")
    print("Press Ctrl + C to stop")

    audio_queue = queue.Queue()
    stop = threading.Event()

    def reader():
        container = av.open(stream_url, options=options)
        resampler = av.AudioResampler(format="flt", layout="mono", rate=WHISPER_RATE)
        try:
            for frame in container.decode(audio=0):
                if stop.is_set():
                    break
                for out in resampler.resample(frame):
                    audio_queue.put(out.to_ndarray().reshape(-1))
        finally:
            container.close()
            audio_queue.put(None)

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()

    with open(path, "w", encoding="utf-8") as f:
        transcriber = StreamingTranscriber(model, language, prompt, f, quiet)

        try:
            ended = False
            while not ended:
                try:
                    chunks = [audio_queue.get(timeout=0.5)]
                except queue.Empty:
                    continue

                while not audio_queue.empty():
                    chunks.append(audio_queue.get_nowait())

                if any(chunk is None for chunk in chunks):
                    ended = True
                    chunks = [chunk for chunk in chunks if chunk is not None]

                if chunks:
                    transcriber.add_audio(np.concatenate(chunks))

        except KeyboardInterrupt:
            print("\nStopping. Transcribing the rest...")
            stop.set()

            chunks = []
            while not audio_queue.empty():
                chunk = audio_queue.get_nowait()
                if chunk is not None:
                    chunks.append(chunk)

            if chunks:
                transcriber.add_audio(np.concatenate(chunks))

        transcriber.finish()

    print(f"Saved to {path}")