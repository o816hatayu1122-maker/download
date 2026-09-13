#!/usr/bin/env bash
# Install the clip workflow globally:
#   - the `vclip` command onto your PATH
#   - the video-clip skill into ~/.claude/skills/
#   - the /clip slash command into ~/.claude/commands/
#
# Usage: ./install.sh [--bin-dir DIR] [--claude-dir DIR]

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
CLAUDE_DIR="${HOME}/.claude"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --bin-dir) BIN_DIR="$2"; shift 2 ;;
        --claude-dir) CLAUDE_DIR="$2"; shift 2 ;;
        -h|--help) sed -n '2,7p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "install.sh: unknown option '$1'" >&2; exit 1 ;;
    esac
done

mkdir -p "$BIN_DIR" "$CLAUDE_DIR/skills" "$CLAUDE_DIR/commands"

# Symlink rather than copy so `git pull` updates the installed command too.
chmod +x "$REPO_DIR/vclip"
ln -sf "$REPO_DIR/vclip" "$BIN_DIR/vclip"
echo "Linked $BIN_DIR/vclip -> $REPO_DIR/vclip"

ln -sfn "$REPO_DIR/.claude/skills/video-clip" "$CLAUDE_DIR/skills/video-clip"
echo "Linked $CLAUDE_DIR/skills/video-clip"

ln -sf "$REPO_DIR/.claude/commands/clip.md" "$CLAUDE_DIR/commands/clip.md"
echo "Linked $CLAUDE_DIR/commands/clip.md"

if ! command -v ffmpeg >/dev/null 2>&1; then
    echo
    echo "Warning: ffmpeg is not on your PATH. Install it before cutting clips:"
    echo "  macOS:  brew install ffmpeg"
    echo "  Ubuntu: sudo apt install ffmpeg"
fi

case ":${PATH}:" in
    *":${BIN_DIR}:"*) ;;
    *)
        echo
        echo "Warning: $BIN_DIR is not on your PATH. Add this to your shell profile:"
        echo "  export PATH=\"\$PATH:$BIN_DIR\""
        ;;
esac

echo
echo "Done. Try: vclip --help"
