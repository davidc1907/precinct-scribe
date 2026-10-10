# precinct-scribe

precinct-scribe transcribes political speeches, debates and press conferences with timestamps. It works with local video and audio files, links (YouTube and everything else yt-dlp supports), live streams and the system audio of your computer. You can use it as a desktop app or from the command line. Transcription runs locally with [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and the Whisper `large-v3` model, so no audio leaves your machine.

precinct-scribe is free and open source. It is made for everyone who wants to follow what politicians actually say: journalists, researchers, students, activists and anyone else who is interested. It was originally built for the research and news work of [Precinct Room](https://precinct-room.com).

## Quick start (Windows)

1. Download the latest ZIP from [Releases](https://github.com/davidc1907/precinct-scribe/releases) and unzip it. Windows sometimes creates a folder inside a folder with the same name. Use the inner folder, the one where you can see `install.bat` and `scribe.bat`.
2. Double click `install.bat`. If Python is missing, it is installed automatically.
3. Wait until it says *Installation finished*. The installation downloads about 4.5 GB with an NVIDIA GPU (mostly the Whisper model and the CUDA libraries) and about 0.6 GB without one, so this takes a while.
4. Double click `scribe.bat`. The app opens.

The transcript is saved in `transcripts/`.

## Using the app

The app has two tabs. In **Settings** you choose what to transcribe, in **Output** you follow the transcript while it is created.

1. **Choose a source:** *PC-Audio* records what your computer plays, *File* transcribes a video or audio file, *Livestream* follows a running stream and *Video-Link* downloads and transcribes a video, for example from YouTube.
2. Depending on the source, choose the **audio device**, click **File** to pick a file or paste the **link**.
3. For files and video links you can transcribe only a part with **Start** and **End**, for example `1:00:00` and `1:10:00`. Leave both empty to transcribe everything.
4. Choose the **language** and a **term list**, and enter the **names and terms** that come up in the recording, separated by commas. For a parliament debate, the speakers of the day work best.
5. **CPU-Mode** and **Model** are set automatically. You only need to change them if the transcription is too slow.
6. Enter a name under **Save transcript as**. The current date and time are already filled in.
7. Confirm the two notes and click **Start Transcription**.

The app switches to the **Output** tab. A progress bar shows how far the download and the transcription are. For PC-Audio and live streams the end is unknown, so the bar only shows that the app is working. Click **Stop** to end a recording. The remaining audio is still transcribed.

The first start takes longer, because the model has to be loaded.

## Command line

Everything the app does also works from the command line. Open the precinct-scribe folder in the Explorer, click into the address bar, type `cmd` and press Enter. A terminal opens in the right folder. Now type `scribe` with the options you need, for example:

```
scribe -f speech.mp4 -o speech
scribe -l "https://www.youtube.com/watch?v=..." -o debate
scribe -a -o live_recording
```

`scribe -h` shows all options.

### Cheat sheet

| I want to ... | Command |
|---|---|
| transcribe a video or audio file | `scribe -f speech.mp4 -o speech` |
| transcribe only part of a file | `scribe -f speech.mp4 --start 1:00:00 --end 1:10:00` |
| transcribe a YouTube video | `scribe -l "LINK" -o debate` |
| follow a YouTube live stream | `scribe -l "LINK" -o live` |
| record what my computer plays | `scribe -a -o recording` |
| stop a live recording | press Ctrl + C |
| transcribe English | add `-s en` |
| get names right | add `-n "Name One, Name Two"` |
| use a topic from the term list | add `-t bundestag` |
| only see the progress | add `-q` |
| see all options | `scribe -h` |

For more details see [Usage](#usage).

## Features

* **Desktop app:** all features in one window, with a live view of the transcript and a progress bar
* **Files:** transcribe any local video or audio file
* **Links:** download and transcribe videos from YouTube and other sites supported by yt-dlp
* **Live streams:** transcribe a running live stream word by word with a delay of a few seconds
* **System audio (Windows only):** record and transcribe whatever your computer is playing, for example a parliament stream in the browser
* **Term lists:** improve the spelling of names and political terms with prompts per language and topic
* **Clips:** transcribe only part of a file with `--start` and `--end`
* **Quiet mode:** show a progress line instead of the full text on the command line

Every line of the transcript has the format

```
[0:01:23 -> 0:01:29] Text of the segment
```

The transcript is written while it is created, so you can open the file at any time.

## Requirements

* Python 3.11 or newer (tested with 3.13)
* An NVIDIA GPU is recommended, but not required. Without one, the program runs on the CPU with the smaller `small` model. This is slower and makes more mistakes, especially with names. Use `-m` to choose another model. Live transcription (`-l` with a live stream, `-a`) needs a GPU to keep up.
* Windows for system audio recording (`-a`). Files, links and live streams should also work on Linux and macOS, but this is not tested yet. If you run into problems, please open an issue.
* The desktop app is made and tested for Windows. On Linux, Python needs Tk (for example the package `python3-tk`), and the font falls back to a system font.

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

Start the app with `python gui.py` or the command line version with `python scribe.py`.

## Usage

This section describes the command line version.

```
python scribe.py (-f FILE | -l LINK | -a | --list-devices) [options]
```

If you used `install.bat` and opened a terminal in the precinct-scribe folder (see [Command line](#command-line)), you can write `scribe` instead of `python scribe.py`.

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
| Live stream on YouTube or another site supported by yt-dlp | *Livestream* or `-l` |
| Live stream on a site yt-dlp does not support, for example a broadcaster's media library | *PC-Audio* or `-a` |
| Anything you want to quote or publish | *Video-Link*, *File*, `-l` or `-f` with the recording after the broadcast |

Live transcription is made for following a debate in real time. For quotes, transcribe the recording afterwards, which is more accurate. On YouTube you can simply use the same link again once the stream has ended.

### How live transcription works

Live streams and system audio are transcribed with the LocalAgreement method from [whisper_streaming](https://github.com/ufal/whisper_streaming). Every second, Whisper transcribes the last few seconds of audio again. A word is written to the transcript only when two passes in a row agree on it. Words that are written never change afterwards.

This means the transcript is a few seconds behind the speaker, and a new line appears when a sentence is finished.

When you stop the recording, the last words have not been confirmed by a second pass. They are written in their own line and marked with `[unconfirmed]`.

## Term lists

The folder `terms` contains one TOML file per language (`de.toml`, `en.toml`). Each file has a `base` prompt that is always used and a table `topics` with additional terms:

```toml
base = "U.S. news. White House, Congress, Senate, ..."

[topics]
economy = "Federal Reserve, interest rates, inflation, ..."
immigration = "Immigration, asylum seekers, refugees, ..."
```

In the app, choose the topic in the second dropdown and enter names in the text field. On the command line, use topics with `-t economy` and add names with `-n`. Whisper only reads the last part of a long prompt, so keep it short. The program warns you when the prompt gets longer than 150 words.

For a parliament debate, the best names are the speakers of the day. The Bundestag publishes the agenda and the speakers for each sitting on [bundestag.de](https://www.bundestag.de/tagesordnungen). Enter them as names instead of adding every member of parliament to the term list.

To add a language, create a new file like `terms/fr.toml`. It appears in the language dropdown of the app automatically, on the command line use `-s fr`. Without a term list for a language only the names from `-n` are used.

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

With PC-Audio everything your computer plays is recorded, including notification sounds. To record only the browser:

1. Install [VB-CABLE](https://vb-audio.com/Cable/).
2. Open *Settings > System > Sound > Volume mixer* and set the output of your browser to **CABLE Input**.
3. In the app, choose the CABLE device in the device dropdown. On the command line, find its number with `scribe --list-devices` and start with `scribe -a --device NUMBER`.

You will not hear the browser anymore. To listen at the same time, open the sound control panel, go to *Recording > CABLE Output > Properties > Listen*, enable *Listen to this device* and choose your speakers or headphones.

## Accuracy

Whisper is good, but not perfect. Names, numbers and rare terms are often wrong, especially when they are not in the prompt. A single wrong word can turn a statement into its opposite, for example a missing "not" or "no". Whisper can also invent text during silence or music. Known phrases like subtitle credits are filtered out, but not everything can be caught.

In a 2-hour test with a Bundestag debate (system audio, `large-v3`, compared with the official plenary record), we found no hallucinations, two gaps of about 35 to 40 seconds and 6 errors that changed the meaning of a statement. Three of those six were a missing "nicht" (not). Names that were not entered as names were often misspelled.

**Always check quotes against the original recording or the official transcript before you publish them.** The timestamps make that easy.

## Known limitations

* The timestamps of PC-Audio and live streams start at the beginning of the recording, not at the time in the original broadcast.
* A download cannot be stopped halfway. Stop only takes effect once the transcription has started.
* Live transcription is a few seconds behind the speaker. On a slow GPU the delay can grow over time.
* yt-dlp may show a warning about a missing JavaScript runtime for YouTube. `install.bat` installs Deno to fix this. Without it, YouTube downloads can still work, but are often much larger, because only formats with video are available. If downloads stop working, update yt-dlp with `pip install -U yt-dlp`.
* Music and singing are usually not transcribed. The voice detection filters them out, because the tool is made for speech.
* GPU acceleration only works with NVIDIA GPUs (CUDA). On AMD or Intel GPUs and on Apple Silicon the program runs on the CPU.
* On the CPU, live transcription can fall behind. Use a smaller model, for example `small` in the app or `-m base` on the command line.

## Privacy

Transcripts are saved in `transcripts/` and downloads in `downloads/`. Both folders are listed in `.gitignore` and should never be pushed to a public repository.

## Acknowledgements

Live transcription is based on the LocalAgreement policy from whisper_streaming by Dominik Macháček, Raj Dabre and Ondřej Bojar (MIT License):

> Macháček, D., Dabre, R., Bojar, O. (2023). *Turning Whisper into Real-Time Transcription System.* Proceedings of IJCNLP-AACL 2023: System Demonstrations. https://aclanthology.org/2023.ijcnlp-demo.3/

The desktop app is built with [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) (MIT License) and uses the font [Inter](https://rsms.me/inter/) by Rasmus Andersson (SIL Open Font License 1.1, see `fonts/OFL.txt`).

## License

See [LICENSE](LICENSE).

## Contact

Questions and feedback: contact@precinct-room.com
