#!/usr/bin/env python3
"""Cut highlight clips out of a video (URL or local file) with ffmpeg."""

import argparse
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

from yt_dlp import YoutubeDL

VERTICAL_SIZE = (1080, 1920)


def parse_time(value: str) -> float:
    """Parse "83", "1:23", "1:02:03" or "1:23.5" into seconds."""
    parts = value.strip().split(":")
    if len(parts) > 3:
        raise ValueError(f"Invalid timestamp: {value}")
    try:
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
    except ValueError:
        raise ValueError(f"Invalid timestamp: {value}") from None
    if seconds < 0:
        raise ValueError(f"Timestamp cannot be negative: {value}")
    return seconds


def parse_range(value: str) -> tuple[float, float]:
    """Parse "START-END" or "START+DURATION" into (start, end) in seconds."""
    if "+" in value:
        start_text, _, length_text = value.partition("+")
        start = parse_time(start_text)
        end = start + parse_time(length_text)
    else:
        # Split on the last "-" that separates two timestamps, so that
        # "1:23-2:10" works without tripping over negative-looking input.
        match = re.fullmatch(r"(.+?)\s*-\s*(.+)", value)
        if not match:
            raise ValueError(
                f"Invalid range: {value} (expected START-END or START+DURATION)"
            )
        start = parse_time(match.group(1))
        end = parse_time(match.group(2))
    if end <= start:
        raise ValueError(f"Range end must be after start: {value}")
    return start, end


def is_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise RuntimeError(
                f"{tool} not found. Install ffmpeg and make sure it is on your PATH."
            )


def fetch_source(url: str, work_dir: str) -> str:
    """Download the full video once so every clip is cut from the same file."""
    ydl_opts = {
        "outtmpl": os.path.join(work_dir, "source.%(ext)s"),
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "noplaylist": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info, outtmpl=os.path.join(work_dir, "source.mp4"))


def probe_chapters(source: str) -> list[dict]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_chapters", source],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout).get("chapters", [])


def format_timestamp(seconds: float) -> str:
    total = int(seconds)
    return f"{total // 3600:02d}:{total % 3600 // 60:02d}:{total % 60:02d}"


def list_chapters(target: str) -> None:
    """Print chapter markers, which make natural clip boundaries."""
    if is_url(target):
        with YoutubeDL({"noplaylist": True, "quiet": True}) as ydl:
            info = ydl.extract_info(target, download=False)
        chapters = [
            {"title": c.get("title", ""), "start": c["start_time"], "end": c["end_time"]}
            for c in (info.get("chapters") or [])
        ]
    else:
        chapters = [
            {
                "title": c.get("tags", {}).get("title", ""),
                "start": float(c["start_time"]),
                "end": float(c["end_time"]),
            }
            for c in probe_chapters(target)
        ]

    if not chapters:
        print("No chapters found. Pick clip ranges manually with -c START-END.")
        return

    for index, chapter in enumerate(chapters, start=1):
        span = f"{format_timestamp(chapter['start'])}-{format_timestamp(chapter['end'])}"
        print(f"{index:2d}. {span}  {chapter['title']}")


def find_font(text: str) -> str | None:
    """Pick a font that actually has glyphs for `text`.

    Asking fontconfig for plain "sans" hands back a Latin font, which renders
    Japanese captions as a row of empty boxes without any error. Matching on
    the caption's own codepoints picks a font that can draw them.
    """
    codepoints = {ord(char) for char in text if not char.isspace() and ord(char) > 32}
    queries = []
    if codepoints:
        charset = " ".join(f"{point:04x}" for point in sorted(codepoints))
        queries.append(f":charset={charset}")
    queries.append("sans")

    for query in queries:
        try:
            result = subprocess.run(
                ["fc-match", "-f", "%{file}", query],
                capture_output=True,
                text=True,
                check=True,
            )
        except (OSError, subprocess.CalledProcessError):
            continue
        if result.stdout.strip():
            return result.stdout.strip()

    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "C:/Windows/Fonts/arial.ttf",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def escape_filter_path(path: str) -> str:
    """Quote a path for use as an ffmpeg filter option value."""
    # ffmpeg accepts forward slashes on every platform, which sidesteps
    # backslash escaping; the drive-letter colon still needs escaping.
    return path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


