package com.example.deliverybot.map

import android.graphics.BitmapFactory
import android.widget.ImageView
import kotlinx.coroutines.*
import java.net.URL

class MapRefresher(private val url: String, private val img: ImageView) {
    private var job: Job? = null
    fun start(periodMs: Long = 1000L) {
        stop()
        job = CoroutineScope(Dispatchers.IO).launch {
            while (isActive) {
                try {
                    val bytes = URL("$url?ts=${System.currentTimeMillis()}").readBytes()
                    val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    if (bmp != null) withContext(Dispatchers.Main) { img.setImageBitmap(bmp) }
                } catch (_: Exception) {}
                delay(periodMs)
            }
        }
    }
    fun stop() { job?.cancel(); job = null }
}
