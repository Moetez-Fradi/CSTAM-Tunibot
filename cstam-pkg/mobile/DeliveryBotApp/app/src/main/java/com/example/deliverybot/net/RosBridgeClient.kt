package com.example.deliverybot.net

import android.util.Log
import okhttp3.*
import okio.ByteString
import org.json.JSONObject
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.TimeUnit

object RosBridgeClient {
    private const val TAG = "RosBridgeClient"

    // WebSocket state
    private var ws: WebSocket? = null
    @Volatile private var connected: Boolean = false
    private var lastUrl: String = "wss://10.42.0.1:9090"

    // Caches
    private val advertisedTopics = mutableSetOf<String>() // topics we advertised
    private val subscriptions =
        ConcurrentHashMap<String, CopyOnWriteArrayList<(String) -> Unit>>() // topic -> callbacks

    // OkHttp client
    // OkHttp client with self-signed cert support
    private val client = getUnsafeOkHttpClient()

    private fun getUnsafeOkHttpClient(): OkHttpClient {
        try {
            // Create a trust manager that does not validate certificate chains
            val trustAllCerts = arrayOf<javax.net.ssl.TrustManager>(object : javax.net.ssl.X509TrustManager {
                override fun checkClientTrusted(chain: Array<java.security.cert.X509Certificate>, authType: String) {}
                override fun checkServerTrusted(chain: Array<java.security.cert.X509Certificate>, authType: String) {}
                override fun getAcceptedIssuers(): Array<java.security.cert.X509Certificate> = arrayOf()
            })

            // Install the all-trusting trust manager
            val sslContext = javax.net.ssl.SSLContext.getInstance("SSL")
            sslContext.init(null, trustAllCerts, java.security.SecureRandom())
            
            // Create an ssl socket factory with our all-trusting manager
            val sslSocketFactory = sslContext.socketFactory

            return OkHttpClient.Builder()
                .sslSocketFactory(sslSocketFactory, trustAllCerts[0] as javax.net.ssl.X509TrustManager)
                .hostnameVerifier { _, _ -> true }
                .pingInterval(15, TimeUnit.SECONDS)
                .retryOnConnectionFailure(true)
                .build()
        } catch (e: Exception) {
            throw RuntimeException(e)
        }
    }

    // Connection listeners
    private val connectionListeners = CopyOnWriteArrayList<(Boolean) -> Unit>()

    fun addConnectionListener(listener: (Boolean) -> Unit) {
        connectionListeners.add(listener)
    }

    fun removeConnectionListener(listener: (Boolean) -> Unit) {
        connectionListeners.remove(listener)
    }

    private fun notifyConnectionListeners(isConnected: Boolean) {
        connectionListeners.forEach { it(isConnected) }
    }

    // ----------------------------------------------------------------------------
    // Public API
    // ----------------------------------------------------------------------------

