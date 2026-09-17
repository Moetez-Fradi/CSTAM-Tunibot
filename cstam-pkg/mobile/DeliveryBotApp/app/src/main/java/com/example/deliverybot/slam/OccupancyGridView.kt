package com.example.deliverybot.slam

import android.content.Context
import android.graphics.*
import android.util.AttributeSet
import android.view.View
import kotlin.math.*

/** يرسم nav_msgs/OccupancyGrid:
 *  -1 = غير معروف (رمادي) / 0 = حر (أبيض) / 100 = مشغول (أسود)
 */
class OccupancyGridView @JvmOverloads constructor(
    context: Context, attrs: AttributeSet? = null
) : View(context, attrs) {

    private var bmp: Bitmap? = null
    private val p = Paint(Paint.ANTI_ALIAS_FLAG)
    private val mat = Matrix()

    /** استقبل شبكة الماب كـ مصفوفة (size = width*height) */
    fun setGrid(width: Int, height: Int, data: IntArray) {
        if (width <= 0 || height <= 0) return
        val b = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
        val pixels = IntArray(width * height)

        // OccupancyGrid بييجي Row-major من أسفل لأعلى غالبًا، بنعكس صفوف للرسم الطبيعي
        for (y in 0 until height) {
            val srcRow = (height - 1 - y) * width
            val dstRow = y * width
            for (x in 0 until width) {
                val v = data[srcRow + x]
                val gray = when {
                    v < 0   -> 0x88  // unknown
                    v >= 100 -> 0x00 // occupied (أسود)
                    else    -> {     // free = أبيض كلما قلّت النسبة
                        val g = 255 - (v * 255 / 100)
                        g
                    }
                }
                val argb = (0xFF shl 24) or (gray shl 16) or (gray shl 8) or gray
                pixels[dstRow + x] = argb
            }
        }
        b.setPixels(pixels, 0, width, 0, 0, width, height)
        bmp = b
        invalidate()
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val b = bmp ?: return
        // وسّع الصورة للحجم المتاح مع الحفاظ على النسبة
        val sx = width.toFloat() / b.width
        val sy = height.toFloat() / b.height
        val s = min(sx, sy)
        val dx = (width - b.width * s) / 2f
        val dy = (height - b.height * s) / 2f
        mat.reset()
        mat.postScale(s, s)
        mat.postTranslate(dx, dy)
        canvas.drawColor(Color.DKGRAY)
        canvas.drawBitmap(b, mat, p)
    }
}
