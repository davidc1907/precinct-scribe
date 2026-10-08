# precinct-scribe

precinct-scribe transcribes political speeches, debates and press conferences with timestamps. It works with local video and audio files, links (YouTube and everything else yt-dlp supports), live streams and the system audio of your computer. Transcription runs locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and the Whisper `large-v3` model, so no audio leaves your machine.

precinct-scribe is free and open source. It is made for everyone who wants to follow what politicians actually say: journalists, researchers, students, activists and anyone else who is interested. It was originally built for the research and news work of [Precinct Room](https://precinct-room.com).

## Quick start (Windows)

1. Download the latest ZIP from [Releases](https://github.com/davidc1907/precinct-scribe/releases) and unzip it.
2. Double click `install.bat`. If Python is missing, it is installed automatically. In that case, run `install.bat` a second time afterwards.
3. Wait until it says *Installation finished*. The Whisper model (about 3 GB) is downloaded during the installation, so this takes a while.
4. Open a terminal in the folder (for example by typing `cmd` into the Explorer address bar and pressing Enter) and start transcribing:

```
scribe -f speech.mp4 -o speech
scribe -l "https://www.youtube.com/watch?v=..." -o debate
scribe -a -o live_recording
```

The transcript is saved in `transcripts/`.

For all options run `scribe -h` or see [Usage](#usage).

## Features

* **Files:** transcribe any local video or audio file
* **Links:** download and transcribe videos from YouTube and other sites supported by yt-dlp
* **Live streams:** transcribe a running live stream word by word with a delay of a few seconds
* **System audio (Windows only):** record and transcribe whatever your computer is playing, for example a parliament stream in the browser
* **Term lists:** improve the spelling of names and political terms with prompts per language and topic
* **Clips:** transcribe only part of a file with `--start` and `--end`
* **Quiet mode:** show a progress line instead of the full text

Every line of the transcript has the format

```
[0:01:23 -> 0:01:29] Text of the segment
```

The transcript is written while it is created, so you can open the file at any time.

## Requirements

* Python 3.11 or newer (tested with 3.13)
* An NVIDIA GPU is recommended, but not required. Without one, the program runs on the CPU with the smaller `small` model. This is slower and makes more mistakes, especially with names. Use `-m` to choose another model. Live transcription (`-l` with a live stream, `-a`) needs a GPU to keep up.
* Windows for system audio recording (`-a`). Files, links and live streams should also work on Linux and macOS, but this is not tested yet. If you run into problems, please open an issue.

FFmpeg does not need to be installed separately, PyAV brings its own copy.

## Manual installation

Use this if you are on Linux or macOS, or if you prefer to set things up yourself.

```
git clone https://github.com/davidc1907/precinct-scribe.git
cd precinct-scribe
python -m venv .venv
```

Activate the virtual environment:

| Shell | Command |
|---|---|
| cmd | `.venv\Scripts\activate.bat` |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Linux / macOS | `source .venv/bin/activate` |

Then install the dependencies:

```
pip install -r requirements-gpu.txt
```

`requirements-gpu.txt` also installs the CUDA libraries (cuBLAS, cuDNN) through pip. On Windows the script finds them automatically. If CUDA 12 and cuDNN 9 are already installed on your system, `pip install -r requirements.txt` is enough.

The model (about 3 GB) is downloaded automatically on the first run.

## Usage

```
python scribe.py (-f FILE | -l LINK | -a | --list-devices) [options]
```

If you used `install.bat`, you can write `scribe` instead of `python scribe.py`.

### Sources (choose exactly one)

| Option | Description |
|---|---|
| `-f`, `--file FILE` | Transcribe a local file |
| `-l`, `--link LINK` | Transcribe a link. Live streams are detected automatically. |
| `-a`, `--audio` | Record and transcribe the system audio (Windows) |
| `--list-devices` | List the available audio devices and exit |

### Options

| Option | Description |
|---|---|
| `-o`, `--output NAME` | Name of the transcript, saved as `transcripts/NAME.txt` (default: `transcript`) |
| `-s`, `--language CODE` | Language of the audio, for example `de` or `en` (default: `de`) |
| `-t`, `--topics LIST` | Comma separated topics from the term list, for example `bundestag,migration` |
| `-n`, `--names TEXT` | Names and terms that appear in the recording, for example `"Friedrich Merz, Lars Klingbeil"` |
| `--start TIME` | Start point, for example `1:42:00` (files and links only) |
| `--end TIME` | End point, for example `1:50:00` (files and links only) |
| `-q`, `--quiet` | Do not print the text, show the progress instead |
| `--device NUMBER` | Audio device for `-a`, see `--list-devices` |
| `--cpu` | Run on the CPU even if an NVIDIA GPU is available |
| `-m`, `--model NAME` | Whisper model, for example `small`, `medium`, `turbo` or `large-v3` (default: `large-v3` on the GPU, `small` on the CPU) |

### Examples

Transcribe a file:

```
python scribe.py -f speech.mp4 -o speech_merz
```

Transcribe part of a YouTube video in English with topics and names:

```
python scribe.py -l "https://www.youtube.com/watch?v=..." -s en -t economy -n "Jerome Powell" --start 0:10:00 --end 0:45:00
```

Transcribe a live stream (stop with Ctrl + C):

```
python scribe.py -l "https://www.youtube.com/watch?v=..." -o debate_live -q
```

Record a Bundestag debate from the system audio, with the speakers of the day:

```
python scribe.py --list-devices
python scribe.py -a --device 35 -t bundestag -n "Name One, Name Two" -o bundestag
```

Stop the recording with Ctrl + C. The remaining audio is transcribed before the program exits.

**Note:** An existing transcript with the same name is overwritten. Use a new name with `-o` for every recording.

### Which mode should I use?

| Situation | Mode |
|---|---|
| Live stream on YouTube or another site supported by yt-dlp | `-l` |
| Live stream on a site yt-dlp does not support, for example a broadcaster's media library | `-a` |
| Anything you want to quote or publish | `-l` or `-f` with the recording after the broadcast |

Live transcription is made for following a debate in real time. For quotes, transcribe the recording afterwards, which is more accurate. On YouTube you can simply run `-l` with the same link once the stream has ended.

### How live transcription works

Live streams and system audio are transcribed with the LocalAgreement method from [whisper_streaming](https://github.com/ufal/whisper_streaming). Every second, Whisper transcribes the last few seconds of audio again. A word is written to the transcript only when two passes in a row agree on it. Words that are written never change afterwards.

This means the transcript is a few seconds behind the speaker, and a new line appears when a sentence is finished.

When you stop the program, the last words have not been confirmed by a second pass. They are written in their own line and marked with `[unconfirmed]`.

## Term lists

The folder `terms` contains one TOML file per language (`de.toml`, `en.toml`). Each file has a `base` prompt that is always used and a table `topics` with additional terms:

```toml
base = "U.S. news. White House, Congress, Senate, ..."

[topics]
economy = "Federal Reserve, interest rates, inflation, ..."
immigration = "Immigration, asylum seekers, refugees, ..."
```

Use topics with `-t economy` and add names with `-n`. Whisper only reads the last part of a long prompt, so keep it short. The program warns you when the prompt gets longer than 150 words.

For a parliament debate, the best names are the speakers of the day. The Bundestag publishes the agenda and the speakers for each sitting on [bundestag.de](https://www.bundestag.de/tagesordnungen). Pass them with `-n` instead of adding every member of parliament to the term list.

To add a language, create a new file like `terms/fr.toml` and use `-s fr`. Without a term list for a language only the names from `-n` are used.

## Contributing term lists

Term lists in more languages are very welcome! If you speak a language that is not covered yet, or you know the political landscape of a country well, please add a file to `terms/` and open a pull request.

A few things that help:

* Name the file after the language code Whisper uses, for example `fr.toml`, `es.toml` or `tr.toml`.
* Use the same structure as the existing files: a `base` prompt and a `[topics]` table.
* Keep each prompt short. Whisper only reads roughly the last 150 words.
* Use the spelling that local news outlets use, especially for names.
* Please use neutral, descriptive terms, not political slogans. For example, use "undocumented immigrants", not "illegal aliens".
* Write a short comment at the top of the file about the region and the sources you used.
* Office holders change, so please also send updates for the existing lists.

Improvements to the German and English lists are welcome too.

## Recording only one program with VB-CABLE

With `-a` everything your computer plays is recorded, including notification sounds. To record only the browser:

1. Install [VB-CABLE](https://vb-audio.com/Cable/).
2. Open *Settings > System > Sound > Volume mixer* and set the output of your browser to **CABLE Input**.
3. Find the number of the CABLE device with `python scribe.py --list-devices`.
4. Start the recording with `python scribe.py -a --device NUMBER`.

You will not hear the browser anymore. To listen at the same time, open the sound control panel, go to *Recording > CABLE Output > Properties > Listen*, enable *Listen to this device* and choose your speakers or headphones.

## Accuracy

Whisper is good, but not perfect. Names, numbers and rare terms are often wrong, especially when they are not in the prompt. A single wrong word can turn a statement into its opposite, for example a missing "not" or "no". Whisper can also invent text during silence or music. Known phrases like subtitle credits are filtered out, but not everything can be caught.

**Always check quotes against the original recording or the official transcript before you publish them.** The timestamps make that easy.

## Known limitations

* The timestamps of `-a` and live streams start at the beginning of the recording, not at the time in the original broadcast.
* Live transcription is a few seconds behind the speaker. On a slow GPU the delay can grow over time.
* yt-dlp may show a warning about a missing JavaScript runtime for YouTube. Downloading usually still works. If not, update yt-dlp with `pip install -U yt-dlp`.
* GPU acceleration only works with NVIDIA GPUs (CUDA). On AMD or Intel GPUs and on Apple Silicon the program runs on the CPU.
* On the CPU, live transcription can fall behind. Use a smaller model with `-m`, for example `-m base`.

## Privacy

Transcripts are saved in `transcripts/` and downloads in `downloads/`. Both folders are listed in `.gitignore` and should never be pushed to a public repository.

## Acknowledgements

Live transcription is based on the LocalAgreement policy from whisper_streaming by Dominik Macháček, Raj Dabre and Ondřej Bojar (MIT License):

> Macháček, D., Dabre, R., Bojar, O. (2023). *Turning Whisper into Real-Time Transcription System.* Proceedings of IJCNLP-AACL 2023: System Demonstrations. https://aclanthology.org/2023.ijcnlp-demo.3/

## License

See [LICENSE](LICENSE).

## Contact

Questions and feedback: contact@precinct-room.com
