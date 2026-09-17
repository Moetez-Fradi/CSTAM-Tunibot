package com.example.deliverybot

import android.content.Context
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.ProgressBar
import android.widget.TextView
import androidx.fragment.app.Fragment

/**
 * Fragment displaying the Streamlit Dashboard.
 * Caches the last loaded HTML for offline viewing.
 */
class DashboardFragment : Fragment() {

    private lateinit var webView: WebView
    private lateinit var progressBar: ProgressBar
    private lateinit var offlineNotice: TextView
    
    private var dashboardUrl: String = ""
    
    companion object {
        private const val ARG_URL = "dashboard_url"
        private const val PREFS_NAME = "dashboard_cache"
        private const val KEY_CACHED_HTML = "cached_html"
        private const val KEY_CACHED_URL = "cached_url"
        
        fun newInstance(url: String): DashboardFragment {
            return DashboardFragment().apply {
                arguments = Bundle().apply {
                    putString(ARG_URL, url)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        dashboardUrl = arguments?.getString(ARG_URL) ?: ""
    }

    override fun onCreateView(
        inflater: LayoutInflater,
        container: ViewGroup?,
        savedInstanceState: Bundle?
    ): View? {
        return inflater.inflate(R.layout.fragment_dashboard, container, false)
    }

    override fun onViewCreated(view: View, savedInstanceState: Bundle?) {
        super.onViewCreated(view, savedInstanceState)
        
        webView = view.findViewById(R.id.dashboardWebView)
        progressBar = view.findViewById(R.id.dashboardProgress)
        offlineNotice = view.findViewById(R.id.txtOfflineNotice)

        setupWebView()
        loadDashboard()
    }

    private fun setupWebView() {
        webView.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            loadWithOverviewMode = true
            useWideViewPort = true
            cacheMode = WebSettings.LOAD_DEFAULT
            // Enable zoom controls
            builtInZoomControls = true
            displayZoomControls = false
            setSupportZoom(true)
        }
        
        // Tap overlay to open fullscreen dashboard
        val clickOverlay = requireView().findViewById<View>(R.id.dashboardClickOverlay)
        clickOverlay.setOnClickListener {
            openFullscreenDashboard()
        }
        
        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                progressBar.visibility = View.GONE
                offlineNotice.visibility = View.GONE
                
                // Cache the page HTML for offline use
                view?.evaluateJavascript(
                    "(function() { return document.documentElement.outerHTML; })();"
                ) { html ->
                    if (html != null && html.length > 100) {
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
    }
    
    private fun openFullscreenDashboard() {
        val intent = android.content.Intent(requireContext(), DashboardActivity::class.java)
        intent.putExtra(DashboardActivity.EXTRA_DASHBOARD_URL, dashboardUrl)
        startActivity(intent)
    }

    private fun loadDashboard() {
        if (dashboardUrl.isNotEmpty()) {
            progressBar.visibility = View.VISIBLE
            offlineNotice.visibility = View.GONE
            webView.loadUrl(dashboardUrl)
        } else {
            // No URL, try cached
            loadCachedVersion()
        }
    }

    private fun loadCachedVersion() {
        val prefs = requireContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val cachedHtml = prefs.getString(KEY_CACHED_HTML, null)
        
        if (cachedHtml != null && cachedHtml.length > 100) {
            progressBar.visibility = View.GONE
            offlineNotice.visibility = View.VISIBLE
            // Unescape the JSON string
            val unescaped = cachedHtml
                .removeSurrounding("\"")
                .replace("\\n", "\n")
                .replace("\\\"", "\"")
                .replace("\\/", "/")
            webView.loadDataWithBaseURL(null, unescaped, "text/html", "UTF-8", null)
        } else {
            progressBar.visibility = View.GONE
            offlineNotice.text = "No cached data available"
            offlineNotice.visibility = View.VISIBLE
        }
    }

    private fun saveCachedHtml(html: String) {
        try {
            val prefs = requireContext().getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
            prefs.edit()
                .putString(KEY_CACHED_HTML, html)
                .putString(KEY_CACHED_URL, dashboardUrl)
                .apply()
        } catch (e: Exception) {
            // Ignore cache errors
        }
    }

    fun updateUrl(newUrl: String) {
        dashboardUrl = newUrl
        if (::webView.isInitialized) {
            loadDashboard()
        }
    }
}
