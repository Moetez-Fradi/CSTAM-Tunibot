package com.example.deliverybot

import android.content.Context
import android.content.SharedPreferences

object ConnectionConfig {

    private fun prefs(ctx: Context): SharedPreferences =
        ctx.getSharedPreferences("app", Context.MODE_PRIVATE)

    // Get raw saved IP / host string
    private fun getRaw(ctx: Context): String =
        (prefs(ctx).getString("ip", "10.42.0.1") ?: "10.42.0.1").trim()

    // Extract host only (remove scheme + port if user entered them)
    fun host(ctx: Context): String {
        var s = getRaw(ctx)

        // remove scheme if exists
        if (s.contains("://")) {
            s = s.substringAfter("://")
        }

        // remove port if exists
        if (s.contains(":")) {
            s = s.substringBefore(":")
        }

        return s.ifBlank { "10.42.0.1" }
    }

    // ROSBridge WebSocket URL (SSL by default)
    fun rosbridgeWs(ctx: Context): String {
        var s = getRaw(ctx)

        // normalize scheme
        if (s.startsWith("ws://")) {
            s = s.replace("ws://", "wss://")
        } else if (!s.startsWith("wss://")) {
            s = "wss://$s"
        }

        // ensure port exists (default 9090)
        val noScheme = s.substringAfter("://")
        if (!noScheme.contains(":")) {
            s = "$s:9090"
        }

        return s
    }

    // ✅ FIXED CAMERA STREAM URL (THIS WAS THE BUG)
    fun cameraUrl(ctx: Context): String {
        val topic = "/camera/image_raw"
        return "http://${host(ctx)}:8080/stream?topic=$topic"
    }

    // Map image (optional feature)
    fun mapUrl(ctx: Context): String =
        "http://${host(ctx)}:8070/map/latest.png"

    // Save IP / host from settings screen
    fun setHost(ctx: Context, ip: String) {
        prefs(ctx).edit().putString("ip", ip.trim()).apply()
    }
}

