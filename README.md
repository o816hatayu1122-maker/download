# download

Command-line tools for downloading videos (or audio) from YouTube and other
[yt-dlp](https://github.com/yt-dlp/yt-dlp)-supported sites, and for cutting
highlight clips out of them.

- `transcribe.py` — build a timestamped transcript so you can find the moments worth clipping
- `clip.py` — cut those moments into clips, optionally reframed vertically with a burned-in caption
- `download.py` — download a whole video or its audio

## Setup

```bash
pip install -r requirements.txt
```

`ffmpeg` must also be installed on your system and on your `PATH`. It merges
separate audio/video streams, extracts audio, and does all the cutting.

Local speech recognition is optional and only needed for videos without
captions:

```bash
pip install faster-whisper
```

## The clipping workflow

Find the moments *first*, then cut. Guessing timestamps and cutting blind
wastes the slow step (downloading and re-encoding), so start by reading the
video rather than watching it end to end.

### 1. Look for chapter markers

Chapters are the cheapest source of clip boundaries, when the video has them:

```bash
python clip.py "<URL>" --list-chapters
```

### 2. Transcribe to find the actual moments

Chapters are coarse and many videos have none. A timestamped transcript lets
you scan the whole video in a minute and spot where something quotable
happens:

```bash
python transcribe.py "<URL>" -o transcript.txt
```

This uses the video's own captions when they exist (fast, no model download),
and falls back to local speech recognition when they do not. Output looks
like:

```
[00:00:01] intro and today's topic
[00:03:12] the part actually worth clipping
[00:07:40] closing summary
```

Options:

- `-o, --output FILE` — write the transcript to a file (default: stdout)
- `-l, --lang CODE` — preferred language, e.g. `ja` or `en`
- `-e, --engine {auto,subs,whisper}` — `auto` prefers captions and falls back to
  local transcription; `subs` refuses to fall back; `whisper` always transcribes locally
- `--model SIZE` — faster-whisper model size (default: `small`)
- `-w, --window SECONDS` — group the transcript into blocks of about this many
  seconds; `0` keeps every caption line (default: `15`)

### 3. Read the transcript and pick your ranges

Scan for the timestamps where something lands, then note them as ranges. Give
each clip a little runway — start a few seconds before the line you want so it
has context, and let it breathe at the end.

### 4. Cut the clips

```bash
python clip.py "<URL>" -c 3:05-3:48 -c 7:35-8:10 -o clips
```

The source video is downloaded once and every range is cut from that same
file, so asking for several clips costs one download.

Options:

- `-c, --clip RANGE` — repeatable; `START-END` or `START+DURATION`
  (`-c 1:23-2:10`, `-c 5:00+45`). Timestamps accept `83`, `1:23`, or `1:02:03`
- `-o, --output-dir DIR` — where to write clips (default: `clips`)
- `-p, --prefix NAME` — output filename prefix (default: `clip`)
- `--vertical {crop,blur}` — reframe to 1080x1920 for Shorts/Reels. `crop`
  zooms in and centre-crops; `blur` fits the whole frame over a blurred
  background
- `--caption TEXT` — burn a caption across the bottom of every clip
- `--copy` — copy streams instead of re-encoding. Much faster, but cuts snap to
  the nearest keyframe (so clips can run seconds long) and no reframing or
  caption is possible
- `--keep-source DIR` — keep the downloaded source video instead of discarding it
- `--list-chapters` — print chapter markers and exit

### Example: a vertical clip for Shorts

```bash
python clip.py "<URL>" -c 3:05-3:48 --vertical blur --caption "the good part" -o clips
```

### Working from a local file

Every command takes a local path in place of a URL, which is worth doing if
you are going to iterate on the ranges:

```bash
python download.py "<URL>" -o ./downloads
python transcribe.py ./downloads/video.mp4 -o transcript.txt
python clip.py ./downloads/video.mp4 -c 3:05-3:48 -o clips
```

## download.py

```bash
python download.py <URL>
```

Options:

- `-o, --output-dir DIR` — directory to save the downloaded file (default: current directory)
- `-a, --audio-only` — extract audio only and save as mp3

## Note

Only download content you have the right to download (your own videos, content
under a permissive license, or content you have explicit permission to use).
Downloading copyrighted material without authorization may violate YouTube's
Terms of Service and applicable copyright law. Clip videos are derivative
works: many creators allow them under stated conditions and others do not, so
check the channel's policy before publishing anything you cut.
