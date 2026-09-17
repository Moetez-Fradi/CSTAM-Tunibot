#!/usr/bin/env bash
set -euo pipefail
MF="app/src/main/AndroidManifest.xml"
TMP="$(mktemp)"

# أدخل سطر MapActivity قبل وسم </application>
awk '
  /<\/application>/ && !done {
    print "        <activity android:name=\".MapActivity\""
    print "            android:exported=\"true\""
    print "            android:label=\"@string/map_view\""
    print "            android:theme=\"@style/Theme.DeliveryBot\" />"
    done=1
  }
  { print }
' "$MF" > "$TMP" && mv "$TMP" "$MF"

echo "[OK] Injected MapActivity into AndroidManifest.xml"
