package com.axeuh.health.monitor.config

import android.content.Context

object ServerConfig {
    private const val PREFS_NAME = "axeuh_prefs"
    private const val KEY_SERVER_URL = "server_url"
    private const val DEFAULT_SERVER_URL = "https://localhost:8767"

    var BASE_URL: String = DEFAULT_SERVER_URL
        private set

    fun init(context: Context) {
        val prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        BASE_URL = prefs.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL) ?: DEFAULT_SERVER_URL
    }

    fun update(url: String) {
        BASE_URL = url
    }
}
