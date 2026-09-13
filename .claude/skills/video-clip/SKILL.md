---
name: video-clip
description: Cut highlight clips ("切り抜き動画") out of a long video or YouTube URL using this repo's transcribe.py and clip.py. Use this skill whenever someone wants to clip, trim, excerpt, or pull highlights out of a video, make Shorts/Reels/TikTok cuts from a longer recording, find the good parts of a stream or talk, or asks for a 切り抜き — even if they only paste a video URL and say "make clips from this" without naming the tools. Also use it when someone asks where the interesting moments in a video are, or wants a timestamped transcript to pick clip points from.
---

# Making clip videos

The whole job is picking the right moments. Cutting is mechanical once you know
the timestamps, so the mistake to avoid is jumping straight to `clip.py` with
guessed times. Downloading and re-encoding are the slow steps — guessing wastes
them and produces clips that start mid-sentence.

Find the moments first, then cut once.

## Step 1: Check for chapters

Chapters are free clip boundaries when the uploader made them:

```bash
python clip.py "<URL>" --list-chapters
```

Chapters are coarse — a 12-minute chapter is not a clip. Treat them as a map of
where to look, not as the ranges themselves. Many videos have none; that is
fine, go to step 2.

## Step 2: Transcribe

A timestamped transcript lets you read a 40-minute video in a minute instead of
watching it:

```bash
python transcribe.py "<URL>" -o transcript.txt
```

This pulls the video's own captions when they exist (fast, no model download)
and falls back to local speech recognition when they do not. Useful flags:

- `-l ja` / `-l en` — preferred language
- `-w 0` — one line per caption instead of ~15-second blocks, when you need
  tighter timestamps for a specific passage
- `-e whisper` — force local transcription when the auto-captions are too
  garbled to read

Local transcription needs `pip install faster-whisper`. If captions are absent
and faster-whisper is not installed, say so rather than guessing timestamps.

## Step 3: Read the transcript and choose ranges

Read it. This is the part that takes judgment and it is the reason the clips
will be good or bad.

What tends to make a clip worth cutting:

- A complete thought — a claim, a punchline, a reveal, a question answered
- A moment that makes sense to someone who has not seen the rest of the video
- Something with a hook in the first few seconds; viewers leave fast

Then set the boundaries:

- **Start a few seconds early.** The transcript timestamp marks where a line
  starts, but the setup usually begins before it. Starting exactly on the
  timestamp clips off the run-up and the clip feels like it begins mid-thought.
- **Do not cut mid-sentence at either end.** Extend to the end of the thought.
- **Let it breathe at the end** — a beat after the last word, not a hard stop.
- **Aim for 30–60 seconds** for Shorts/Reels/TikTok; up to a few minutes for a
  standalone clip. If a moment needs five minutes of context, it is not a clip.

When the user has not said which moments they want, propose the ranges with a
one-line reason for each and let them confirm before you spend time cutting.
Do not silently pick for them.

## Step 4: Cut

```bash
python clip.py "<URL>" -c 3:05-3:48 -c 7:35-8:10 -o clips
```

Pass every range in one command. The source is downloaded once and all ranges
are cut from that same file, so ten clips cost one download.

Ranges accept `START-END` or `START+DURATION` (`-c 5:00+45`). Timestamps accept
`83`, `1:23`, or `1:02:03`.

For vertical platforms:

```bash
python clip.py "<URL>" -c 3:05-3:48 --vertical blur --caption "the good part" -o clips
```

- `--vertical crop` zooms in and centre-crops. Good when the subject is centred;
  it will cut off anything at the edges of the frame.
- `--vertical blur` fits the whole frame over a blurred background. Safer when
  the framing matters — nothing is lost — but the subject ends up smaller.
- `--caption` burns text across the bottom. Keep it short; it is a hook, not a
  summary.
- `--copy` skips re-encoding and is much faster, but cuts snap to the nearest
  keyframe, so clips can run seconds longer than asked. Use it only for rough
  drafts, and never with `--vertical` or `--caption` (those need re-encoding).

## Iterating

If the user will want to adjust ranges, download once and work locally — this
avoids re-downloading on every attempt:

```bash
python download.py "<URL>" -o ./downloads
python transcribe.py ./downloads/video.mp4 -o transcript.txt
python clip.py ./downloads/video.mp4 -c 3:05-3:48 -o clips
```

Every command takes a local path wherever it takes a URL.

## Requirements

`ffmpeg` must be on the `PATH`, and `pip install -r requirements.txt` covers
yt-dlp. If a download fails with a proxy or network error, report the blocked
host rather than retrying around it — sandboxed environments often block
youtube.com outright, in which case the user needs to run these commands on
their own machine.

## Rights

Clips are derivative works. Many creators explicitly allow clip channels under
stated conditions and some prohibit them. If the user is going to publish, it is
worth a reminder to check the channel's policy — once, not as a lecture on every
clip.
