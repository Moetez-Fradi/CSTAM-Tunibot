package com.example.deliverybot

import android.content.ContentProvider
import android.content.ContentValues
import android.content.Context
import android.database.Cursor
import android.net.Uri

/**
 * مزوّد بسيط يوفّر ApplicationContext مبكرًا لو لزم.
 * شِلنا أي مراجع قديمة لـ RosBridge.
 */
class InitProvider : ContentProvider() {
    override fun onCreate(): Boolean {
        appContext = context?.applicationContext
        return true
    }

    override fun query(u: Uri, p: Array<out String>?, s: String?, a: Array<out String>?, o: String?): Cursor? = null
    override fun getType(u: Uri): String? = null
    override fun insert(u: Uri, v: ContentValues?): Uri? = null
    override fun delete(u: Uri, s: String?, a: Array<out String>?): Int = 0
    override fun update(u: Uri, v: ContentValues?, s: String?, a: Array<out String>?): Int = 0

    companion object {
        @JvmStatic var appContext: Context? = null
    }
}
