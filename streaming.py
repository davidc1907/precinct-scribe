import numpy as np

from utils import convert_seconds, WHISPER_RATE

# Phrases from subtitle credits and video outros in Whisper's training data.
# A segment that contains one of these is dropped.
HALLUCINATIONS = [
    # German broadcasters and subtitle credits
    "Untertitelung des ZDF",
    "Untertitel im Auftrag des ZDF",
    "Untertitelung im Auftrag des ZDF",
    "Untertitel der Amara.org-Community",
    "Untertitel von Stephanie Geiges",
    "Copyright WDR",
    "Untertitelung. BR",
    "Untertitelung: BR",
    "SWR 2020",
    "SWR 2021",
    # German video outros
    "Vielen Dank fürs Zuschauen",
    "Danke fürs Zuschauen",
    "Abonniert den Kanal",
    "Bis zum nächsten Mal",
    # English
    "Subtitles by the Amara.org community",
    "Thank you for watching",
    "Thanks for watching",
    "Please subscribe",
    "Like and subscribe",
    "Transcription by CastingWords",
    "www.mooji.org",
    # other languages that show up when Whisper loses track
    "Sous-titrage ST' 501",
    "Sous-titres réalisés para la communauté d'Amara.org",
    "Субтитры сделал DimaTorzok",
    "Продолжение следует",
]

# Hallucinations only if they are the whole segment ("Musikschulen" must stay).
HALLUCINATION_SEGMENTS = [
    "Musik",
    "Applaus",
    "Untertitel",
    "Ende",
]

ABBREVIATIONS = {
    "de": [
        # titles
        "dr.", "prof.", "hr.", "fr.", "dipl.",
        # common
        "z.b.", "bzw.", "ca.", "usw.", "etc.", "u.a.", "d.h.", "v.a.",
        "vgl.", "ggf.", "sog.", "bspw.", "inkl.", "evtl.", "bzgl.",
        "z.t.", "o.ä.", "u.ä.", "i.d.r.", "zzgl.", "gem.", "lt.",
        # numbers and units
        "nr.", "mio.", "mrd.", "tsd.", "std.", "min.", "jh.",
        # law
        "art.", "abs.", "ziff.", "ff.",
        # places
        "str.", "st.",
    ],
    "en": [
        # titles
        "mr.", "mrs.", "ms.", "dr.", "prof.", "jr.", "sr.",
        "sen.", "rep.", "gov.", "pres.", "gen.", "lt.", "col.", "sgt.", "capt.", "adm.",
        # countries and organizations
        "u.s.", "u.k.", "u.n.", "e.u.", "d.c.",
        # common
        "e.g.", "i.e.", "etc.", "vs.", "approx.", "no.", "dept.", "st.",
        "inc.", "corp.", "co.", "ltd.",
        # time
        "a.m.", "p.m.",
        "jan.", "feb.", "aug.", "sept.", "oct.", "nov.", "dec.",
    ],
}

STEP_SECONDS = 1.0
TRIM_SECONDS = 15.0
MAX_BUFFER_SECONDS = 30.0
PROMPT_WORDS = 60
MAX_LINE_WORDS = 25
NO_SPEECH_THRESHOLD = 0.9


def is_sentence_end(text, language):
    word = text.strip().lower()
    if not word.endswith((".", "!", "?")):
        return False
    if word[:-1].isdigit():
        return False
    if word in ABBREVIATIONS.get(language, []):
        return False
    return True


def normalize(text):
    result = ""
    for char in text:
        if char.isalnum():
            result += char
    return result.lower()


def common_prefix_length(old, new):
    length = 0
    for i in range(min(len(old), len(new))):
        if old[i] == new[i]:
            length = length + 1
        else:
            break
    return length


def is_hallucination(text):
    lowered = text.lower()
    for phrase in HALLUCINATIONS:
        if phrase.lower() in lowered:
            return True

    for phrase in HALLUCINATION_SEGMENTS:
        if normalize(text) == normalize(phrase):
            return True

    return False


