# download

Command-line tools for downloading videos from YouTube and other
[yt-dlp](https://github.com/yt-dlp/yt-dlp)-supported sites, and for cutting
clip videos (切り抜き) out of them — hook-first, digest, or plain cuts.

- `transcribe.py` — build a timestamped transcript so you can find the moments worth clipping
- `clip.py` — cut those moments into clips, reframed vertically with burned-in captions
- `download.py` — download a whole video or its audio
- `vclip` — one command that wraps all three

## Setup

```bash
pip install -r requirements.txt
```

`ffmpeg` must also be installed and on your `PATH`. It merges separate
audio/video streams, extracts audio, and does all the cutting.

Local speech recognition is optional, and only needed for videos without
captions:

```bash
pip install faster-whisper
```

### Install globally

```bash
./install.sh
```

This puts the `vclip` command on your `PATH` (via `~/.local/bin`), and installs
the Claude Code integration into `~/.claude/`: the `video-clip` skill and the
`/clip` slash command. Everything is symlinked to this repo, so `git pull`
updates the installed copies too.

Options: `--bin-dir DIR` and `--claude-dir DIR` to install elsewhere.

## The clipping workflow

Interview first, then find the moments, then cut. Cutting is the mechanical
part — downloading and re-encoding are slow, so every wrong assumption about
format or length costs a full round trip.

### 0. Decide what you are making

Three questions settle most of it: which style, what platform and length, and
whether it is vertical. The `/clip` slash command asks these before it starts.

### 1. Look for chapter markers

Chapters are the cheapest source of clip boundaries, when the video has them:

```bash
vclip chapters "<URL>"
```

They are coarse — a 12-minute chapter is not a clip — so treat them as a map of
where to look.

### 2. Transcribe to find the actual moments

A timestamped transcript lets you scan a 40-minute video in a minute:

```bash
vclip transcribe "<URL>" -o transcript.txt -l ja
```

This uses the video's own captions when they exist (fast, no model download),
and falls back to local speech recognition when they do not. Output looks like:

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
- `-w, --window SECONDS` — group into blocks of about this many seconds; `0`
  keeps every caption line (default: `15`)

### 3. Read the transcript and pick your ranges

Scan for where something lands, then note the ranges. Start a few seconds
before the line you want so it has its run-up, do not cut mid-sentence, and let
it breathe at the end. Aim for 30–60 seconds for Shorts.

### 4. Cut

Pass every range in one command — the source is downloaded once and all ranges
are cut from it, so ten clips cost one download.

## Clip styles

**Hook-first** — lead with the sharpest few seconds, then play the segment in
full. The lead-in is what stops the scroll.

```bash
vclip clip "<URL>" --style hook --hook 12:40-12:48 -c 12:10-13:05 \
  --vertical blur --caption "この一言で空気が変わった" -o clips
```

The caption lands on the hook only by default — held across the whole clip it
reads as a subtitle rather than a hook.

**Digest** — join several ranges into one clip, for "the good parts of a 2-hour
stream".

```bash
vclip clip "<URL>" --style digest -c 4:10-4:38 -c 18:02-18:44 -c 51:20-51:58 -o clips
```

**Plain** (default) — each range becomes its own file.

```bash
vclip clip "<URL>" -c 3:05-3:48 -c 7:35+45 -o clips
```

### clip options

- `-c, --clip RANGE` — repeatable; `START-END` or `START+DURATION`
  (`-c 1:23-2:10`, `-c 5:00+45`). Timestamps accept `83`, `1:23`, or `1:02:03`
- `-s, --style {plain,digest,hook}` — see above (default: `plain`)
- `--hook RANGE` — the moment to lead with, required by `--style hook`
- `--vertical {crop,blur,both}` — reframe to 1080x1920. `crop` zooms and
  centre-crops (more impact, edges lost); `blur` fits the whole frame over a
  blurred background (nothing lost, subject smaller); `both` writes each so you
  can compare
- `--caption TEXT` — burn text across the bottom. A CJK-capable font is chosen
  automatically when the caption needs one
- `--caption-scope {hook,all}` — defaults to `hook` for `--style hook`, `all` otherwise
- `-o, --output-dir DIR` — where to write clips (default: `clips`)
- `-p, --prefix NAME` — output filename prefix (default: `clip`)
- `--copy` — copy streams instead of re-encoding. Much faster, but cuts snap to
  the nearest keyframe (clips run long) and it cannot be combined with
  reframing, captions, or the joined styles
- `--keep-source DIR` — keep the downloaded source instead of discarding it
- `--list-chapters` — print chapter markers and exit

## Working from a local file

Worth doing if you will iterate on the ranges — it avoids re-downloading:

```bash
vclip download "<URL>" -o ./downloads
vclip transcribe ./downloads/video.mp4 -o transcript.txt
vclip clip ./downloads/video.mp4 --style hook --hook 12:40-12:48 -c 12:10-13:05 -o clips
```

Every command takes a local path wherever it takes a URL.

## Claude Code integration

After `./install.sh`:

- `/clip <URL>` — runs the whole workflow, interviewing you about style,
  length, framing and captions before it cuts anything
- The `video-clip` skill triggers on its own whenever you ask for a 切り抜き,
  a digest, Shorts, or "clips from this video"

## download.py

```bash
vclip download <URL>
```

Options:

- `-o, --output-dir DIR` — directory to save the file (default: current directory)
- `-a, --audio-only` — extract audio only and save as mp3

## Note

Only download content you have the right to download (your own videos, content
under a permissive license, or content you have explicit permission to use).
Downloading copyrighted material without authorization may violate YouTube's
Terms of Service and applicable copyright law. Clip videos are derivative
works: many creators allow them under stated conditions and others do not, so
check the channel's policy before publishing anything you cut.
