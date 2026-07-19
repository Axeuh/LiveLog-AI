package com.axeuh.health.monitor

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.SslErrorHandler
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebView
import android.webkit.WebViewClient
import android.webkit.WebChromeClient
import android.webkit.ValueCallback
import android.net.http.SslError
import androidx.activity.ComponentActivity
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts

/**
 * 手机端 WebView Activity — 全屏托管前端移动网页
 *
 * 布局：
 *   - WebView 填充整个屏幕，无原生底部导航
 *   - 底部导航由前端 HTML/CSS 在 WebView 内实现
 *
 * 导航逻辑：
 *   - 所有 5 个 tab（聊天/看板/文件/报告/设置）由前端 switchTab() 管理
 *   - 设置 tab 显示引导页，点击"打开系统设置"按钮触发 axeuh://open-settings
 *   - scheme 由 WebViewClient.shouldOverrideUrlLoading 拦截
 *   - 加载失败时显示本地资产错误页面
 */
class MobileActivity : ComponentActivity() {

    private var webViewRef: WebView? = null
    private var mainUrl: String = ""
    private var uploadMessage: ValueCallback<Array<Uri>>? = null

    private val fileChooserLauncher = registerForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        if (uploadMessage != null) {
            val uris = if (result.resultCode == RESULT_OK && result.data != null) {
                WebChromeClient.FileChooserParams.parseResult(result.resultCode, result.data)
            } else {
                null
            }
            uploadMessage?.onReceiveValue(uris)
            uploadMessage = null
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // 返回键：WebView 可后退则后退，否则退出
        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                val wv = webViewRef
                if (wv != null && wv.canGoBack()) {
                    wv.goBack()
                } else {
                    isEnabled = false
                    onBackPressedDispatcher.onBackPressed()
                }
            }
        })

        val token = intent.getStringExtra("token") ?: ""
        val baseUrl = intent.getStringExtra("baseUrl") ?: com.axeuh.health.monitor.config.ServerConfig.BASE_URL
        mainUrl = "$baseUrl/mobile/?token=$token"
        val finalMainUrl = mainUrl

        val webView = WebView(this).apply {
            webViewRef = this
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.MATCH_PARENT
            )

            // WebView 配置
            settings.apply {
                javaScriptEnabled = true
                domStorageEnabled = true
                loadWithOverviewMode = true
                useWideViewPort = true
                setSupportZoom(true)
                allowFileAccess = true
                allowContentAccess = true
            }

            // Scheme 拦截 + 错误处理
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(
                    view: WebView,
                    request: WebResourceRequest
                ): Boolean {
                    val requestUrl = request.url.toString()
                    when {
                        requestUrl.startsWith("axeuh://open-settings") -> {
                            startActivity(Intent(this@MobileActivity, SettingsActivity::class.java))
                            return true
                        }
                        requestUrl.startsWith("axeuh://open-debug") -> {
                            startActivity(Intent(this@MobileActivity, MainActivity::class.java).apply {
                                putExtra("showDebugPanel", true)
                                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            })
                            return true
                        }
                        requestUrl.startsWith("axeuh://retry") -> {
                            view.loadUrl(finalMainUrl)
                            return true
                        }
                    }
                    return false
                }

                // 主页面加载失败 → 显示本地错误页面
                override fun onReceivedError(
                    view: WebView,
                    errorCode: Int,
                    description: String,
                    failingUrl: String?
                ) {
                    if (failingUrl == finalMainUrl || failingUrl?.startsWith(baseUrl) == true) {
                        val errorAsset = "file:///android_asset/error_page.html?code=$errorCode&msg=${Uri.encode(description)}"
                        view.loadUrl(errorAsset)
                    }
                }

                // HTTP 非200 → 显示本地错误页面
                override fun onReceivedHttpError(
                    view: WebView,
                    request: WebResourceRequest,
                    errorResponse: WebResourceResponse
                ) {
                    val code = errorResponse.statusCode
                    val reqUrl = request.url.toString()
                    if ((code < 200 || code >= 300) && (reqUrl == finalMainUrl || reqUrl.startsWith(baseUrl))) {
                        view.loadUrl("file:///android_asset/error_page.html?code=$code")
                    }
                }
            }

            // 文件上传支持（WebChromeClient 处理 <input type="file">）
            webChromeClient = object : WebChromeClient() {
                override fun onShowFileChooser(
                    webView: WebView?,
                    filePathCallback: ValueCallback<Array<Uri>>?,
                    fileChooserParams: FileChooserParams?
                ): Boolean {
                    uploadMessage = filePathCallback
                    val intent = fileChooserParams?.createIntent() ?: Intent(Intent.ACTION_GET_CONTENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE)
                        type = "*/*"
                    }
                    fileChooserLauncher.launch(Intent.createChooser(intent, "选择文件"))
                    return true
                }
            }

            loadUrl(finalMainUrl)
        }

        setContentView(webView)
    }

    override fun onDestroy() {
        webViewRef?.destroy()
        super.onDestroy()
    }
}
