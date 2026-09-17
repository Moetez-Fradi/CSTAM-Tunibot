package com.example.deliverybot.ui

import android.app.Activity
import android.util.Log
import android.view.View
import android.view.ViewGroup
import android.widget.Button
import android.widget.Toast

private const val TAG = "DeliveryBot/PanelToggle"

fun wireControlPanelToggle(activity: Activity) {
    fun <T: View> Activity.find(idName: String): T? {
        val id = resources.getIdentifier(idName, "id", packageName)
        @Suppress("UNCHECKED_CAST")
        return if (id != 0) findViewById<T>(id) else null
    }

    // ابحث عن زر التبديل: بالـ id الشائع أو بالنص "Control Panel"
    val toggleBtn: Button? =
        activity.find("btnControlPanel")
            ?: findButtonByText(activity, "Control Panel")

    if (toggleBtn == null) {
        val msg = "Control Panel button not found (id=btnControlPanel or text=Control Panel)"
        Log.w(TAG, msg)
        Toast.makeText(activity, msg, Toast.LENGTH_SHORT).show()
        return
    }

    // أهداف التبديل (لوحة الاتجاهات)
    val explicitPanel: View? =
        activity.find("controlPanel")
            ?: activity.find("teleopPanel")

    // بدائل: أزرار الاتجاهات الفردية
    val btnUp   : View? = activity.find("btnUp")
    val btnDown : View? = activity.find("btnDown")
    val btnLeft : View? = activity.find("btnLeft")
    val btnRight: View? = activity.find("btnRight")
    val btnStop : View? = activity.find("btnStop")

    // لو مفيش panel، جرّب ناخد الـ parent بتاع btnUp كلوحة
    val inferredPanel: View? = explicitPanel ?: (btnUp?.parent as? View)

    // مجموعة fallback لأزرار منفردة لو مفيش panel واحد
    val padButtons = listOfNotNull(btnUp, btnDown, btnLeft, btnRight, btnStop)

    // خليهم في الأول ظاهرين (لو انت عايزهم يبتدوا مخفيين خلّي VISIBLE -> GONE)
    if (inferredPanel != null) {
        inferredPanel.visibility = inferredPanel.visibility
        Log.i(TAG, "Panel source: " + idNameOf(activity, inferredPanel))
    } else if (padButtons.isNotEmpty()) {
        padButtons.forEach { it.visibility = it.visibility }
        Log.i(TAG, "Panel inferred from individual buttons.")
    } else {
        val msg = "No teleop panel or buttons found (try ids: controlPanel/teleopPanel/btnUp...)"
        Log.w(TAG, msg)
        Toast.makeText(activity, msg, Toast.LENGTH_SHORT).show()
    }

    toggleBtn.setOnClickListener {
        val panel = inferredPanel
        if (panel != null) {
            panel.visibility = if (panel.visibility == View.VISIBLE) View.GONE else View.VISIBLE
            Log.d(TAG, "Toggled panel -> ${panel.visibility}")
        } else if (padButtons.isNotEmpty()) {
            val anyVisible = padButtons.any { it.visibility == View.VISIBLE }
            val newVis = if (anyVisible) View.GONE else View.VISIBLE
            padButtons.forEach { it.visibility = newVis }
            Log.d(TAG, "Toggled ${padButtons.size} buttons -> $newVis")
        } else {
            Toast.makeText(activity, "Nothing to toggle", Toast.LENGTH_SHORT).show()
        }
    }
}

/** يدور في شجرة الـ View على Button بالنص */
private fun findButtonByText(activity: Activity, text: String): Button? {
    val root = (activity.findViewById<View>(android.R.id.content) as ViewGroup).getChildAt(0)
    return findButtonByTextDFS(root, text)
}

private fun findButtonByTextDFS(v: View?, text: String): Button? {
    if (v == null) return null
    if (v is Button && v.text?.toString()?.trim()?.equals(text, ignoreCase = true) == true) return v
    if (v is ViewGroup) {
        for (i in 0 until v.childCount) {
            findButtonByTextDFS(v.getChildAt(i), text)?.let { return it }
        }
    }
    return null
}

private fun idNameOf(activity: Activity, view: View): String {
    return try {
        val id = view.id
        if (id == View.NO_ID) "NO_ID"
        else activity.resources.getResourceEntryName(id)
    } catch (_: Exception) { "UNKNOWN_ID" }
}
