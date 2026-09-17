#!/bin/bash
# ==========================
# DeliveryBot build & run
# ==========================

APP=~/ws/mobile/DeliveryBotApp
PKG="com.example.deliverybot"
APK="$APP/app/build/outputs/apk/debug/app-debug.apk"

cd "$APP" || { echo "❌ App folder not found"; read -rp "(Press Enter to close)..."; exit 1; }
chmod +x ./gradlew

echo "🚀 Starting build..."
if ! ./gradlew clean assembleDebug; then
  echo "❌ Build failed"
  read -rp "(Press Enter to close)..."
  exit 1
fi

if [ -f "$APK" ]; then
  echo "📱 Installing on device..."
  adb uninstall "$PKG" >/dev/null 2>&1 || true
  adb install -r "$APK" || { echo "❌ Install failed"; read -rp "(Press Enter to close)..."; exit 1; }

  echo "🔌 Reversing ports (9090, 8554)..."
  adb reverse tcp:9090 tcp:9090 || true
  adb reverse tcp:8554 tcp:8554 || true

  echo "▶️  Launching MainActivity..."
  adb shell am start -W -n "$PKG"/.MainActivity

  echo
  echo "✅ DeliveryBot launched with Black–Blue theme."
  echo "---- Recent logs (AndroidRuntime + app) ----"
  adb logcat -d | grep -i -e "$PKG" -e AndroidRuntime | tail -n 150 || true
else
  echo "❌ APK not found. Build may have failed."
fi

echo
read -rp "(Press Enter to close this terminal)..."

