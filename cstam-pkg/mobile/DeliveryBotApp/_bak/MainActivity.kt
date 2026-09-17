package com.example.deliverybot

import android.content.Intent
import android.graphics.BitmapFactory
import android.net.Uri
import android.os.Bundle
import android.util.Base64
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.FileProvider
import com.google.android.exoplayer2.ExoPlayer
import com.google.android.exoplayer2.MediaItem
import com.google.android.exoplayer2.ui.StyledPlayerView
import org.json.JSONObject
import org.osmdroid.config.Configuration
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polyline
import android.preference.PreferenceManager
import java.io.File

class MainActivity : AppCompatActivity() {

    private lateinit var statusText: TextView
    private lateinit var robotInfo: TextView
    private lateinit var qrImage: ImageView
    private lateinit var btnReconnect: Button
    private lateinit var btnRequestQr: Button
    private lateinit var btnShare: Button
    private lateinit var btnOpenMap: Button
    private lateinit var btnOpenCamera: Button
    private lateinit var btnOpenChat: Button
    private lateinit var map: MapView
    private lateinit var playerView: StyledPlayerView

    private var robotMarker: Marker? = null
    private var routeLine: Polyline = Polyline()

    private var player: ExoPlayer? = null
    private var rtspUrl: String = "rtsp://127.0.0.1:8554/stream"

    private lateinit var ros: RosbridgeClient
    private var lastOrderId: String? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Configuration.getInstance().load(this, PreferenceManager.getDefaultSharedPreferences(this))
        Configuration.getInstance().userAgentValue = packageName
        setContentView(R.layout.activity_main)

        statusText = findViewById(R.id.statusText)
        robotInfo  = findViewById(R.id.robotInfo)
        qrImage    = findViewById(R.id.qrImage)
        btnReconnect = findViewById(R.id.btnReconnect)
        btnRequestQr = findViewById(R.id.btnRequestQr)
        btnShare     = findViewById(R.id.btnShare)
        btnOpenMap   = findViewById(R.id.btnOpenMap)
        btnOpenCamera= findViewById(R.id.btnOpenCamera)
        btnOpenChat  = findViewById(R.id.btnOpenChat)
        map          = findViewById(R.id.map)
        playerView   = findViewById(R.id.playerView)

        map.setMultiTouchControls(true)
        map.controller.setZoom(18.0)
        map.controller.setCenter(GeoPoint(30.0444, 31.2357))
        routeLine.setWidth(6f)
        map.overlays.add(routeLine)

        initPlayer()

        ros = RosbridgeClient(
            url = "ws://127.0.0.1:9090",
            onState = { s -> runOnUiThread { statusText.text = "ROS: $s" } },
            onPublish = { topic, msg -> onRosMessage(topic, msg) }
        )
        ros.connect()
        ros.subscribe("/robot/state", "std_msgs/msg/String")
        ros.subscribe("/order/created", "std_msgs/msg/String")
        ros.subscribe("/order/qr", "std_msgs/msg/String")

        btnReconnect.setOnClickListener { ros.close(); ros.connect() }
        btnRequestQr.setOnClickListener {
            val id = lastOrderId ?: run { Toast.makeText(this, "No order_id yet", Toast.LENGTH_SHORT).show(); return@setOnClickListener }
            val args = JSONObject().put("order_id", id)
            ros.callService("/order/request_qr", args) { resp ->
                val values = resp.optJSONObject("values") ?: return@callService
                val b64 = values.optString("qr_b64_png", "")
                if (b64.isNotEmpty()) {
                    val bytes = Base64.decode(b64, Base64.DEFAULT)
                    val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    runOnUiThread { qrImage.setImageBitmap(bmp) }
                }
            }
        }
        btnShare.setOnClickListener { shareQrToWhatsApp("+201000000000", "Order QR") }

