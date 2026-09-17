package com.example.deliverybot

import android.util.Log
import okhttp3.*
import okio.ByteString
import org.json.JSONObject
import java.util.concurrent.TimeUnit

class RosbridgeClient(
    private val url: String,
    private val onState: (String) -> Unit = {},
    private val onPublish: (topic: String, msg: JSONObject) -> Unit = { _, _ -> }
) : WebSocketListener() {

    private val client = OkHttpClient.Builder()
        .pingInterval(15, TimeUnit.SECONDS)
        .readTimeout(0, TimeUnit.MILLISECONDS)
        .build()

    private var ws: WebSocket? = null
    private var reconnectAttempts = 0

    fun connect() {
        onState("connecting")
        val req = Request.Builder().url(url).build()
        ws = client.newWebSocket(req, this)
    }

    fun close() {
        ws?.close(1000, "bye")
        ws = null
    }

    fun subscribe(topic: String, type: String) {
        val obj = JSONObject()
            .put("op", "subscribe")
            .put("topic", topic)
            .put("type", type)
        ws?.send(obj.toString())
    }

    fun publish(topic: String, msg: JSONObject) {
        val obj = JSONObject()
            .put("op", "publish")
            .put("topic", topic)
            .put("msg", msg)
        ws?.send(obj.toString())
    }

    override fun onOpen(webSocket: WebSocket, response: Response) {
        reconnectAttempts = 0
        onState("connected")
    }

    override fun onMessage(webSocket: WebSocket, text: String) {
        try {
            val j = JSONObject(text)
            val topic = j.optString("topic", "")
            val msg = j.optJSONObject("msg") ?: return
            if (topic.isNotBlank()) onPublish(topic, msg)
        } catch (e: Exception) {
            Log.w("Rosbridge", "Non-JSON message: $text")
        }
    }

    override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
        // rosbridge is text, ignore
    }

    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
        onState("closed")
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        onState("disconnected: ${t.message ?: "error"}")
        if (reconnectAttempts < 6) {
            val backoffMs = (1000 * Math.pow(2.0, reconnectAttempts.toDouble())).toLong().coerceAtMost(15000)
            reconnectAttempts++
            Thread.sleep(backoffMs)
            connect()
        }
    }
}
