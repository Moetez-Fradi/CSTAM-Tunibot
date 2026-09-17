package com.example.deliverybot

import android.content.Context

object PreferenceHelper {
    private const val PREFS = "deliverybot_prefs"
    private const val KEY_HOST = "host"

    fun getSavedHost(ctx: Context): String? {
        val sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return sp.getString(KEY_HOST, null)
    }

    fun setSavedHost(ctx: Context, host: String) {
        val sp = ctx.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        sp.edit().putString(KEY_HOST, host).apply()
    }
}
