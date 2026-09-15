#!/usr/bin/env bash
# Register the clip workflow on this machine:
#   - a virtualenv with the Python dependencies
#   - the `vclip` command on your PATH
#   - the video-clip skill and /clip slash command in ~/.claude/
#
# Usage: ./install.sh [options]
#   --with-whisper   also install faster-whisper (for videos without captions)
#   --no-venv        install dependencies with your current python instead
#   --no-path        do not touch your shell profile
#   --bin-dir DIR    where to put the command  (default: ~/.local/bin)
#   --claude-dir DIR where to put the skill    (default: ~/.claude)
#   --uninstall      undo everything this script did

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
CLAUDE_DIR="${HOME}/.claude"
VENV_DIR="${REPO_DIR}/.venv"
MARKER_START="# >>> vclip >>>"
MARKER_END="# <<< vclip <<<"

use_venv=1
edit_path=1
with_whisper=0
uninstall=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-whisper) with_whisper=1; shift ;;
        --no-venv) use_venv=0; shift ;;
        --no-path) edit_path=0; shift ;;
        --bin-dir) BIN_DIR="$2"; shift 2 ;;
        --claude-dir) CLAUDE_DIR="$2"; shift 2 ;;
        --uninstall) uninstall=1; shift ;;
        -h|--help) sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "install.sh: unknown option '$1'" >&2; exit 1 ;;
    esac
done

# Pick the file a login shell of this type actually reads.
shell_profile() {
    case "$(basename "${SHELL:-bash}")" in
        zsh) echo "${ZDOTDIR:-$HOME}/.zshrc" ;;
        fish) echo "${HOME}/.config/fish/config.fish" ;;
        *)
            if [[ "$(uname -s)" == "Darwin" && -f "${HOME}/.bash_profile" ]]; then
                echo "${HOME}/.bash_profile"
            else
                echo "${HOME}/.bashrc"
            fi
            ;;
    esac
}

# Rewrite the profile with python so the marked block can be replaced or
# removed cleanly no matter what else the user keeps in there.
strip_block() {
    local profile="$1"
    [[ -f "$profile" ]] || return 0
    python3 - "$profile" "$MARKER_START" "$MARKER_END" <<'PY'
import sys
path, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, encoding="utf-8") as handle:
    lines = handle.read().splitlines(keepends=True)
kept, skipping = [], False
for line in lines:
    if line.strip() == start:
        skipping = True
    elif line.strip() == end:
        skipping = False
    elif not skipping:
        kept.append(line)
with open(path, "w", encoding="utf-8") as handle:
    handle.writelines(kept)
PY
}

if [[ $uninstall -eq 1 ]]; then
    rm -f "$BIN_DIR/vclip"
    rm -f "$CLAUDE_DIR/skills/video-clip" "$CLAUDE_DIR/commands/clip.md"
    strip_block "$(shell_profile)"
    echo "Removed the vclip command, the skill, and the PATH entry."
    echo "The virtualenv at $VENV_DIR was left in place; delete it if you want it gone."
    exit 0
fi

command -v python3 >/dev/null 2>&1 || { echo "python3 is required but not on PATH." >&2; exit 1; }

# --- dependencies -----------------------------------------------------------
if [[ $use_venv -eq 1 ]]; then
    [[ -d "$VENV_DIR" ]] || python3 -m venv "$VENV_DIR"
    PIP="$VENV_DIR/bin/pip"
    "$PIP" install --quiet --upgrade pip
    echo "Installing dependencies into $VENV_DIR"
else
    PIP="python3 -m pip"
    echo "Installing dependencies with your current python"
fi
# PyPI reads time out often enough that a bare failure here is mostly noise.
PIP_FLAGS=(--quiet --retries 5 --timeout 60)
$PIP install "${PIP_FLAGS[@]}" -r "$REPO_DIR/requirements.txt"
if [[ $with_whisper -eq 1 ]]; then
    echo "Installing faster-whisper (this one is large)"
    $PIP install "${PIP_FLAGS[@]}" faster-whisper
fi

# --- the command ------------------------------------------------------------
mkdir -p "$BIN_DIR" "$CLAUDE_DIR/skills" "$CLAUDE_DIR/commands"
chmod +x "$REPO_DIR/vclip"

# Symlink rather than copy so `git pull` updates the installed command too.
ln -sf "$REPO_DIR/vclip" "$BIN_DIR/vclip"
ln -sfn "$REPO_DIR/.claude/skills/video-clip" "$CLAUDE_DIR/skills/video-clip"
ln -sf "$REPO_DIR/.claude/commands/clip.md" "$CLAUDE_DIR/commands/clip.md"
echo "Installed vclip, the video-clip skill, and the /clip command"

# --- PATH -------------------------------------------------------------------
path_already_ok=0
case ":${PATH}:" in *":${BIN_DIR}:"*) path_already_ok=1 ;; esac

profile="$(shell_profile)"
if [[ $path_already_ok -eq 0 && $edit_path -eq 1 ]]; then
    strip_block "$profile"
    mkdir -p "$(dirname "$profile")"
    if [[ "$(basename "${SHELL:-bash}")" == "fish" ]]; then
        printf '%s\nfish_add_path %s\n%s\n' "$MARKER_START" "$BIN_DIR" "$MARKER_END" >> "$profile"
    else
        printf '%s\nexport PATH="$PATH:%s"\n%s\n' "$MARKER_START" "$BIN_DIR" "$MARKER_END" >> "$profile"
    fi
    echo "Added $BIN_DIR to your PATH in $profile"
    echo
    echo "Open a new terminal, or run:  source $profile"
elif [[ $path_already_ok -eq 0 ]]; then
    echo
    echo "Note: $BIN_DIR is not on your PATH. Add this to $profile yourself:"
    echo "  export PATH=\"\$PATH:$BIN_DIR\""
fi

# --- ffmpeg -----------------------------------------------------------------
if ! command -v ffmpeg >/dev/null 2>&1; then
    echo
    echo "ffmpeg is not installed, and nothing can be cut without it:"
    case "$(uname -s)" in
        Darwin) echo "  brew install ffmpeg" ;;
        *) echo "  sudo apt install ffmpeg      # or your distro's package manager" ;;
    esac
fi

echo
echo "Done. Check it with:  vclip --help"
