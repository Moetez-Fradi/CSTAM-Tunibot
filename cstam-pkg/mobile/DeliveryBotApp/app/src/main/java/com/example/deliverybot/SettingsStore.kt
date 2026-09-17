package com.example.deliverybot

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking

private val Context.dataStore by preferencesDataStore(name = "deliverybot_settings")

object SettingsStore {
    private val KEY_ROBOT_IP = stringPreferencesKey("robot_ip")
    private const val DEFAULT_IP = "127.0.0.1"

    /** حفظ الـ IP */
    fun saveIpBlocking(context: Context, ip: String) = runBlocking {
        context.dataStore.edit { it[KEY_ROBOT_IP] = ip.trim() }
    }

    /** قراءة الـ IP (افتراضي 127.0.0.1) */
    fun getIpBlocking(context: Context): String = runBlocking {
        val prefs = context.dataStore.data.first()
        (prefs[KEY_ROBOT_IP] ?: DEFAULT_IP).ifBlank { DEFAULT_IP }
    }

    /** WebSocket (rosbridge) — افتراضياً 9090 */
    fun getWsUrlBlocking(context: Context, port: Int = 9090): String {
        val ip = getIpBlocking(context)
        return "ws://$ip:$port"
    }

    /** REST/Flask QR server — افتراضياً 5000 */
    fun getQrServerBaseBlocking(context: Context, port: Int = 5000): String {
        val ip = getIpBlocking(context)
        return "http://$ip:$port"
    }

    /** RTSP للكاميرا — افتراضياً 8554/stream */
    fun getRtspUrlBlocking(context: Context, port: Int = 8554, path: String = "stream"): String {
        val ip = getIpBlocking(context)
        return "rtsp://$ip:$port/$path"
    }
}