def build_filter(vertical: str | None, caption_file: str | None, font: str | None) -> str | None:
    """Assemble the ffmpeg filter chain for framing and caption burn-in."""
    steps: list[str] = []

    if vertical == "crop":
        width, height = VERTICAL_SIZE
        steps.append(
            f"scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height}"
        )
    elif vertical == "blur":
        width, height = VERTICAL_SIZE
        steps.append(
            f"split=2[bg][fg];"
            f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
            f"crop={width}:{height},gblur=sigma=25[bgblur];"
            f"[fg]scale={width}:-2[fgscaled];"
            f"[bgblur][fgscaled]overlay=(W-w)/2:(H-h)/2"
        )

    if caption_file and font:
        font_size = 64 if vertical else 48
        # textfile= plus expansion=none keeps arbitrary caption text (quotes,
        # colons, percent signs) out of the filter-string escaping rules.
        steps.append(
            f"drawtext=fontfile='{escape_filter_path(font)}':"
            f"textfile='{escape_filter_path(caption_file)}':expansion=none:"
            f"fontcolor=white:fontsize={font_size}:borderw=4:bordercolor=black@0.8:"
            f"x=(w-text_w)/2:y=h-text_h-80"
        )

    return ",".join(steps) if steps else None


def cut_clip(
    source: str,
    start: float,
    end: float,
    output: str,
    vertical: str | None,
    caption: str | None,
    copy_streams: bool,
) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-i",
        source,
        "-t",
        f"{end - start:.3f}",
    ]

    with contextlib.ExitStack() as stack:
        video_filter = None
        if not copy_streams:
            caption_file = None
            font = None
            if caption:
                font = find_font(caption)
                if font is None:
                    print(
                        "Warning: no usable font found, skipping the caption.",
                        file=sys.stderr,
                    )
                else:
                    handle = stack.enter_context(
                        tempfile.NamedTemporaryFile(
                            "w", suffix=".txt", encoding="utf-8"
                        )
                    )
                    handle.write(caption)
                    handle.flush()
                    caption_file = handle.name
            video_filter = build_filter(vertical, caption_file, font)

        if copy_streams:
            command += ["-c", "copy", "-avoid_negative_ts", "make_zero"]
        else:
            if video_filter:
                command += ["-vf", video_filter]
            command += [
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "20",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
            ]

        command += ["-movflags", "+faststart", output]

        result = subprocess.run(command, capture_output=True, text=True)

    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg failed for {output}:\n{tail}")


