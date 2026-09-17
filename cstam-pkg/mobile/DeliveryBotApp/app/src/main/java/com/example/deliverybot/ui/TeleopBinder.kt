package com.example.deliverybot.ui

import android.app.Activity
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.view.ViewTreeObserver
import android.widget.Button
import android.widget.Toast

private const val TAG = "DeliveryBot/TeleopBinder"

/**
 * موحّد ربط أزرار التيليوب مع callback ترسل أوامر كنصوص.
 * - يوجد طريقتان:
 *   1) bind(activity, send)  : تربط فورًا.
 *   2) bindSmart(activity, send) : تنتظر اكتمال الـ layout ثم تربط (مفيدة بعد setContentView مباشرة).
 *
 * ملاحظات:
 * - لا يعتمد على أي كلاس خارجي (لا WebSocket ولا TeleopClient) لضمان أنه يكمبايل دائمًا.
 * - الأوامر الافتراضية: FWD/BACK/LEFT/RIGHT/STOP/FASTER/SLOWER/CONNECT/DISCONNECT
 * - عدّل أسماء الـ IDs لو مختلفة عندك.
 */
object TeleopBinder {

    // helper عام لإيجاد View بالاسم
    @Suppress("UNCHECKED_CAST")
    private fun <T> Activity.findId(idName: String): T? {
        val id = resources.getIdentifier(idName, "id", packageName)
        return if (id != 0) findViewById(id) as? T else null
    }

    // يربط زر واحد إن وُجد
    private fun Activity.bindButtonIfExists(idName: String, onClick: () -> Unit): Boolean {
        val btn = findId<Button>(idName)
        return if (btn != null) {
            btn.setOnClickListener { onClick() }
            true
        } else {
            false
        }
    }

    // الخريطة بين IDs والأوامر النصية
    private val defaultMap: LinkedHashMap<String, String> = linkedMapOf(
        "btnUp"          to "FWD",
        "btnDown"        to "BACK",
        "btnLeft"        to "LEFT",
        "btnRight"       to "RIGHT",
        "btnStop"        to "STOP",
        "btnFaster"      to "FASTER",
        "btnSlower"      to "SLOWER",
        "btnConnect"     to "CONNECT",
        "btnDisconnect"  to "DISCONNECT"
    )

    /**
     * ربط مباشر. وفّر callback يرسل الأمر (مثلاً: sendCommand(cmd))
     */
    fun bind(activity: Activity, send: (String) -> Unit) {
        var wired = 0
        for ((idName, cmd) in defaultMap) {
            val ok = activity.bindButtonIfExists(idName) {
                try {
                    send(cmd)
                } catch (t: Throwable) {
                    Log.e(TAG, "send(cmd) threw: ${t.message}", t)
                    Toast.makeText(activity, "Failed to send: $cmd", Toast.LENGTH_SHORT).show()
                }
            }
            if (ok) wired++
        }
        Log.i(TAG, "TeleopBinder.bind: wired $wired buttons")
        if (wired == 0) {
            Toast.makeText(activity, "No teleop buttons found", Toast.LENGTH_SHORT).show()
        }
    }

    /**
     * ربط “ذكي” بعد اكتمال الـ layout (آمن تُناديه بعد setContentView مباشرة).
     * إن ما احتجتش تأخير، استخدم bind(...) العادي.
     */
    fun bindSmart(activity: Activity, send: (String) -> Unit) {
        val root = activity.window?.decorView ?: run {
            // fallback: جرّب بعد 100ms
            Handler(Looper.getMainLooper()).postDelayed({ bind(activity, send) }, 100)
            return
        }
        val vto = root.viewTreeObserver
        val listener = object : ViewTreeObserver.OnGlobalLayoutListener {
            override fun onGlobalLayout() {
                if (root.viewTreeObserver.isAlive) {
                    root.viewTreeObserver.removeOnGlobalLayoutListener(this)
                }
                // اربط بعد ما كل الـ views تبقى جاهزة
                Handler(Looper.getMainLooper()).post { bind(activity, send) }
            }
        }
        vto.addOnGlobalLayoutListener(listener)
        Log.d(TAG, "bindSmart: will bind after layout")
    }

    /**
     * نسخة overload اختيارية في حال عايز تربط بدون إرسال فعلي (للغرض التجريبي أو اللوج فقط).
     * هتكمبايل أكيد ومش بتعتمد على أي كلاس خارجي.
     */
    fun bind(activity: Activity) {
        bind(activity) { cmd ->
            Log.i(TAG, "Command: $cmd (no sender provided)")
        }
    }

    fun bindSmart(activity: Activity) {
        bindSmart(activity) { cmd ->
            Log.i(TAG, "Command: $cmd (no sender provided)")
        }
    }
}
