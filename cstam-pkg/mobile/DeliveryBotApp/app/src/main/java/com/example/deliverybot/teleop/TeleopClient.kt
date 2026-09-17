package com.example.deliverybot.teleop

import android.content.Context
import android.util.Log
import com.example.deliverybot.ConnectionConfig
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

class TeleopClient(private val ctx: Context) : WebSocketListener() {

    private val logTag = "TeleopClient"
    private val client = OkHttpClient()
    private var socket: WebSocket? = null

    fun connect() {
        val wsUrl = ConnectionConfig.rosbridgeWs(ctx)   // مثال: ws://10.42.0.1:9090 أو ws://10.42.0.1/rosbridge/
        val req = Request.Builder().url(wsUrl).build()
        socket = client.newWebSocket(req, this)
        Log.i(logTag, "connecting to $wsUrl")
    }

    fun sendRaw(json: String) {
        socket?.send(json)
    }

    fun close() {
        socket?.close(1000, "bye")
        socket = null
    }

    override fun onOpen(webSocket: WebSocket, response: Response) {
        Log.i(logTag, "ws open")
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        Log.e(logTag, "ws failure: ${t.message}")
    }
}