    @JvmStatic
    fun connect(baseUrl: String = lastUrl) {
        if (connected && ws != null) {
            if (baseUrl == lastUrl) {
                Log.i(TAG, "Already connected to $baseUrl")
                notifyConnectionListeners(true) // Notify listeners that we are connected
                return
            }
            // URL changed, close existing
            try { ws?.close(1000, "Reconnecting") } catch(_: Throwable){}
            ws = null
            connected = false
        }
        lastUrl = baseUrl
        try {
            val req = Request.Builder().url(baseUrl).build()
            ws = client.newWebSocket(req, object : WebSocketListener() {
                override fun onOpen(webSocket: WebSocket, response: Response) {
                    connected = true
                    Log.i(TAG, "WS OPEN: $baseUrl  code=${response.code}")
                    notifyConnectionListeners(true)
                    // Re-subscribe any previously requested topics after reconnect
                    resubscribeAll()
                }

                override fun onMessage(webSocket: WebSocket, text: String) {
                    // Route incoming messages to subscribers
                    try {
                        Log.d(TAG, "WS RX: $text")
                        val obj = JSONObject(text)

                        // rosbridge publish message format typically contains: "op":"publish", "topic":"...", "msg":{...}
                        val topic = if (obj.has("topic")) obj.optString("topic") else null
                        val msg = obj.optJSONObject("msg")
                        val data = msg?.optString("data", null)

                        if (topic != null && data != null) {
                            subscriptions[topic]?.forEach { cb ->
                                try { cb(data) } catch (t: Throwable) {
                                    Log.w(TAG, "subscriber threw for $topic: ${t.message}")
                                }
                            }
                        }
                    } catch (t: Throwable) {
                        Log.w(TAG, "onMessage parse error: ${t.message}")
                    }
                }

                override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                    Log.d(TAG, "WS RX(bytes): ${bytes.size}B")
                }

                override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                    connected = false
                    Log.e(TAG, "WS FAIL: ${t.message}", t)
                    notifyConnectionListeners(false)
                }

                override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                    connected = false
                    Log.i(TAG, "WS CLOSED: $code $reason")
                    notifyConnectionListeners(false)
                }
            })
        } catch (t: Throwable) {
            connected = false
            Log.e(TAG, "connect() error: ${t.message}", t)
        }
    }

    @JvmStatic
    fun isConnected(): Boolean = connected

    @JvmStatic
    fun send(json: String) {
        if (!connected) {
            Log.w(TAG, "send() called but WS not connected")
            return
        }
        ws?.send(json)
    }

    /**
     * Publish std_msgs/msg/String to a topic.
     * Will 'advertise' the topic once per app session.
     */
    @JvmStatic
    fun publish(topic: String, data: String) {
        if (!connected) {
            Log.w(TAG, "publish() called but WS not connected, topic=$topic")
            return
        }
        try {
            // Advertise once
            if (advertisedTopics.add(topic)) {
                val adv = JSONObject()
                    .put("op", "advertise")
                    .put("topic", topic)
                    .put("type", "std_msgs/msg/String")
                ws?.send(adv.toString())
                Log.d(TAG, "WS TX advertise: $adv")
            }

            // Publish
            val obj = JSONObject()
                .put("op", "publish")
                .put("topic", topic)
                .put("msg", JSONObject().put("data", data))
            ws?.send(obj.toString())
            Log.d(TAG, "WS TX publish: $obj")
        } catch (t: Throwable) {
            Log.e(TAG, "publish() error: ${t.message}", t)
        }
    }

    /**
     * Subscribe to std_msgs/msg/String topic.
     * The same topic can have multiple callbacks.
     */
    @JvmStatic
    fun subscribe(topic: String, callback: (String) -> Unit) {
        // Register callback locally
        val list = subscriptions.getOrPut(topic) { CopyOnWriteArrayList() }
        list.add(callback)

        // Send subscribe op if connected
        if (connected) {
            try {
                val sub = JSONObject()
                    .put("op", "subscribe")
                    .put("topic", topic)
                    .put("type", "std_msgs/msg/String")
                ws?.send(sub.toString())
                Log.d(TAG, "WS TX subscribe: $sub")
            } catch (t: Throwable) {
                Log.e(TAG, "subscribe() error: ${t.message}", t)
            }
        }
    }

    /**
     * Unsubscribe from a topic (all callbacks if callback == null).
     */
    @JvmStatic
    fun unsubscribe(topic: String, callback: ((String) -> Unit)? = null) {
        val list = subscriptions[topic]
        if (list != null) {
            if (callback == null) list.clear() else list.remove(callback)
            if (list.isEmpty()) {
                subscriptions.remove(topic)
                if (connected) {
                    try {
                        val unsub = JSONObject()
                            .put("op", "unsubscribe")
                            .put("topic", topic)
                        ws?.send(unsub.toString())
                        Log.d(TAG, "WS TX unsubscribe: $unsub")
                    } catch (_: Throwable) {}
                }
            }
        }
    }

    @JvmStatic
    fun close() {
        try {
            // Unadvertise
            for (t in advertisedTopics) {
                try {
                    val unadv = JSONObject()
                        .put("op", "unadvertise")
                        .put("topic", t)
                    ws?.send(unadv.toString())
                    Log.d(TAG, "WS TX unadvertise: $unadv")
                } catch (_: Throwable) { /* ignore */ }
            }
            advertisedTopics.clear()

            // Unsubscribe all
            for (t in subscriptions.keys) {
                try {
                    val unsub = JSONObject()
                        .put("op", "unsubscribe")
                        .put("topic", t)
                    ws?.send(unsub.toString())
                    Log.d(TAG, "WS TX unsubscribe: $unsub")
                } catch (_: Throwable) {}
            }
            subscriptions.clear()

            ws?.close(1000, "bye")
        } finally {
            connected = false
            ws = null
        }
    }

    // ----------------------------------------------------------------------------
    // Helpers
    // ----------------------------------------------------------------------------

    private fun resubscribeAll() {
        if (!connected) return
        for (t in subscriptions.keys) {
            try {
                val sub = JSONObject()
                    .put("op", "subscribe")
                    .put("topic", t)
                    .put("type", "std_msgs/msg/String")
                ws?.send(sub.toString())
                Log.d(TAG, "WS TX resubscribe: $sub")
            } catch (_: Throwable) {}
        }
        // Re-advertise previously advertised topics (optional; rosbridge usually persists)
        val prev = advertisedTopics.toList()
        advertisedTopics.clear()
        for (t in prev) {
            if (advertisedTopics.add(t)) {
                try {
                    val adv = JSONObject()
                        .put("op", "advertise")
                        .put("topic", t)
                        .put("type", "std_msgs/msg/String")
                    ws?.send(adv.toString())
                    Log.d(TAG, "WS TX re-advertise: $adv")
                } catch (_: Throwable) {}
            }
        }
    }
}

