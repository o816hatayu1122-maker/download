#!/usr/bin/env python3
"""Download videos from YouTube (and other yt-dlp-supported sites)."""

import argparse
import sys

from yt_dlp import YoutubeDL


def download(url: str, output_dir: str, audio_only: bool) -> None:
    ydl_opts = {
        "outtmpl": f"{output_dir}/%(title)s.%(ext)s",
        "format": "bestaudio/best" if audio_only else "bestvideo+bestaudio/best",
        "merge_output_format": "mp4" if not audio_only else None,
        "noplaylist": True,
    }
    if audio_only:
        ydl_opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3"}
        ]

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="Video URL to download")
    parser.add_argument(
        "-o", "--output-dir", default=".", help="Directory to save the file (default: current directory)"
    )
    parser.add_argument(
        "-a", "--audio-only", action="store_true", help="Extract audio only (mp3)"
    )
    args = parser.parse_args()

    try:
        download(args.url, args.output_dir, args.audio_only)
    except Exception as exc:  # yt-dlp raises DownloadError and others
        print(f"Download failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
