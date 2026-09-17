#!/usr/bin/env bash
set -euo pipefail

MF="app/src/main/AndroidManifest.xml"
GR="app/build.gradle"

echo "[backup] AndroidManifest.xml -> ${MF}.bak"
cp "$MF" "${MF}.bak"

# 1) احذف أي تكرارات لـ MapActivity (سواء كانت سطر واحد أو بلوك متعدد الأسطر)
TMP="$(mktemp)"
awk '
  BEGIN{skip=0}
  # بداية بلوك activity لو فيه MapActivity
  /<activity[^>]*MapActivity/ { skip=1 }
  skip==1 {
    # نهاية البلوك: إما self-closing "/>" أو "</activity>"
    if ($0 ~ /\/>/ || $0 ~ /<\/activity>/) { skip=0 }
    next
  }
  { print }
' "$MF" > "$TMP" && mv "$TMP" "$MF"

# 2) أضف تعريف وحيد سطر واحد لـ MapActivity قبل </application>
# لو أصلاً موجود تعريف MapActivity بعد التنضيف، ما نضيفش تاني
if ! grep -q 'activity.*MapActivity' "$MF"; then
  awk '
    /<\/application>/ && !done {
      print "        <activity android:name=\".MapActivity\" android:exported=\"true\" android:label=\"@string/map_view\" android:theme=\"@style/Theme.DeliveryBot\" />"
      done=1
    }
    { print }
  ' "$MF" > "$TMP" && mv "$TMP" "$MF"
  echo "[inject] Added single MapActivity entry"
else
  echo "[skip] MapActivity exists (single) after cleanup"
fi

# 3) شيل الـ package="..." من وسم <manifest> (AGP الجديدة بتحتاج namespace بدل package)
if grep -q '<manifest' "$MF"; then
  sed -E -i 's/(<manifest[^>]*?)\s+package="[^"]*"([^>]*>)/\1\2/' "$MF" || true
  echo "[fix] Removed package=\"...\" from <manifest>"
fi

# 4) ضيف namespace في app/build.gradle لو مش موجود
if ! grep -q 'namespace' "$GR"; then
  # لو فيه android { } حنضيف جواه
  if grep -q 'android\s*{' "$GR"; then
    sed -i '/android\s*{/{n; s/^/    namespace "com.example.deliverybot"\n/; }' "$GR" || \
    sed -i '/android\s*{/a \    namespace "com.example.deliverybot"' "$GR"
    echo "[inject] Added namespace to existing android{} block"
  else
    # مفيش android{}؟ نضيف بلوك كامل
    cat >> "$GR" <<'EOF'

android {
    namespace "com.example.deliverybot"
}
EOF
    echo "[inject] Created android{} with namespace"
  fi
else
  echo "[ok] namespace already set in build.gradle"
fi

echo "[done] Manifest & namespace fixes completed."
