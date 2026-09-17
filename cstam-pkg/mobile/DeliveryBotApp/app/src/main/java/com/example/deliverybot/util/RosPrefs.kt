package com.example.deliverybot.util

import android.content.Context

object RosPrefs {
    private const val NAME = "ros_prefs"
    private const val KEY_IP = "robot_ip"

    fun saveIp(ctx: Context, ip: String) {
        ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).edit()
            .putString(KEY_IP, ip).apply()
    }

    fun getIp(ctx: Context): String? {
        return ctx.getSharedPreferences(NAME, Context.MODE_PRIVATE).getString(KEY_IP, null)
    }
}
