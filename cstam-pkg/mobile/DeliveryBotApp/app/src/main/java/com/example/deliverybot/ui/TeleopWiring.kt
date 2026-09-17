package com.example.deliverybot.ui

import android.app.Activity
import android.util.Log
import android.view.View
import android.widget.Button
import android.widget.Toast

private const val TAG = "DeliveryBot/TeleopWiring"

fun wireTeleopButtonsSmart(
    activity: Activity,
    onSend: (String) -> Unit
) {
    fun <T: View> find(idName: String): T? {
        val id = activity.resources.getIdentifier(idName, "id", activity.packageName)
        @Suppress("UNCHECKED_CAST")
        return if (id != 0) activity.findViewById(id) as? T else null
    }

    // جرّب IDs مشهورة
    val up    = find<Button>("btnUp")
    val down  = find<Button>("btnDown")
    val left  = find<Button>("btnLeft")
    val right = find<Button>("btnRight")
    val stop  = find<Button>("btnStop")

    var wired = 0

    fun attach(btn: Button?, command: String) {
        btn?.setOnClickListener { onSend(command) }?.also { wired++ }
    }

    // ربط مباشر لو الـ IDs سليمة
    attach(up,    "MOVE_FORWARD")
    attach(down,  "MOVE_BACKWARD")
    attach(left,  "TURN_LEFT")
    attach(right, "TURN_RIGHT")
    attach(stop,  "STOP")

    // لو مفيش IDs/أو متبادلة: اربط حسب نص الزر نفسه (↑ ↓ ← → ■ أو نص عربي/إنجليزي)
    val all = listOfNotNull(up, down, left, right, stop) +
              // لو اللوحة فيها أزرار أخرى، جرّب التقاطها من جذور شهيرة
              listOfNotNull(
                  find<Button>("arrowUp"),
                  find<Button>("arrowDown"),
                  find<Button>("arrowLeft"),
                  find<Button>("arrowRight")
              )

    all.distinct().forEach { b ->
        if (b.hasOnClickListeners()) return@forEach
        val t = (b.text?.toString() ?: "").trim()
        when {
            t == "↑" || t.equals("up", true) || t.contains("forward", true) || t.contains("قدّام") ->
                attach(b, "MOVE_FORWARD")
            t == "↓" || t.equals("down", true) || t.contains("back", true) || t.contains("ورا") ->
                attach(b, "MOVE_BACKWARD")
            t == "←" || t.contains("left", true) || t.contains("شمال") ->
                attach(b, "TURN_LEFT")
            t == "→" || t.contains("right", true) || t.contains("يمين") ->
                attach(b, "TURN_RIGHT")
            t == "■" || t.equals("stop", true) || t.contains("توقف") || t.contains("قف") ->
                attach(b, "STOP")
        }
    }

    if (wired == 0) {
        val msg = "لم أجد أزرار الاتجاهات. راجع IDs أو نصوص الأزرار."
        Log.w(TAG, msg)
        Toast.makeText(activity, msg, Toast.LENGTH_SHORT).show()
    } else {
        Log.i(TAG, "تم ربط $wired زر تحكم.")
    }
}
