package com.example.deliverybot.video

import android.graphics.BitmapFactory
import android.widget.ImageView
import kotlinx.coroutines.*
import java.io.BufferedInputStream
import java.net.HttpURLConnection
import java.net.URL

class MjpegInput(private val url: String, private val target: ImageView) {
    private var job: Job? = null

    fun start() {
        stop()
        job = CoroutineScope(Dispatchers.IO).launch {
            try {
                val conn = URL(url).openConnection() as HttpURLConnection
                conn.setRequestProperty("User-Agent", "DeliveryBotApp")
                conn.connect()
                val ins = BufferedInputStream(conn.inputStream)
                val buf = ByteArray(1 shl 20)

                while (isActive) {
                    // sync to SOI (FF D8)
                    var off = 0
                    while (true) {
                        val b = ins.read()
                        if (b == -1) return@launch
                        if (b == 0xFF) {
                            val b2 = ins.read()
                            if (b2 == 0xD8) {
                                buf[0] = 0xFF.toByte(); buf[1] = 0xD8.toByte(); off = 2
                                break
                            }
                        }
                    }
                    // read until EOI (FF D9)
                    while (true) {
                        val r = ins.read(buf, off, buf.size - off)
                        if (r <= 0) break
                        off += r
                        if (off >= 2 && buf[off - 2] == 0xFF.toByte() && buf[off - 1] == 0xD9.toByte()) break
                    }
                    val bmp = BitmapFactory.decodeByteArray(buf, 0, off)
                    if (bmp != null) withContext(Dispatchers.Main) { target.setImageBitmap(bmp) }
                }
            } catch (_: Exception) { /* ignore */ }
        }
    }

    fun stop() { job?.cancel(); job = null }
}
