#!/usr/bin/env python3
"""Produce a timestamped transcript so you can find clip-worthy moments."""

import argparse
import glob
import html
import os
import re
import shutil
import sys
import tempfile

from yt_dlp import YoutubeDL

# Inline karaoke timing tags YouTube puts inside auto-generated captions,
# e.g. "<00:00:01.000><c>word</c>".
TAG_PATTERN = re.compile(r"<[^>]+>")
CUE_PATTERN = re.compile(
    r"(\d{2}:\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}[.,]\d{3})"
)


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def parse_cue_time(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def parse_vtt(path: str) -> list[tuple[float, str]]:
    """Parse a VTT/SRT file into (start_seconds, text) segments."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        lines = handle.read().splitlines()

    segments: list[tuple[float, str]] = []
    start: float | None = None
    buffer: list[str] = []

    def flush() -> None:
        if start is None:
            return
        text = " ".join(buffer).strip()
        text = html.unescape(TAG_PATTERN.sub("", text)).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            segments.append((start, text))

    for line in lines:
        match = CUE_PATTERN.search(line)
        if match:
            flush()
            start = parse_cue_time(match.group(1))
            buffer = []
        elif start is not None:
            stripped = line.strip()
            if stripped and stripped != "WEBVTT" and not stripped.isdigit():
                buffer.append(stripped)
    flush()

    return dedupe(segments)


def dedupe(segments: list[tuple[float, str]]) -> list[tuple[float, str]]:
    """Drop the rolling repeats YouTube's auto-captions emit."""
    result: list[tuple[float, str]] = []
    for start, text in segments:
        if result:
            previous = result[-1][1]
            if text == previous:
                continue
            # Auto-captions re-send the previous line with a few words added.
            if text.startswith(previous):
                result[-1] = (result[-1][0], text)
                continue
            if previous.endswith(text):
                continue
        result.append((start, text))
    return result


def fetch_subtitles(url: str, languages: list[str], work_dir: str) -> str | None:
    """Download manual subtitles if present, otherwise auto-generated ones."""
    ydl_opts = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": languages,
        "subtitlesformat": "vtt",
        "outtmpl": os.path.join(work_dir, "subs.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    found = sorted(glob.glob(os.path.join(work_dir, "*.vtt")))
    return found[0] if found else None


def transcribe_with_whisper(source: str, language: str | None, model_size: str) -> list[tuple[float, str]]:
    """Fall back to local speech recognition when there are no captions."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "No captions available and faster-whisper is not installed.\n"
            "Install it with: pip install faster-whisper"
        ) from None

    print(f"Transcribing locally with faster-whisper ({model_size})...", file=sys.stderr)
    model = WhisperModel(model_size, compute_type="int8")
    segments, _ = model.transcribe(source, language=language)
    return [(segment.start, segment.text.strip()) for segment in segments if segment.text.strip()]


def fetch_media(url: str, work_dir: str) -> str:
    """Grab audio only — that is all local transcription needs."""
    ydl_opts = {
        "outtmpl": os.path.join(work_dir, "audio.%(ext)s"),
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


def group_segments(
    segments: list[tuple[float, str]], window: float
) -> list[tuple[float, str]]:
    """Merge short segments into readable blocks of roughly `window` seconds."""
    if window <= 0 or not segments:
        return segments

    grouped: list[tuple[float, str]] = []
    block_start = segments[0][0]
    parts: list[str] = []

    for start, text in segments:
        if parts and start - block_start >= window:
            grouped.append((block_start, " ".join(parts)))
            block_start = start
            parts = []
        parts.append(text)

    if parts:
        grouped.append((block_start, " ".join(parts)))
    return grouped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Video URL or path to a local media file")
    parser.add_argument(
        "-o", "--output", help="Write the transcript here (default: print to stdout)"
    )
    parser.add_argument(
        "-l",
        "--lang",
        help="Preferred caption/speech language code, e.g. ja or en",
    )
    parser.add_argument(
        "-e",
        "--engine",
        choices=["auto", "subs", "whisper"],
        default="auto",
        help="auto: use captions if available, else local speech recognition; "
        "subs: captions only; whisper: always transcribe locally (default: auto)",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="faster-whisper model size for local transcription (default: small)",
    )
    parser.add_argument(
        "-w",
        "--window",
        type=float,
        default=15.0,
        help="Group the transcript into blocks of about this many seconds; "
        "0 keeps every caption line (default: 15)",
    )
    args = parser.parse_args()

    temp_dir = tempfile.mkdtemp(prefix="transcribe-")
    try:
        segments: list[tuple[float, str]] = []

        if args.engine in ("auto", "subs"):
            if is_url(args.source):
                languages = [args.lang] if args.lang else ["ja", "en"]
                subtitle_file = fetch_subtitles(args.source, languages, temp_dir)
                if subtitle_file:
                    segments = parse_vtt(subtitle_file)
            elif args.source.lower().endswith((".vtt", ".srt")):
                segments = parse_vtt(args.source)

            if not segments and args.engine == "subs":
                raise RuntimeError(
                    "No captions found. Try --engine whisper to transcribe locally."
                )

        if not segments:
            source = args.source
            if is_url(source):
                print("No captions found; downloading audio...", file=sys.stderr)
                source = fetch_media(source, temp_dir)
            segments = transcribe_with_whisper(source, args.lang, args.model)

        if not segments:
            raise RuntimeError("Transcription produced no text.")

        lines = [
            f"[{format_timestamp(start)}] {text}"
            for start, text in group_segments(segments, args.window)
        ]
        output_text = "\n".join(lines)

        if args.output:
            with open(args.output, "w", encoding="utf-8") as handle:
                handle.write(output_text + "\n")
            print(f"Wrote {len(lines)} lines to {args.output}")
        else:
            print(output_text)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # yt-dlp raises DownloadError and others
        print(f"Failed: {exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
