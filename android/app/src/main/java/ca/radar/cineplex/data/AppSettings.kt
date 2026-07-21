package ca.radar.cineplex.data

import android.content.Context

data class ConnectionSettings(
    val backendUrl: String = "",
    val bearerToken: String = "",
    val ntfyTopic: String = "",
)

class AppSettings(context: Context) {
    private val prefs = context.getSharedPreferences("radar-settings", Context.MODE_PRIVATE)

    fun load() = ConnectionSettings(
        backendUrl = prefs.getString("backend_url", "") ?: "",
        bearerToken = prefs.getString("bearer_token", "") ?: "",
        ntfyTopic = prefs.getString("ntfy_topic", "") ?: "",
    )

    fun save(value: ConnectionSettings) {
        prefs.edit()
            .putString("backend_url", value.backendUrl.trim().trimEnd('/'))
            .putString("bearer_token", value.bearerToken.trim())
            .putString("ntfy_topic", value.ntfyTopic.trim())
            .apply()
    }

    fun savePushEndpoint(endpoint: String) {
        prefs.edit().putString("unified_push_endpoint", endpoint).apply()
    }
}

