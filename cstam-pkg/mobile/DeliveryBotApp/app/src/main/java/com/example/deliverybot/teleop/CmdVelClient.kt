package com.example.deliverybot.teleop

import android.content.Context
import android.util.Log
import okhttp3.*
import org.json.JSONObject
import java.util.concurrent.TimeUnit
import com.example.deliverybot.ConnectionConfig

class CmdVelClient(private val ctx: Context) : WebSocketListener() {

    private val tag = "CmdVel"
    private val topic = "/cmd_vel"
    private val type  = "geometry_msgs/Twist"

    private val client = getUnsafeOkHttpClient()

    private fun getUnsafeOkHttpClient(): OkHttpClient {
        try {
            val trustAllCerts = arrayOf<javax.net.ssl.TrustManager>(object : javax.net.ssl.X509TrustManager {
                override fun checkClientTrusted(chain: Array<java.security.cert.X509Certificate>, authType: String) {}
                override fun checkServerTrusted(chain: Array<java.security.cert.X509Certificate>, authType: String) {}
                override fun getAcceptedIssuers(): Array<java.security.cert.X509Certificate> = arrayOf()
            })
            val sslContext = javax.net.ssl.SSLContext.getInstance("SSL")
            sslContext.init(null, trustAllCerts, java.security.SecureRandom())
            val sslSocketFactory = sslContext.socketFactory

            return OkHttpClient.Builder()
                .sslSocketFactory(sslSocketFactory, trustAllCerts[0] as javax.net.ssl.X509TrustManager)
                .hostnameVerifier { _, _ -> true }
                .readTimeout(0, TimeUnit.MILLISECONDS)
                .pingInterval(15, TimeUnit.SECONDS)
                .build()
        } catch (e: Exception) {
            throw RuntimeException(e)
        }
    }

    private var ws: WebSocket? = null
    @Volatile private var connected = false
    private var id = 0
    private fun nextId() = "id_${System.currentTimeMillis()}_${id++}"


    private fun wsUrl(): String {
        return ConnectionConfig.rosbridgeWs(ctx)
    }

    fun connect() {
        if (connected) return
        val req = Request.Builder().url(wsUrl()).build()
        ws = client.newWebSocket(req, this)
    }

    fun close() {
        try { ws?.close(1000, "bye") } catch (_: Throwable) {}
        ws = null
        connected = false
    }

    override fun onOpen(webSocket: WebSocket, response: Response) {
        connected = true
        Log.i(tag, "rosbridge connected")
        val adv = JSONObject()
            .put("op","advertise")
            .put("id", nextId())
            .put("topic", topic)
            .put("type", type)
        webSocket.send(adv.toString())
    }

    override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
        Log.e(tag, "ws failure: ${t.message}")
        connected = false
    }

    override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
        Log.i(tag, "ws closed: $code $reason")
        connected = false
    }

    fun publish(
        linearX: Double = 0.0, linearY: Double = 0.0, linearZ: Double = 0.0,
        angularX: Double = 0.0, angularY: Double = 0.0, angularZ: Double = 0.0
    ) {
        if (!connected) connect()
        val msg = JSONObject()
            .put("op","publish")
            .put("id", nextId())
            .put("topic", topic)
            .put("msg", JSONObject()
                .put("linear", JSONObject().put("x",linearX).put("y",linearY).put("z",linearZ))
                .put("angular", JSONObject().put("x",angularX).put("y",angularY).put("z",angularZ))
            )
        ws?.send(msg.toString())
    }

    fun stop() = publish(0.0,0.0,0.0,0.0,0.0,0.0)
}
