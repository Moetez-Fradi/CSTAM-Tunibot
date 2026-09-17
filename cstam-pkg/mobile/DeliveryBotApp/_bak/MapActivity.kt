package com.example.deliverybot

import android.os.Bundle
import android.preference.PreferenceManager
import androidx.appcompat.app.AppCompatActivity
import org.json.JSONObject
import org.osmdroid.config.Configuration
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polyline

class MapActivity : AppCompatActivity() {
    private lateinit var map: MapView
    private var robotMarker: Marker? = null
    private val routeLine = Polyline()
    private lateinit var ros: RosbridgeClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Configuration.getInstance().load(this, PreferenceManager.getDefaultSharedPreferences(this))
        Configuration.getInstance().userAgentValue = packageName
        setContentView(R.layout.activity_map)

        map = findViewById(R.id.map)
        map.setMultiTouchControls(true)
        map.controller.setZoom(18.0)
        map.controller.setCenter(GeoPoint(30.0444, 31.2357))
        routeLine.setWidth(6f)
        map.overlays.add(routeLine)

        ros = RosbridgeClient(
            url = "ws://127.0.0.1:9090",
            onState = { /* optional: show state somewhere */ },
            onPublish = { topic, msg -> onRosMessage(topic, msg) }
        )
        ros.connect()
        ros.subscribe("/robot/state", "std_msgs/msg/String")
    }

    private fun onRosMessage(topic: String, msg: JSONObject) {
        if (topic != "/robot/state") return
        val raw = msg.optString("data", "{}")
        val obj = try { JSONObject(raw) } catch (_: Throwable) { JSONObject() }
        val pose = obj.optJSONObject("pose") ?: JSONObject()
        val x = pose.optDouble("x", 0.0) // lon?
        val y = pose.optDouble("y", 0.0) // lat?
        runOnUiThread { updateMap(x, y) }
    }

    private fun updateMap(x: Double, y: Double) {
        val gp = GeoPoint(y, x)
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
        map.controller.animateTo(gp)
        map.invalidate()
    }

    override fun onDestroy() {
        super.onDestroy()
        map.onDetach()
    }
}
