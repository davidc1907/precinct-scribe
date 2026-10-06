import numpy as np

WHISPER_RATE = 16000

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

def write_segments(segments, f, offset=0.0):
    for segment in segments:
        start_time = convert_seconds(offset + segment.start)
        end_time = convert_seconds(offset + segment.end)
        line=f"[{start_time} -> {end_time}] {segment.text}"
        print(line)
        f.write(line + "\n")
        f.flush()


def transcribe_chunk(model, raw_bytes, channels, rate, language, prompt, f, offset):
    audio = to_whisper_format(raw_bytes, channels, rate)
    segments,_ = model.transcribe(
        audio,
        language=language,
        initial_prompt=prompt,
        vad_filter=True,
        condition_on_previous_text=False
    )
    write_segments(segments, f, offset)


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


# Function converting the seconds from whisper into hours minutes and seconds

def convert_seconds(seconds):
    seconds = int(seconds)
    hour = seconds // 3600
    seconds = seconds % 3600
    minutes = seconds // 60
    seconds = seconds % 60
    timestamp = (f"{hour}:{minutes:02d}:{seconds:02d}")
    return timestamp


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


def transcribe_system_audio(model, device_index, language, prompt, path, chunk_seconds=30):
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
        chunk_bytes = bytes_per_second * chunk_seconds

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

            buffer = bytearray()
            offset = 0.0

            try:
                while True:
                    try:
                        buffer += audio_queue.get(timeout=0.5)

                    except queue.Empty:
                        continue

                    if len(buffer) >= chunk_bytes:
                        transcribe_chunk(model, bytes(buffer), channels, rate, language, prompt, f, offset)
                        offset += len(buffer) / bytes_per_second
                        buffer = bytearray()

            except KeyboardInterrupt:
                print("\n Stopping. Transcribing the rest...")
                stream.stop_stream()
                while not audio_queue.empty():
                    buffer += audio_queue.get()

                if buffer:
                    transcribe_chunk(model, bytes(buffer), channels, rate, language, prompt, f, offset)

    print(f"Saved to {path}")



