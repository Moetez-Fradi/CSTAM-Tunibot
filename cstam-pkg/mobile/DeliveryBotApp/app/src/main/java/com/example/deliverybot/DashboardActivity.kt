package com.example.deliverybot

import android.app.DownloadManager
import android.content.Context
import android.net.Uri
import android.os.Bundle
import android.os.Environment
import android.view.View
import android.webkit.CookieManager
import android.webkit.DownloadListener
import android.webkit.URLUtil
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ImageButton
import android.widget.ProgressBar
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity

/**
 * Activity to display the Streamlit Dashboard inside a WebView.
 * Supports offline caching of the last loaded page.
 */
class DashboardActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var txtOffline: TextView
    private lateinit var btnBack: ImageButton
    private lateinit var btnRefresh: ImageButton

    private var dashboardUrl: String = ""

    companion object {
        const val EXTRA_DASHBOARD_URL = "dashboard_url"
        private const val PREFS_NAME = "dashboard_cache"
        private const val KEY_CACHED_HTML = "cached_html"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_dashboard)

        // Get URL from intent or use default
        dashboardUrl = intent.getStringExtra(EXTRA_DASHBOARD_URL) 
            ?: "http://${Prefs.getRawIp(this)}:8501"

        bindViews()
        setupWebView()
        setupClickListeners()
        loadDashboard()
    }

    private fun bindViews() {
        webView = findViewById(R.id.dashboardWebView)
        progressBar = findViewById(R.id.progressBar)
        txtOffline = findViewById(R.id.txtOffline)
        btnBack = findViewById(R.id.btnBack)
        btnRefresh = findViewById(R.id.btnRefresh)
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            builtInZoomControls = true
            displayZoomControls = false
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
                txtOffline.visibility = View.GONE

                // Cache the page HTML for offline use
                view?.evaluateJavascript(
                    "(function() { return document.documentElement.outerHTML; })();"
                ) { html ->
                    if (html != null && html.length > 500) {
                        saveCachedHtml(html)
                    }
                }
            }

            override fun onReceivedError(
                view: WebView?,
                errorCode: Int,
                description: String?,
                failingUrl: String?
            ) {
                // Try to load cached version
                loadCachedVersion()
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onProgressChanged(view: WebView?, newProgress: Int) {
                if (newProgress < 100) {
                    progressBar.visibility = View.VISIBLE
                } else {
                    progressBar.visibility = View.GONE
                }
            }
        }
        
        // Handle file downloads (PDF, Excel, etc.)
        webView.setDownloadListener { url, userAgent, contentDisposition, mimeType, contentLength ->
            try {
                val request = DownloadManager.Request(Uri.parse(url))
                
                // Get filename from content disposition or URL
                val fileName = URLUtil.guessFileName(url, contentDisposition, mimeType)
                
                // Set download properties
                request.setMimeType(mimeType)
                request.addRequestHeader("cookie", CookieManager.getInstance().getCookie(url))
                request.addRequestHeader("User-Agent", userAgent)
                request.setDescription("Downloading file...")
                request.setTitle(fileName)
                request.allowScanningByMediaScanner()
                request.setNotificationVisibility(DownloadManager.Request.VISIBILITY_VISIBLE_NOTIFY_COMPLETED)
                request.setDestinationInExternalPublicDir(Environment.DIRECTORY_DOWNLOADS, fileName)
                
                // Start download
                val dm = getSystemService(Context.DOWNLOAD_SERVICE) as DownloadManager
                dm.enqueue(request)
                
                Toast.makeText(this, "📥 Downloading: $fileName", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                Toast.makeText(this, "❌ Download failed: ${e.message}", Toast.LENGTH_LONG).show()
            }
        }
    }

    private fun setupClickListeners() {
        // Back button always closes the activity and returns to main screen
        btnBack.setOnClickListener {
            finish()
        }

        btnRefresh.setOnClickListener {
            progressBar.visibility = View.VISIBLE
            txtOffline.visibility = View.GONE
            webView.reload()
        }
    }

    private fun loadDashboard() {
        progressBar.visibility = View.VISIBLE
        txtOffline.visibility = View.GONE
        webView.loadUrl(dashboardUrl)
    }

    private fun loadCachedVersion() {
        val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val cachedHtml = prefs.getString(KEY_CACHED_HTML, null)

        progressBar.visibility = View.GONE

        if (cachedHtml != null && cachedHtml.length > 500) {
            txtOffline.visibility = View.VISIBLE
            // Unescape the JSON string
            val unescaped = cachedHtml
                .removeSurrounding("\"")
                .replace("\\n", "\n")
                .replace("\\\"", "\"")
                .replace("\\/", "/")
            webView.loadDataWithBaseURL(dashboardUrl, unescaped, "text/html", "UTF-8", null)
        } else {
            txtOffline.text = "❌ Dashboard not available (No cached data)"
            txtOffline.visibility = View.VISIBLE
        }
    }

    private fun saveCachedHtml(html: String) {
        try {
            val prefs = getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit()
                .putString(KEY_CACHED_HTML, html)
                .apply()
        } catch (e: Exception) {
            // Ignore cache errors
        }
    }

    override fun onBackPressed() {
        if (webView.canGoBack()) {
            webView.goBack()
        } else {
            super.onBackPressed()
        }
    }
}
