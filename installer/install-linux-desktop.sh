#!/bin/sh
set -eu
notify() {
  if command -v zenity >/dev/null 2>&1; then zenity --info --title="ShopPOS" --text="$1"; else printf '%s\n' "$1"; fi
}
fail() {
  if command -v zenity >/dev/null 2>&1; then zenity --error --title="ShopPOS installer" --text="$1"; else printf '%s\n' "$1" >&2; fi
  exit 1
}
app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app="$app_dir/../ShopPOS/ShopPOS"
if [ ! -x "$app" ]; then fail "ShopPOS executable was not found. Build the release first; installer and ShopPOS folders must be together inside dist/."; fi
desktop_dir=""
if command -v xdg-user-dir >/dev/null 2>&1; then desktop_dir=$(xdg-user-dir DESKTOP 2>/dev/null || true); fi
if [ -z "$desktop_dir" ] || [ "$desktop_dir" = "$HOME" ]; then desktop_dir="${XDG_DESKTOP_DIR:-$HOME/Desktop}"; fi
mkdir -p "$desktop_dir"
launcher="$desktop_dir/ShopPOS.desktop"
printf '%s\n' '[Desktop Entry]' 'Version=1.0' 'Type=Application' 'Name=ShopPOS' "Exec=\"$app\"" "TryExec=$app" "Path=$(dirname "$app")" 'Terminal=false' 'Categories=Office;' > "$launcher"
chmod +x "$launcher"
if command -v gio >/dev/null 2>&1; then gio set "$launcher" metadata::trusted true 2>/dev/null || true; fi
notify "ShopPOS is installed. A ShopPOS icon is now on your desktop. The application will open now; next time, just double-click that icon."
"$app" &
