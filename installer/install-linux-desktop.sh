#!/bin/sh
set -eu
app_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
app="$app_dir/../ShopPOS/ShopPOS"
if [ ! -x "$app" ]; then echo "ShopPOS executable was not found next to this installer." >&2; exit 1; fi
desktop_dir="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
mkdir -p "$desktop_dir"
launcher="$desktop_dir/ShopPOS.desktop"
printf '%s\n' '[Desktop Entry]' 'Version=1.0' 'Type=Application' 'Name=ShopPOS' "Exec=$app" "Path=$(dirname "$app")" 'Terminal=false' 'Categories=Office;' > "$launcher"
chmod +x "$launcher"
echo "Created desktop launcher: $launcher"
