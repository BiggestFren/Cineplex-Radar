package ca.radar.cineplex.push

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat
import ca.radar.cineplex.MainActivity
import ca.radar.cineplex.data.AppSettings
import ca.radar.cineplex.data.RadarApi
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.unifiedpush.android.connector.FailedReason
import org.unifiedpush.android.connector.PushService
import org.unifiedpush.android.connector.data.PushEndpoint
import org.unifiedpush.android.connector.data.PushMessage

class RadarPushService : PushService() {
    override fun onNewEndpoint(endpoint: PushEndpoint, instance: String) {
        val settings = AppSettings(this)
        settings.savePushEndpoint(endpoint.url)
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            runCatching {
                RadarApi(settingsProvider = { settings.load() }).registerPushEndpoint(endpoint.url)
            }.onFailure {
                notify("Radar push setup incomplete", "Save the backend URL and token, then reconnect push.", "radar://settings")
            }
        }
    }

    override fun onMessage(message: PushMessage, instance: String) {
        val raw = message.content.decodeToString()
        val parsed = runCatching { Json.parseToJsonElement(raw).jsonObject }.getOrNull()
        val title = parsed?.get("title")?.jsonPrimitive?.content ?: "Radar alert"
        val body = parsed?.get("message")?.jsonPrimitive?.content ?: raw
        val action = parsed?.get("action")?.jsonPrimitive?.content ?: "radar://events"
        notify(title, body, action)
    }

    override fun onRegistrationFailed(reason: FailedReason, instance: String) {
        notify("Radar push setup failed", reason.toString(), "radar://settings")
    }

    override fun onUnregistered(instance: String) {
        notify("Radar push disconnected", "Reconnect UnifiedPush in Settings.", "radar://settings")
    }

    private fun notify(title: String, body: String, action: String) {
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(CHANNEL, "Radar drops and approvals", NotificationManager.IMPORTANCE_HIGH).apply {
            description = "Time-sensitive movie ticket alerts and booking approvals"
        }
        manager.createNotificationChannel(channel)
        val intent = Intent(this, MainActivity::class.java).apply { data = Uri.parse(action); flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP }
        val pending = PendingIntent.getActivity(this, action.hashCode(), intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        manager.notify(
            System.currentTimeMillis().toInt(),
            NotificationCompat.Builder(this, CHANNEL)
                .setSmallIcon(android.R.drawable.ic_dialog_info)
                .setContentTitle(title)
                .setContentText(body)
                .setStyle(NotificationCompat.BigTextStyle().bigText(body))
                .setPriority(NotificationCompat.PRIORITY_HIGH)
                .setAutoCancel(true)
                .setContentIntent(pending)
                .build(),
        )
    }

    companion object { private const val CHANNEL = "radar-urgent" }
}
