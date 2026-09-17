package com.example.deliverybot

import android.annotation.SuppressLint
import android.os.Bundle
import android.view.View
import android.webkit.*
import android.widget.FrameLayout
import android.widget.ProgressBar
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

class CameraActivity : AppCompatActivity() {
    private lateinit var web: WebView
    private lateinit var progress: ProgressBar

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = FrameLayout(this)
        web = WebView(this)
        progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            isIndeterminate = false
            max = 100
            visibility = View.GONE
        }
        root.addView(web, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT,
            FrameLayout.LayoutParams.MATCH_PARENT
        ))
        root.addView(progress, FrameLayout.LayoutParams(
            FrameLayout.LayoutParams.MATCH_PARENT, 6
        ))
        setContentView(root)

        with(web.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true
            cacheMode = WebSettings.LOAD_NO_CACHE
            useWideViewPort = true
            loadWithOverviewMode = true
            try { mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW } catch (_: Throwable) {}
        }

        web.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                progress.visibility = if (newProgress in 1..99) View.VISIBLE else View.GONE
                progress.progress = newProgress
            }
        }
        web.webViewClient = object : WebViewClient() {
            override fun onReceivedError(v: WebView, req: WebResourceRequest, err: WebResourceError) {
                if (req.isForMainFrame)
                    Toast.makeText(this@CameraActivity, "Camera error: ${err.description}", Toast.LENGTH_SHORT).show()
            }
            override fun onReceivedHttpError(v: WebView, req: WebResourceRequest, resp: WebResourceResponse) {
                if (req.isForMainFrame)
                    Toast.makeText(this@CameraActivity, "HTTP ${resp.statusCode} ${resp.reasonPhrase}", Toast.LENGTH_SHORT).show()
            }
        }

        val url = ConnectionConfig.cameraUrl(this)
        web.loadUrl(url)
    }

    override fun onResume() { super.onResume(); try { web.onResume() } catch (_: Throwable) {} }
    override fun onPause()  { try { web.onPause() } catch (_: Throwable) {}; super.onPause() }
    override fun onDestroy(){ try { web.destroy() } catch (_: Throwable) {}; super.onDestroy() }
}
