package com.example.deliverybot.teleop

import android.util.Log
import org.json.JSONObject
import kotlin.math.round

class CmdVelPublisher(private val ros: RosbridgeLite) {
    private var advertised = false
    private val topic = "/cmd_vel"
    private val msgType = "geometry_msgs/Twist"

    fun ensureAdvertised() {
        if (advertised || !ros.connected) return
        val adv = JSONObject()
            .put("op", "advertise")
            .put("topic", topic)
            .put("type", msgType)
        ros.send(adv.toString())
        advertised = true
        Log.i("CmdVelPublisher", "advertised $topic")
    }

    private fun publish(linear: Double, angular: Double) {
        if (!ros.connected) return
        ensureAdvertised()
        val msg = JSONObject()
            .put("linear", JSONObject().put("x", linear).put("y", 0).put("z", 0))
            .put("angular", JSONObject().put("x", 0).put("y", 0).put("z", angular))
        val pub = JSONObject()
            .put("op", "publish")
            .put("topic", topic)
            .put("msg", msg)
        ros.send(pub.toString())
    }

    fun forward(speed: Double) = publish(speed, 0.0)
    fun backward(speed: Double) = publish(-speed, 0.0)
    fun left(speed: Double) = publish(0.0, +speed)
    fun right(speed: Double) = publish(0.0, -speed)
    fun stop() = publish(0.0, 0.0)

    companion object {
        /** يحوّل قيمة السلايدر [0..100] إلى سرعة [0..1.0] */
        fun speedFromProgress(p: Int): Double = round((p.coerceIn(0,100) / 100.0) * 100) / 100.0
    }
}