def concat_segments(segment_files: list[str], output: str) -> None:
    """Join already-cut segments. They share an encode, so a copy is enough."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".txt", encoding="utf-8", delete=False
    ) as handle:
        for path in segment_files:
            escaped = os.path.abspath(path).replace("'", r"'\''")
            handle.write(f"file '{escaped}'\n")
        list_file = handle.name

    try:
        result = subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                list_file,
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                output,
            ],
            capture_output=True,
            text=True,
        )
    finally:
        os.unlink(list_file)

    if result.returncode != 0:
        tail = "\n".join(result.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg failed to join segments into {output}:\n{tail}")


def render_joined(
    source: str,
    segments: list[tuple[float, float]],
    output: str,
    vertical: str | None,
    captions: list[str | None],
    work_dir: str,
) -> None:
    """Cut each segment, then join them into one clip."""
    segment_files = []
    for index, (start, end) in enumerate(segments):
        part = os.path.join(work_dir, f"part_{index:03d}.mp4")
        print(
            f"  segment {index + 1}/{len(segments)}: "
            f"{format_timestamp(start)}-{format_timestamp(end)}"
        )
        # Segments all come from one source through one filter chain, so they
        # end up with matching codecs and dimensions and can be joined losslessly.
        cut_clip(source, start, end, part, vertical, captions[index], False)
        segment_files.append(part)

    concat_segments(segment_files, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Video URL or path to a local video file")
    parser.add_argument(
        "-c",
        "--clip",
        action="append",
        default=[],
        metavar="RANGE",
        help="Clip range as START-END or START+DURATION (repeatable), "
        "e.g. -c 1:23-2:10 -c 5:00+45",
    )
    parser.add_argument(
        "-o", "--output-dir", default="clips", help="Where to write clips (default: clips)"
    )
    parser.add_argument(
        "-p", "--prefix", default="clip", help="Output filename prefix (default: clip)"
    )
    parser.add_argument(
        "-s",
        "--style",
        choices=["plain", "digest", "hook"],
        default="plain",
        help="plain: one file per range. digest: join every range into a single "
        "clip. hook: lead with --hook, then play the range in full "
        "(default: plain)",
    )
    parser.add_argument(
        "--hook",
        metavar="RANGE",
        help="The few seconds to lead with, for --style hook. Pick the most "
        "arresting moment; it decides whether anyone watches the rest",
    )
    parser.add_argument(
        "--vertical",
        choices=["crop", "blur", "both"],
        help="Reframe to 1080x1920 for Shorts/Reels: 'crop' zooms and centre-crops, "
        "'blur' fits the video over a blurred background, 'both' writes each so "
        "you can compare",
    )
    parser.add_argument(
        "--caption", help="Burn a caption across the bottom of the clip"
    )
    parser.add_argument(
        "--caption-scope",
        choices=["hook", "all"],
        help="Where the caption appears. Defaults to 'hook' for --style hook "
        "(a caption over the whole clip reads as a subtitle, not a hook) and "
        "'all' otherwise",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copy streams instead of re-encoding (much faster, but cuts snap to "
        "keyframes and no reframing or caption is possible)",
    )
    parser.add_argument(
        "--list-chapters",
        action="store_true",
        help="Print the video's chapter markers and exit",
    )
    parser.add_argument(
        "--keep-source",
        metavar="DIR",
        help="Keep the downloaded source video in DIR instead of a temp directory",
    )
    args = parser.parse_args()

    try:
        require_ffmpeg()

        if args.list_chapters:
            list_chapters(args.source)
            return

        if not args.clip:
            parser.error("at least one -c/--clip range is required")
        if args.copy and (args.vertical or args.caption):
            parser.error(
                "--copy cannot be combined with --vertical or --caption; "
                "those need re-encoding"
            )
        if args.copy and args.style != "plain":
            parser.error(
                "--copy only applies to --style plain; joining segments needs "
                "a consistent re-encode"
            )
        if args.style == "hook" and not args.hook:
            parser.error(
                "--style hook needs --hook RANGE: the moment to lead with. "
                "Read the transcript and pick the line that earns the watch"
            )
        if args.hook and args.style != "hook":
            parser.error("--hook only applies to --style hook")

        ranges = [parse_range(value) for value in args.clip]
        hook_range = parse_range(args.hook) if args.hook else None

        caption_scope = args.caption_scope or (
            "hook" if args.style == "hook" else "all"
        )
        if args.caption_scope == "hook" and args.style != "hook":
            parser.error("--caption-scope hook only applies to --style hook")

        work_dir = args.keep_source
        temp_dir = None
        if is_url(args.source):
            if work_dir:
                os.makedirs(work_dir, exist_ok=True)
            else:
                temp_dir = tempfile.mkdtemp(prefix="clip-")
                work_dir = temp_dir
            print(f"Downloading source video from {args.source}")
            source = fetch_source(args.source, work_dir)
        else:
            source = args.source
            if not os.path.exists(source):
                raise RuntimeError(f"No such file: {source}")

        try:
            os.makedirs(args.output_dir, exist_ok=True)
            variants = (
                ["crop", "blur"] if args.vertical == "both" else [args.vertical]
            )
            written = 0

            for variant in variants:
                suffix = f"_{variant}" if args.vertical == "both" else ""

                if args.style == "plain":
                    for index, (start, end) in enumerate(ranges, start=1):
                        output = os.path.join(
                            args.output_dir,
                            f"{args.prefix}_{index:02d}{suffix}.mp4",
                        )
                        print(
                            f"Cutting {format_timestamp(start)}-"
                            f"{format_timestamp(end)} -> {output}"
                        )
                        cut_clip(
                            source, start, end, output, variant, args.caption, args.copy
                        )
                        written += 1
                    continue

                if args.style == "digest":
                    segments = ranges
                    # A caption pinned across a digest belongs to no single
                    # moment, so it stays on every segment or none.
                    captions = [args.caption] * len(segments)
                    name = "digest"
                else:
                    segments = [hook_range] + ranges
                    captions = [args.caption] + [
                        args.caption if caption_scope == "all" else None
                    ] * len(ranges)
                    name = "hook"

                output = os.path.join(
                    args.output_dir, f"{args.prefix}_{name}{suffix}.mp4"
                )
                print(f"Building {name} -> {output}")
                with tempfile.TemporaryDirectory(prefix="clip-parts-") as parts_dir:
                    render_joined(
                        source, segments, output, variant, captions, parts_dir
                    )
                written += 1

            print(f"Done. {written} clip(s) written to {args.output_dir}")
        finally:
            if temp_dir:
                shutil.rmtree(temp_dir, ignore_errors=True)
    except (RuntimeError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # yt-dlp raises DownloadError and others
        print(f"Failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