        btnOpenMap.setOnClickListener {
            startActivity(Intent(this, MapActivity::class.java))
        }
        btnOpenCamera.setOnClickListener {
            startActivity(Intent(this, CameraActivity::class.java).putExtra("rtspUrl", rtspUrl))
        }
        btnOpenChat.setOnClickListener {
            startActivity(Intent(this, ChatActivity::class.java))
        }
    }

    private fun initPlayer() {
        player = ExoPlayer.Builder(this).build().also { p ->
            playerView.player = p
            p.setMediaItem(MediaItem.fromUri(Uri.parse(rtspUrl)))
            p.prepare()
            p.playWhenReady = true
        }
    }

    private fun releasePlayer() {
        playerView.player = null
        player?.release()
        player = null
    }

    private fun onRosMessage(topic: String, msg: JSONObject) {
        when (topic) {
            "/robot/state" -> {
                val raw = msg.optString("data", "{}")
                val obj = try { JSONObject(raw) } catch (_: Throwable) { JSONObject() }
                val mode = obj.optString("mode", "-")
                val batt = (obj.optDouble("battery", -1.0) * 100).toInt()
                val pose = obj.optJSONObject("pose") ?: JSONObject()
                val x = pose.optDouble("x", 0.0)
                val y = pose.optDouble("y", 0.0)
                val yaw = pose.optDouble("yaw", 0.0)
                val eta = obj.optInt("eta_sec", -1)
                runOnUiThread {
                    robotInfo.text = "Mode: $mode, Battery: ${if (batt>=0) "$batt%" else "-"}, Pose: (%.2f, %.2f, %.2f), ETA: %ds".format(x, y, yaw, eta)
                    updateMap(x, y)
                }
            }
            "/order/created" -> {
                val raw = msg.optString("data", "{}")
                val obj = try { JSONObject(raw) } catch (_: Throwable) { JSONObject() }
                lastOrderId = obj.optString("order_id", null)
                runOnUiThread { Toast.makeText(this, "Order: ${lastOrderId ?: "-"}", Toast.LENGTH_SHORT).show() }
            }
            "/order/qr" -> {
                val raw = msg.optString("data", "{}")
                val obj = try { JSONObject(raw) } catch (_: Throwable) { JSONObject() }
                val b64 = obj.optString("qr_b64_png", "")
                if (b64.isNotEmpty()) {
                    val bytes = Base64.decode(b64, Base64.DEFAULT)
                    val bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
                    runOnUiThread { qrImage.setImageBitmap(bmp) }
                }
            }
        }
    }

    private fun updateMap(x: Double, y: Double) {
        val gp = org.osmdroid.util.GeoPoint(y, x)
        if (robotMarker == null) {
            robotMarker = Marker(map).also {
                it.position = gp
                it.setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
                map.overlays.add(it)
            }
        } else {
            robotMarker?.position = gp
        }
        routeLine.addPoint(gp)
        map.invalidate()
        map.controller.animateTo(gp)
    }

    private fun shareQrToWhatsApp(phone: String, msg: String) {
        val cacheFile = File(cacheDir, "qr.png")
        (qrImage.drawable as? android.graphics.drawable.BitmapDrawable)?.bitmap?.let { bmp ->
            cacheFile.outputStream().use { out -> bmp.compress(android.graphics.Bitmap.CompressFormat.PNG, 100, out) }
        }
        val intent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
            setPackage("com.whatsapp")
            putExtra(android.content.Intent.EXTRA_TEXT, msg)
            type = if (cacheFile.exists()) "image/*" else "text/plain"
            if (cacheFile.exists()) {
                val uri = FileProvider.getUriForFile(this@MainActivity, "${packageName}.provider", cacheFile)
                putExtra(android.content.Intent.EXTRA_STREAM, uri)
                addFlags(android.content.Intent.FLAG_GRANT_READ_URI_PERMISSION)
            }
        }
        try { startActivity(intent) } catch (_: Exception) {
            Toast.makeText(this, "WhatsApp not installed", Toast.LENGTH_SHORT).show()
        }
    }

    override fun onStart() { super.onStart(); if (player == null) initPlayer() }
    override fun onStop() { super.onStop(); releasePlayer() }
}
