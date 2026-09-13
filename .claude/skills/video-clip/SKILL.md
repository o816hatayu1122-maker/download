---
name: video-clip
description: Make clip videos ("切り抜き動画") from a long video or YouTube URL — hook-first, digest, or plain cuts — using the vclip command (transcribe.py / clip.py). Use this skill whenever someone wants to clip, trim, excerpt, or pull highlights out of a video, make Shorts/Reels/TikTok cuts from a longer recording, build a digest of the good parts, find where the interesting moments are, or asks for a 切り抜き or ダイジェスト — even if they only paste a video URL and say "make clips from this" without naming any tool. Also use it when someone wants a timestamped transcript to pick clip points from.
---

# Making clip videos

Two things decide whether a clip is good, and neither is the cutting: knowing
what the user actually wants, and finding the right moment. Cutting is
mechanical once those are settled.

So the order is: **interview, then find the moments, then cut.** Skipping
ahead produces clips that are technically fine and useless — the wrong format,
the wrong length, starting mid-sentence.

## Step 0: Interview the user first

Do this before touching the video. Downloading and re-encoding are the slow
steps, and every wrong assumption costs a full round trip. Ask, and wait for
answers:

- **Style** — hook-first, digest, or a plain cut? (See the styles below. If
  they are unsure, describe the three in a line each rather than picking for
  them.)
- **Platform and length** — vertical Shorts/Reels/TikTok at 30–60s? Longer
  vertical for talking-head material? Horizontal 1–3 minutes? Full length?
- **Framing**, if vertical — blurred-background fit (nothing is lost, subject
  is smaller) or centre-crop zoom (more impact, edges are cut)? Offering both
  and comparing is cheap and often the right answer.
- **Captions** — a short burned-in hook line, none, or captions throughout?
- **Which moments**, if they already have some in mind. Often they do, and it
  saves the transcript pass.

Ask these as actual questions, in one batch. Do not present a plan built on
guesses and ask them to approve it — they cannot see what you assumed.

## The three styles

**Hook-first** (`--style hook`) leads with the most arresting few seconds, then
plays the segment in full. The lead-in is what stops the scroll, so it earns
its keep on Shorts and Reels. It needs two ranges: the hook and the body.

```bash
vclip clip "<URL>" --style hook --hook 12:40-12:48 -c 12:10-13:05 \
  --vertical blur --caption "この一言で空気が変わった" -o clips
```

The caption lands on the hook only by default. A caption held across the whole
clip stops reading as a hook and starts reading as a subtitle.

**Digest** (`--style digest`) joins several ranges into one clip — the shape
for "the good parts of a 2-hour stream". Order the ranges so it builds; put
the strongest moment first if the platform punishes slow starts.

```bash
vclip clip "<URL>" --style digest -c 4:10-4:38 -c 18:02-18:44 -c 51:20-51:58 -o clips
```

**Plain** (`--style plain`, the default) writes each range as its own file. Use
it when the moments stand alone, or to draft candidates before deciding what
goes into a digest.

```bash
vclip clip "<URL>" -c 3:05-3:48 -c 7:35+45 -o clips
```

## Step 1: Look for chapters

Chapters are free clip boundaries when the uploader made them:

```bash
vclip chapters "<URL>"
```

They are coarse — a 12-minute chapter is not a clip. Treat them as a map of
where to look. Many videos have none; that is fine.

## Step 2: Transcribe

A timestamped transcript lets you read a 40-minute video in a minute instead of
watching it:

```bash
vclip transcribe "<URL>" -o transcript.txt -l ja
```

This uses the video's own captions when they exist (fast, no model download)
and falls back to local speech recognition when they do not. Useful flags:

- `-w 0` — one line per caption instead of ~15-second blocks, when you need
  tighter timestamps for a passage you have already located
- `-e whisper` — force local transcription when auto-captions are too garbled

Local transcription needs `pip install faster-whisper`. If there are no
captions and it is not installed, say so — do not fall back to guessing.

## Step 3: Choose the ranges

Read the transcript. This is the part that takes judgment.

What tends to be worth clipping: a complete thought — a claim, a punchline, a
reveal, a question finally answered — that makes sense to someone who has not
seen the rest of the video.

Setting the boundaries:

- **Start a few seconds early.** The transcript timestamp marks where a line
  starts, but the setup begins before it. Cutting exactly on the timestamp
  loses the run-up and the clip opens mid-thought.
- **Do not cut mid-sentence** at either end; extend to the end of the thought.
- **Let it breathe** — a beat after the last word, not a hard stop.
- **30–60 seconds** for Shorts/Reels/TikTok. If a moment needs five minutes of
  setup, it is not a clip.
- **For hook-first, the hook is a different decision from the body.** Look for
  the sharpest 3–8 seconds *inside* the segment — the line someone would quote.
  A hook that merely starts the story is not a hook.

Propose the ranges with a one-line reason each and get confirmation before
cutting. Do not silently pick for the user.

## Step 4: Cut

Pass every range in one command. The source is downloaded once and all ranges
are cut from it, so ten clips cost one download.

Options worth knowing:

- `--vertical crop|blur|both` — reframe to 1080x1920. `both` writes each so the
  user can compare; that is usually worth the extra encode on a first pass.
- `--caption TEXT` — burned-in text. Short. It is a hook, not a summary.
- `--caption-scope hook|all` — defaults to `hook` for hook-first, `all` otherwise.
- `--copy` — skips re-encoding, much faster, but cuts snap to keyframes so
  clips run long. Draft use only; it cannot be combined with reframing,
  captions, or the joined styles.
- `-p PREFIX` — output filename prefix, worth setting when producing several
  variants into one directory.

## Iterating

If the ranges will need adjusting, download once and work from the local file
so you are not re-downloading each attempt:

```bash
vclip download "<URL>" -o ./downloads
vclip transcribe ./downloads/video.mp4 -o transcript.txt
vclip clip ./downloads/video.mp4 --style hook --hook 12:40-12:48 -c 12:10-13:05 -o clips
```

Every command takes a local path wherever it takes a URL.

## Requirements

`ffmpeg` must be on the `PATH`. If `vclip` is not installed, the scripts run
directly (`python3 clip.py ...`) from the repo.

If a download fails with a proxy or network error, report the blocked host
rather than retrying around it — sandboxed environments often block
youtube.com outright, and the user then needs to run the command on their own
machine.

## Rights

Clips are derivative works. Many creators explicitly allow clip channels under
stated conditions and some prohibit them. If the user is going to publish, a
single reminder to check the channel's policy is worth it — once, not as a
lecture on every clip.