class StreamingTranscriber:
    def __init__(self, model, language, prompt, f, quiet=False):
        self.model = model
        self.language = language
        self.prompt = prompt
        self.f = f
        self.quiet = quiet

        self.buffer = np.zeros(0, dtype=np.float32)
        self.buffer_offset = 0.0
        self.new_samples = 0

        self.previous_words = []
        self.committed_until = 0.0
        self.committed_text = []
        self.current_line = []

    # ---------- public ----------

    def add_audio(self, samples):
        self.buffer = np.concatenate([self.buffer, samples])
        self.new_samples += len(samples)

        if self.new_samples >= STEP_SECONDS * WHISPER_RATE:
            self.process()
            self.new_samples = 0

    def finish(self):
        self.write_line()

        words = None
        if len(self.buffer) > 0:
            words = self.transcribe_buffer()

        if words is None:
            words = self.previous_words
        else:
            words = self.drop_already_committed(words)

        if words:
            self.current_line = words
            self.write_line(" [unconfirmed]")

    # ---------- internal ----------

    def process(self):
        words = self.transcribe_buffer()
        if words is None:
            return

        words = self.drop_already_committed(words)

        old = [word[3] for word in self.previous_words]
        new = [word[3] for word in words]
        n = common_prefix_length(old, new)

        if n > 0:
            self.commit(words[:n])

        self.previous_words = words[n:]

        self.trim_buffer()

    def transcribe_buffer(self):
        try:
            segments, _ = self.model.transcribe(
                self.buffer,
                language=self.language,
                initial_prompt=self.current_prompt(),
                beam_size=5,
                word_timestamps=True,
                condition_on_previous_text=True,
                vad_filter=True,
            )
            segments = list(segments)

        except IndexError:
            return None

        words = []
        for segment in segments:
            if segment.no_speech_prob > NO_SPEECH_THRESHOLD:
                continue

            if segment.words is None:
                continue

            if is_hallucination(segment.text):
                continue

            for word in segment.words:
                start = word.start + self.buffer_offset
                end = word.end + self.buffer_offset
                words.append((start, end, word.word, normalize(word.word)))

        return words

    def current_prompt(self):
        recent = self.committed_text[-PROMPT_WORDS:]
        recent = self.committed_text[-PROMPT_WORDS:]

        has_punctuation = any(is_sentence_end(word[2], self.language) for word in recent)
        if has_punctuation:
            context = "".join(word[2] for word in recent).strip()
        else:
            context = ""

        parts = []
        if self.prompt:
            parts.append(self.prompt)

        if context:
            parts.append(context)

        if parts:
            return " ".join(parts)
        else:
            return None

    def drop_already_committed(self, words):
        # Adapted from HypothesisBuffer.insert in whisper_streaming
        # (Macháček et al., 2023, MIT License): https://github.com/ufal/whisper_streaming
        words = [word for word in words if word[0] > self.committed_until - 0.1]

        if not words:
            return words

        if not self.committed_text:
            return words

        if abs(words[0][0] - self.committed_until) >= 1:
            return words

        max_k = min(5, len(self.committed_text), len(words))
        for k in range(1, max_k + 1):
            old = [word[3] for word in self.committed_text[-k:]]
            new = [word[3] for word in words[:k]]

            if old == new:
                words = words[k:]
                break

        return words

    def commit(self, words):
        self.committed_text.extend(words)
        self.committed_until = words[-1][1]
        self.write_words(words)

    def write_words(self, words):
        for word in words:
            self.current_line.append(word)

            if is_sentence_end(word[2], self.language):
                self.write_line()
            elif len(self.current_line) >= MAX_LINE_WORDS:
                self.write_line()

    def write_line(self, marker=""):
        if not self.current_line:
            return

        start = self.current_line[0][0]
        end = self.current_line[-1][1]
        text = "".join(word[2] for word in self.current_line).strip()
        line = f"[{convert_seconds(start)} -> {convert_seconds(end)}] {text}{marker}"

        self.f.write(line + "\n")
        self.f.flush()

        if not self.quiet:
            print(line)

        self.current_line = []

    def trim_buffer(self):
        buffer_seconds = len(self.buffer) / WHISPER_RATE
        if buffer_seconds < TRIM_SECONDS:
            return

        cut_time = None
        for word in reversed(self.committed_text):
            if word[0] < self.buffer_offset:
                break
            if is_sentence_end(word[2], self.language):
                cut_time = word[1]
                break

        if cut_time is None and buffer_seconds > MAX_BUFFER_SECONDS:
            cut_time = self.committed_until

        if cut_time is None:
            return

        cut = int((cut_time - self.buffer_offset) * WHISPER_RATE)
        self.buffer = self.buffer[cut:]
        self.buffer_offset = cut_time


