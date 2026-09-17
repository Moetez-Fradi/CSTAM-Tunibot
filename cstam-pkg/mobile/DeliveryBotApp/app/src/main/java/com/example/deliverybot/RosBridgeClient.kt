package com.example.deliverybot

import android.util.Log
import okhttp3.*

import java.util.concurrent.TimeUnit

class RosBridgeClient(
    private val url: String,
    private val onOpen: () -> Unit = {},
    private val onMessage: (String) -> Unit = {},
    private val onFailure: (Throwable) -> Unit = {},
    private val onClosed: () -> Unit = {}
) {
    private val TAG = "DeliveryBot/RosWS"
    private var ws: WebSocket? = null

    private val client = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .retryOnConnectionFailure(true)
        .build()

    fun connect() {
        val req = Request.Builder().url(url).build()
        ws = client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                Log.i(TAG, "WS OPEN"); onOpen()
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                onMessage(text)
            }
            override fun onMessage(webSocket: WebSocket, bytes: okio.ByteString) {
                onMessage(bytes.utf8())
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                Log.e(TAG, "WS FAIL: ${t.message}"); onFailure(t)
            }
            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                Log.i(TAG, "WS CLOSED: $code/$reason"); onClosed()
            }
        })
    }

    fun send(json: String) { ws?.send(json) }
    fun close() { ws?.close(1000, "bye") }
}
