# download

A simple command-line tool for downloading videos (or audio) from YouTube and other
[yt-dlp](https://github.com/yt-dlp/yt-dlp)-supported sites.

## Setup

```bash
pip install -r requirements.txt
```

`ffmpeg` must also be installed on your system to merge separate audio/video
streams or extract audio.

## Usage

```bash
python download.py <URL>
```

Options:

- `-o, --output-dir DIR` — directory to save the downloaded file (default: current directory)
- `-a, --audio-only` — extract audio only and save as mp3

### Example

```bash
python download.py "https://www.youtube.com/watch?v=fSumcZ_YWzg" -o ./downloads
```

## Note

Only download content you have the right to download (your own videos, content
under a permissive license, or content you have explicit permission to use).
Downloading copyrighted material without authorization may violate YouTube's
Terms of Service and applicable copyright law.
