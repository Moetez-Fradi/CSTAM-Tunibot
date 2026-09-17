package com.example.deliverybot.teleop

import android.util.Log
import okhttp3.*
import okio.ByteString
import java.util.concurrent.TimeUnit

class RosbridgeLite(private val wsUrl: String) {
    private val logTag = "RosbridgeLite"
    private val client = OkHttpClient.Builder()
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()
    private var socket: WebSocket? = null
    var connected: Boolean = false
        private set

    fun connect(onOpen: (() -> Unit)? = null) {
        if (wsUrl.isBlank() || !wsUrl.startsWith("ws://")) {
            Log.w(logTag, "skip connect: invalid wsUrl='$wsUrl'")
            return
        }
        val req = Request.Builder().url(wsUrl).build()
        socket = client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                connected = true
                Log.i(logTag, "connected $wsUrl")
                onOpen?.invoke()
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                Log.d(logTag, "msg: $text")
            }
            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                Log.d(logTag, "bin(${bytes.size})")
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                connected = false
                Log.e(logTag, "failure: ${t.message}")
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                connected = false
                Log.i(logTag, "closed: $code $reason")
            }
        })
    }

    fun send(json: String) {
        if (!connected) return
        socket?.send(json)
    }

    fun close() {
        try { socket?.close(1000, "bye") } catch (_: Exception) {}
        finally { connected = false; socket = null }
    }
}
