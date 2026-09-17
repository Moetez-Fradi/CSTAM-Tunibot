#!/usr/bin/env bash
set -euo pipefail

PKG="com.example.deliverybot"
USER_ID="${USER_ID:-0}"

cmd_help() {
  echo "Usage: $0 [install|start|start-map|start-chat|clear|uninstall|logs]"
  echo "  USER_ID=<id> $0 start      # اختياري: تحديد المستخدم (الافتراضي 0)"
}

cmd_install() {
  APK="${1:-app/build/outputs/apk/debug/app-debug.apk}"
  if [ ! -f "$APK" ]; then
    echo "❌ APK not found: $APK"
    exit 1
  fi
  adb install --user "$USER_ID" -r "$APK"
}

cmd_start() {
  adb shell am start --user "$USER_ID" -n "$PKG/.MainActivity"
}

cmd_start_map() {
  adb shell am start --user "$USER_ID" -n "$PKG/.MapActivity"
}

cmd_start_chat() {
  adb shell am start --user "$USER_ID" -n "$PKG/.ChatActivity"
}

cmd_clear() {
  adb shell pm clear --user "$USER_ID" "$PKG" || true
}

cmd_uninstall() {
  adb shell pm uninstall --user "$USER_ID" "$PKG" || true
}

cmd_logs() {
  PID="$(adb shell pidof $PKG || true)"
  if [ -n "$PID" ]; then
    echo "[*] Attaching logcat to PID=$PID"
    adb logcat --pid="$PID"
  else
    echo "[*] No PID yet; tailing filtered logcat… (Ctrl+C to exit)"
    adb logcat | grep -iE "AndroidRuntime|FATAL EXCEPTION|$PKG|MapActivity|ChatActivity"
  fi
}

case "${1:-}" in
  install)    shift; cmd_install "$@";;
  start)                cmd_start;;
  start-map)            cmd_start_map;;
  start-chat)           cmd_start_chat;;
  clear)                cmd_clear;;
  uninstall)            cmd_uninstall;;
  logs)                 cmd_logs;;
  * )                   cmd_help;;
esac
