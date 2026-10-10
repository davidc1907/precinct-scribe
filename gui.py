import queue
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import av
import ctranslate2
import customtkinter as ctk

import scribe
from livestream import get_devices, transcribe_livestream, transcribe_system_audio
from utils import parse_time

FONTS = Path(__file__).parent / "fonts"
LIMITATIONS_URL = "https://github.com/davidc1907/precinct-scribe#known-limitations"

TEXT = "#000000"
GRAY = "#D9D9D9"
GRAY_HOVER = "#C4C4C4"
BORDER = "#000000"
BLUE = "#006BEE"

BUTTON_STYLE = {
    "fg_color": GRAY,
    "hover_color": GRAY_HOVER,
    "text_color": TEXT,
    "corner_radius": 0
}

ENTRY_STYLE = {
    "fg_color": "white",
    "border_color": BORDER,
    "border_width": 1,
    "corner_radius": 0,
    "text_color": TEXT
}

NO_TOPIC = "No term list selected"

for file in FONTS.glob("*.ttf"):
    ctk.FontManager.load_font(str(file))


def file_duration(path):
    try:
        with av.open(str(path)) as container:
            if container.duration:
                return container.duration / 1_000_000
    except Exception:
        pass
    return None


def line_end_seconds(line):
    try:
        times = line[1:line.index("]")]
        return parse_time(times.split(" -> ")[1])
    except (ValueError, IndexError):
        return None


def clean_file_name(name):
    for char in '/\\:*?"<>|':
        name = name.replace(char, "_")
    return name


class PrecinctScribeGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.file_path = None
        self.geometry("900x900")
        self.title("PRECINCT SCRIBE")
        ctk.set_appearance_mode("light")
        self.configure(fg_color="white")

        self.title_font = ctk.CTkFont(family="Inter", size=32, weight="bold")
        self.tab_font = ctk.CTkFont(family="Inter SemiBold", size=16)
        self.medium_font = ctk.CTkFont(family="Inter Medium", size=14)
        self.regular_font = ctk.CTkFont(family="Inter", size=14)
        self.regular16_font = ctk.CTkFont(family="Inter", size=16)
        self.link_font = ctk.CTkFont(family="Inter", size=14, underline=True)

        self.lines = queue.Queue()
        self.status = queue.Queue()
        self.progress = queue.Queue()
        self.stop = threading.Event()
        self.finished = threading.Event()
        self.running = False
        self.progress_running = False
        self.model = None
        self.model_key = None

        title_label = ctk.CTkLabel(self, text="PRECINCT SCRIBE", font=self.title_font,
                                   text_color=TEXT, anchor="w")
        title_label.pack(fill="x", padx=50, pady=(20, 0))

        self.tabs = ctk.CTkTabview(
            self,
            fg_color="white",
            corner_radius=0,
            segmented_button_fg_color="white",
            segmented_button_selected_color="white",
            segmented_button_selected_hover_color="#F0F0F0",
            segmented_button_unselected_color="white",
            segmented_button_unselected_hover_color="#F0F0F0",
            text_color="black",
        )
        self.tabs.pack(fill="both", expand=True)
        self.settings_tab = self.tabs.add("Settings")
        self.output_tab = self.tabs.add("Output")

        self.build_source()
        self.build_time()
        self.build_model()
        self.build_terms()
        self.build_output_name()
        self.build_disclaimers()
        self.build_output()

        self.update_source()
        self.poll()


    def build_source(self):
        self.settings_tab.grid_columnconfigure(0, weight=1)
        self.frame_source = ctk.CTkFrame(self.settings_tab, fg_color="transparent")
        self.frame_source.grid(row=0, column=0, padx=50, pady=(40, 0))
        self.frame_source.grid_columnconfigure(1, weight=1)

        self.file_button = ctk.CTkButton(self.frame_source, text="File", font=self.tab_font, height=29, width=158, command=self.choose_file, **BUTTON_STYLE)
        self.file_button.grid(row=0, column=0, sticky="w")

        self.link_entry = ctk.CTkEntry(self.frame_source, placeholder_text="Livestream- / Video-Link", font=self.tab_font, width=600, height=29, justify="center", **ENTRY_STYLE)
        self.link_entry.grid(row=0, column=1, sticky="ew", padx=(160, 0))

        radio_frame = ctk.CTkFrame(self.frame_source, fg_color="transparent")
        radio_frame.grid(row=1, column=0, columnspan=2, pady=(30, 0))

        self.source_var = ctk.StringVar(value="audio")

        self.pc_audio_selector = ctk.CTkRadioButton(radio_frame, text="PC-Audio", value="audio", variable=self.source_var, font=self.regular_font, command=self.update_source, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.pc_audio_selector.grid(row=0, column=0, padx=30)
        self.file_selector = ctk.CTkRadioButton(radio_frame, text="File", value="file", variable=self.source_var, font=self.regular_font, command=self.update_source, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.file_selector.grid(row=0, column=1, padx=30)
        self.livestream_selector = ctk.CTkRadioButton(radio_frame, text="Livestream", value="live", variable=self.source_var, font=self.regular_font, command=self.update_source, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.livestream_selector.grid(row=0, column=2, padx=30)
        self.video_link_selector = ctk.CTkRadioButton(radio_frame, text="Video-Link", value="video-link", variable=self.source_var, font=self.regular_font, command=self.update_source, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.video_link_selector.grid(row=0, column=3, padx=30)

        self.devices = {}
        default_name = None

        try:
            device_list = get_devices()
        except Exception:
            device_list = []

        for index, name, is_default in device_list:
            self.devices[name] = index
            if is_default:
                default_name = name

        device_names = list(self.devices)
        self.device_var = ctk.StringVar(value=default_name or "Select output device")

        self.device_menu = ctk.CTkOptionMenu(
            self.frame_source,
            values=device_names,
            variable=self.device_var,
            width=158, height=29,
            dynamic_resizing=False,
            font=self.medium_font,
            dropdown_font=self.regular_font,
            fg_color=GRAY,
            button_color=GRAY,
            button_hover_color=GRAY_HOVER,
            text_color=TEXT,
            corner_radius=0,
        )
        self.device_menu.grid(row=2, column=0, sticky="sw", pady=(30, 0))

    def build_time(self):
        self.frame_time = ctk.CTkFrame(self.frame_source, fg_color="transparent")
        self.frame_time.grid(row=2, column=1, sticky="w", pady=(30, 0))

        self.label_start = ctk.CTkLabel(self.frame_time, text="Start", font=self.tab_font, fg_color="transparent")
        self.label_start.grid(row=0, column=0, padx=(30, 0))
        self.start_entry = ctk.CTkEntry(self.frame_time, placeholder_text="HH:MM:SS", font=self.tab_font, width=158, height=29, justify="center", **ENTRY_STYLE)
        self.start_entry.grid(row=1, column=0, sticky="ew", padx=(30, 0))
        self.label_end = ctk.CTkLabel(self.frame_time, text="End", font=self.tab_font, fg_color="transparent")
        self.label_end.grid(row=0, column=2, padx=(30, 0))
        self.end_entry = ctk.CTkEntry(self.frame_time, placeholder_text="HH:MM:SS", font=self.tab_font, width=158, height=29, justify="center", **ENTRY_STYLE)
        self.end_entry.grid(row=1, column=2, sticky="ew", padx=(30, 0))


    def build_model(self):
        self.frame_lower = ctk.CTkFrame(self.settings_tab, fg_color="transparent")
        self.frame_lower.grid(row=1, column=0, sticky="nsew", padx=50, pady=(40, 0))
        self.frame_lower.grid_columnconfigure((0, 1), weight=1)

        self.frame_left = ctk.CTkFrame(self.frame_lower, fg_color="transparent")
        self.frame_left.grid(row=0, column=0, sticky="nw")

        self.frame_right = ctk.CTkFrame(self.frame_lower, fg_color="transparent")
        self.frame_right.grid(row=0, column=1, sticky="ne")

        has_gpu = ctranslate2.get_cuda_device_count() > 0
        self.cpu_var = ctk.BooleanVar(value=not has_gpu)

        if has_gpu:
            self.model_var = ctk.StringVar(value="large-v3")
        else:
            self.model_var = ctk.StringVar(value="small")

        self.cpu_selector = ctk.CTkCheckBox(self.frame_right, text="CPU-Mode", variable=self.cpu_var,
                                            command=self.update_model,
                                            font=self.regular_font, fg_color="black",
                                            border_color=GRAY, hover_color=GRAY_HOVER,
                                            corner_radius=0)
        self.cpu_selector.grid(row=0, column=0, sticky="w", padx=30)

        if not has_gpu:
            self.cpu_selector.configure(state="disabled")

        self.model_small = ctk.CTkRadioButton(self.frame_right, text="small (default without GPU)", variable=self.model_var, font=self.regular_font, value="small", fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.model_small.grid(row=1, column=0, sticky="w", padx=30, pady=(40, 0))
        self.model_medium = ctk.CTkRadioButton(self.frame_right, text="medium", variable=self.model_var, font=self.regular_font, value="medium", fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.model_medium.grid(row=2, column=0, sticky="w", padx=30, pady=(15, 0))
        self.model_turbo = ctk.CTkRadioButton(self.frame_right, text="turbo", variable=self.model_var, value="turbo", font=self.regular_font, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.model_turbo.grid(row=3, column=0, sticky="w", padx=30, pady=(15, 0))
        self.model_large = ctk.CTkRadioButton(self.frame_right, text="large-v3 (default with GPU)", variable=self.model_var, value="large-v3", font=self.regular_font, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER)
        self.model_large.grid(row=4, column=0, sticky="w", padx=30, pady=(15, 0))


    def build_terms(self):
        self.language_var = ctk.StringVar(value="de")

        languages = sorted(path.stem for path in scribe.TERMS_FOLDER.glob("*.toml"))

        self.language_menu = ctk.CTkOptionMenu(
            self.frame_left,
            values=languages,
            variable=self.language_var,
            command=self.update_terms,
            width=168, height=29,
            dynamic_resizing=False,
            font=self.medium_font,
            dropdown_font=self.regular_font,
            fg_color=GRAY,
            button_color=GRAY,
            button_hover_color=GRAY_HOVER,
            text_color=TEXT,
            corner_radius=0,
        )
        self.language_menu.grid(row=0, column=0, sticky="w")

        topics = scribe.available_topics("de")

        self.topic_var = ctk.StringVar(value="bundestag")

        self.topics_menu = ctk.CTkOptionMenu(
            self.frame_left,
            values=[NO_TOPIC] + topics,
            variable=self.topic_var,
            width=168, height=29,
            dynamic_resizing=False,
            font=self.medium_font,
            dropdown_font=self.regular_font,
            fg_color=GRAY,
            button_color=GRAY,
            button_hover_color=GRAY_HOVER,
            text_color=TEXT,
            corner_radius=0,
        )
        self.topics_menu.grid(row=0, column=1, sticky="w", padx=(20, 0))

        names_label = ctk.CTkLabel(self.frame_left,
                                   text="Names and terms, separated by commas",
                                   font=self.regular_font, text_color=TEXT)
        names_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(30, 4))

        self.names_box = ctk.CTkTextbox(self.frame_left,
                                        width=270, height=200,
                                        font=self.regular_font,
                                        fg_color="white",
                                        border_color=BORDER,
                                        border_width=1,
                                        corner_radius=0,
                                        text_color=TEXT,
                                        wrap="word")
        self.names_box.grid(row=3, column=0, columnspan=2, sticky="w")

    def build_output_name(self):
        self.output_label = ctk.CTkLabel(self.frame_left, text="Save transcript as", font=self.regular_font, text_color=TEXT)
        self.output_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=(30, 4))

        self.output_entry = ctk.CTkEntry(self.frame_left, font=self.regular_font, width=270, height=29, **ENTRY_STYLE)
        self.output_entry.grid(row=5, column=0, columnspan=2, sticky="w")
        self.output_entry.insert(0, datetime.now().strftime("%Y-%m-%d_%H%M"))


    def build_disclaimers(self):
        self.limits_var = ctk.BooleanVar(value=False)
        self.errors_var = ctk.BooleanVar(value=False)

        limits_row = ctk.CTkFrame(self.frame_right, fg_color="transparent")
        limits_row.grid(row=5, column=0, sticky="w", padx=30, pady=(60, 0))

        self.checkbox_limits = ctk.CTkCheckBox(limits_row, text="I have read the", variable=self.limits_var, command=self.update_start_button, font=self.regular_font, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER, corner_radius=0, offvalue=False, onvalue=True)
        self.checkbox_limits.pack(side="left")

        link = ctk.CTkLabel(limits_row, text="known limitations", text_color=BLUE, font=self.link_font, cursor="hand2")
        link.pack(side="left", padx=(4, 0))
        link.bind("<Button-1>", lambda event: webbrowser.open(LIMITATIONS_URL))

        dot = ctk.CTkLabel(limits_row, text=".", font=self.regular_font, text_color=TEXT)
        dot.pack(side="left")

        self.checkbox_errors = ctk.CTkCheckBox(self.frame_right, text="I understand that transcripts may contain errors\nand will verify all quotes against the original\nsource before publishing.", variable=self.errors_var, command=self.update_start_button, font=self.regular_font, fg_color="black", border_color=GRAY, hover_color=GRAY_HOVER, corner_radius=0, offvalue=False, onvalue=True)
        self.checkbox_errors.grid(row=6, column=0, sticky="w", padx=30, pady=(30, 0))

        self.start_button = ctk.CTkButton(self.frame_right, text="Start Transcription", font=self.tab_font, width=300, height=50, command=self.start, state="disabled", **BUTTON_STYLE)
        self.start_button.grid(row=7, column=0, sticky="e", padx=30, pady=(40, 0))


    def build_output(self):
        self.output_tab.grid_columnconfigure((0, 1), weight=1)
        self.output_tab.grid_rowconfigure(2, weight=1)

        self.status_label = ctk.CTkLabel(self.output_tab, text="Ready",
                                         font=self.medium_font, text_color=TEXT)
        self.status_label.grid(row=0, column=0, sticky="w", padx=(50, 0), pady=(30, 10))

        self.progress_label = ctk.CTkLabel(self.output_tab, text="",
                                           font=self.medium_font, text_color=TEXT)
        self.progress_label.grid(row=0, column=1, sticky="e", padx=(0, 50), pady=(30, 10))

        self.progress_bar = ctk.CTkProgressBar(self.output_tab, height=8, corner_radius=0, fg_color=GRAY, progress_color="black", mode="determinate")
        self.progress_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=50, pady=(0, 20))
        self.progress_bar.set(0)

        self.output_box = ctk.CTkTextbox(self.output_tab, font=self.regular_font, fg_color="white", border_color=BORDER, border_width=1, corner_radius=0, text_color=TEXT, wrap="word", state="disabled")
        self.output_box.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=50)

        self.stop_button = ctk.CTkButton(self.output_tab, text="Stop", font=self.tab_font, width=158, height=40, command=self.stop_transcription, state="disabled", **BUTTON_STYLE)
        self.stop_button.grid(row=3, column=1, sticky="e", padx=50, pady=30)


    def update_source(self):
        match self.source_var.get():
            case "audio":
                self.file_button.configure(state="disabled")
                self.link_entry.configure(state="disabled")
                self.device_menu.configure(state="normal")
            case "file":
                self.device_menu.configure(state="disabled")
                self.link_entry.configure(state="disabled")
                self.file_button.configure(state="normal")
            case "live":
                self.device_menu.configure(state="disabled")
                self.file_button.configure(state="disabled")
                self.link_entry.configure(state="normal")
            case "video-link":
                self.device_menu.configure(state="disabled")
                self.file_button.configure(state="disabled")
                self.link_entry.configure(state="normal")

        self.update_time()

    def update_time(self):
        match self.source_var.get():
            case "audio" | "live":
                self.start_entry.configure(state="disabled")
                self.end_entry.configure(state="disabled")
            case "file" | "video-link":
                self.start_entry.configure(state="normal")
                self.end_entry.configure(state="normal")

    def update_model(self):
        if self.cpu_var.get():
            self.model_var.set("small")
        else:
            self.model_var.set("large-v3")

    def update_terms(self, language):
        topics = scribe.available_topics(language)
        self.topics_menu.configure(values=[NO_TOPIC] + topics)
        self.topic_var.set(NO_TOPIC)

    def update_start_button(self):
        if self.running:
            self.start_button.configure(state="disabled")
        elif self.limits_var.get() and self.errors_var.get():
            self.start_button.configure(state="normal")
        else:
            self.start_button.configure(state="disabled")

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="Choose a video or audio file",
            filetypes=[
                ("Video and audio", "*.mp4 *.mkv *.mov *.webm *.mp3 *.wav *.m4a *.ogg *.flac"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        self.file_path = path
        self.file_button.configure(text=Path(path).name)

    def start(self):
        if self.running:
            return

        if not (self.limits_var.get() and self.errors_var.get()):
            return

        settings = {
            "source": self.source_var.get(),
            "file": self.file_path,
            "link": self.link_entry.get().strip(),
            "device": self.devices.get(self.device_var.get()),
            "start": self.start_entry.get().strip(),
            "end": self.end_entry.get().strip(),
            "language": self.language_var.get(),
            "topic": self.topic_var.get(),
            "names": self.names_box.get("1.0", "end").strip(),
            "output": clean_file_name(self.output_entry.get().strip()),
            "cpu": self.cpu_var.get(),
            "model": self.model_var.get(),
        }

        source = settings["source"]

        if source == "audio" and settings["device"] is None:
            messagebox.showwarning("Missing input", "Please select an audio device.")
            return

        if source == "file" and not (self.file_path and Path(self.file_path).is_file()):
            messagebox.showwarning("Missing input", "Please choose a file.")
            return

        if source in ("live", "video-link") and not settings["link"]:
            messagebox.showwarning("Missing input", "Please enter a link.")
            return

        # start and end only count for files and video links
        if source in ("audio", "live"):
            settings["start"] = ""
            settings["end"] = ""

        try:
            if settings["start"]:
                parse_time(settings["start"])
            if settings["end"]:
                parse_time(settings["end"])
        except ValueError:
            messagebox.showwarning("Invalid time", "Please enter times like 1:42:00.")
            return

        if not settings["output"]:
            settings["output"] = datetime.now().strftime("%Y-%m-%d_%H%M")

        self.output_box.configure(state="normal")
        self.output_box.delete("1.0", "end")
        self.output_box.configure(state="disabled")

        self.running = True
        self.stop.clear()
        self.finished.clear()
        self.tabs.set("Output")
        self.stop_button.configure(state="normal")
        self.start_button.configure(state="disabled")
        self.reset_progress()

        thread = threading.Thread(target=self.worker, args=(settings,), daemon=True)
        thread.start()


    def stop_transcription(self):
        self.stop.set()
        self.stop_button.configure(state="disabled")
        self.status_label.configure(text="Stopping, transcribing the rest...")


    def reset_progress(self):
        if self.progress_running:
            self.progress_bar.stop()
            self.progress_running = False
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self.progress_label.configure(text="")


    def poll(self):
        while not self.lines.empty():
            line = self.lines.get_nowait()
            self.output_box.configure(state="normal")
            self.output_box.insert("end", line + "\n")
            self.output_box.configure(state="disabled")
            self.output_box.see("end")

        while not self.status.empty():
            self.status_label.configure(text=self.status.get_nowait())

        while not self.progress.empty():
            value = self.progress.get_nowait()

            # None means the length is unknown, the bar just keeps moving
            if value is None:
                if not self.progress_running:
                    self.progress_bar.configure(mode="indeterminate")
                    self.progress_bar.start()
                    self.progress_running = True
                self.progress_label.configure(text="")
            else:
                if self.progress_running:
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate")
                    self.progress_running = False
                self.progress_bar.set(value)
                self.progress_label.configure(text=f"{value * 100:.0f} %")

        if self.running and self.finished.is_set():
            self.running = False
            self.stop_button.configure(state="disabled")
            self.update_start_button()

            if self.progress_running:
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
                self.progress_running = False

        self.after(100, self.poll)


    def load_model(self, cpu, model_name):
        key = (cpu, model_name)

        if self.model is None or self.model_key != key:
            self.status.put("Loading model... (the first time this downloads the model)")
            self.progress.put(None)
            self.model = scribe.load_model(cpu, model_name)
            self.model_key = key

        return self.model


    def worker(self, settings):
        try:
            start = None
            if settings["start"]:
                start = parse_time(settings["start"])

            end = None
            if settings["end"]:
                end = parse_time(settings["end"])

            topic = settings["topic"]
            if topic == NO_TOPIC:
                topic = None

            names = settings["names"] or None
            if names:
                names = ", ".join(line.strip() for line in names.splitlines() if line.strip())

            prompt = scribe.build_prompt(settings["language"], topic, names)
            path = scribe.transcript_path(settings["output"])
            model = self.load_model(settings["cpu"], settings["model"])

            source = settings["source"]

            if source == "audio":
                self.status.put("Recording system audio...")
                self.progress.put(None)
                transcribe_system_audio(model, settings["device"], settings["language"], prompt, path,
                                        quiet=True, on_line=self.lines.put, stop=self.stop)

            elif source == "file":
                self.transcribe_with_progress(model, settings["file"], path, settings["language"], prompt, start, end)

            else:
                self.status.put("Checking the link...")
                self.progress.put(None)
                info = scribe.get_link_info(settings["link"])

                if info.get("is_live"):
                    self.status.put("Transcribing the live stream...")
                    transcribe_livestream(model, info, settings["language"], prompt, path,
                                          quiet=True, on_line=self.lines.put, stop=self.stop)
                else:
                    self.status.put("Downloading...")
                    self.progress.put(0.0)
                    source_file = scribe.download_audio(settings["link"], on_progress=self.on_download)
                    self.transcribe_with_progress(model, source_file, path, settings["language"], prompt, start, end,
                                                  duration=info.get("duration"))

            if self.stop.is_set():
                self.status.put(f"Stopped. Saved to {path}")
            else:
                self.status.put(f"Finished. Saved to {path}")
                self.progress.put(1.0)

        except Exception as error:
            traceback.print_exc()
            self.status.put(f"Error: {error}")

        finally:
            self.finished.set()


    def on_download(self, info):
        # called by yt-dlp in the worker thread, so only queues here
        if info["status"] != "downloading":
            return

        total = info.get("total_bytes") or info.get("total_bytes_estimate")
        downloaded = info.get("downloaded_bytes") or 0

        if not total:
            self.progress.put(None)
            return

        self.progress.put(min(1.0, downloaded / total))

        text = f"Downloading... {downloaded / 1024 ** 2:.0f} of {total / 1024 ** 2:.0f} MB"
        eta = info.get("eta")
        if eta:
            eta = int(eta)
            text += f", {eta // 60}:{eta % 60:02d} left"
        self.status.put(text)


    def transcribe_with_progress(self, model, source_file, path, language, prompt, start, end, duration=None):
        if duration is None:
            duration = file_duration(source_file)

        begin = start or 0
        stop_at = end or duration

        total = None
        if stop_at:
            total = stop_at - begin

        def on_line(line):
            self.lines.put(line)

            if total:
                seconds = line_end_seconds(line)
                if seconds is not None:
                    self.progress.put(min(1.0, max(0.0, (seconds - begin) / total)))

        self.status.put("Transcribing...")
        if total:
            self.progress.put(0.0)
        else:
            self.progress.put(None)

        scribe.transcribe_file(model, source_file, path, language, prompt,
                               start, end, quiet=True, on_line=on_line, stop=self.stop)



if __name__ == "__main__":
    app = PrecinctScribeGUI()
    app.mainloop()
