package ca.radar.cineplex.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException

class RadarApiException(val status: Int?, message: String) : IOException(message)

class RadarApi(
    private val settingsProvider: () -> ConnectionSettings,
    private val client: OkHttpClient = OkHttpClient(),
) {
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    private val mediaType = "application/json; charset=utf-8".toMediaType()

    private suspend fun request(path: String, method: String = "GET", body: String? = null): String =
        withContext(Dispatchers.IO) {
            val settings = settingsProvider()
            if (settings.backendUrl.isBlank() || settings.bearerToken.isBlank()) {
                throw RadarApiException(null, "Set the backend URL and bearer token in Settings.")
            }
            val builder = Request.Builder()
                .url(settings.backendUrl.trimEnd('/') + path)
                .header("Authorization", "Bearer ${settings.bearerToken}")
                .header("Accept", "application/json")
            when (method) {
                "POST" -> builder.post((body ?: "{}").toRequestBody(mediaType))
                "PUT" -> builder.put((body ?: "{}").toRequestBody(mediaType))
                "PATCH" -> builder.patch((body ?: "{}").toRequestBody(mediaType))
                "DELETE" -> builder.delete()
            }
            client.newCall(builder.build()).execute().use { response ->
                val content = response.body.string()
                if (!response.isSuccessful) {
                    val detail = runCatching { json.decodeFromString<ApiError>(content).detail.toString() }.getOrNull()
                    throw RadarApiException(response.code, detail ?: "Backend returned ${response.code}")
                }
                content
            }
        }

    suspend fun radar(): List<RadarItem> = json.decodeFromString(request("/radar"))
    suspend fun events(): List<EventItem> = json.decodeFromString(request("/events"))
    suspend fun suggestions(): List<Suggestion> = json.decodeFromString(request("/suggestions?suggestion_status=pending"))
    suspend fun theatrePreferences(): List<TheatrePreference> =
        json.decodeFromString(request("/settings/theatres"))

    suspend fun updateTheatrePreferences(enabledNames: List<String>): List<TheatrePreference> {
        val body = buildJsonObject {
            putJsonArray("enabled_names") {
                enabledNames.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) }
            }
        }
        return json.decodeFromString(request("/settings/theatres", "PUT", body.toString()))
    }

    suspend fun updateRadar(
        id: Int,
        partySize: Int,
        armedMode: String,
        theatreNames: List<String>,
        formats: List<String>,
        dates: List<String>,
        timeStart: String?,
        timeEnd: String?,
    ): RadarItem {
        val body = buildJsonObject {
            put("party_size", partySize)
            put("armed_mode", armedMode)
            putJsonArray("preferred_theatre_names") { theatreNames.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
            putJsonArray("format_preference") { formats.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
            putJsonArray("preferred_dates") { dates.forEach { add(kotlinx.serialization.json.JsonPrimitive(it)) } }
            if (timeStart == null) put("time_start", kotlinx.serialization.json.JsonNull) else put("time_start", timeStart)
            if (timeEnd == null) put("time_end", kotlinx.serialization.json.JsonNull) else put("time_end", timeEnd)
        }
        return json.decodeFromString(request("/radar/$id", "PATCH", body.toString()))
    }

    suspend fun deleteRadar(id: Int) { request("/radar/$id", "DELETE") }
    suspend fun acceptSuggestion(id: Int): RadarItem = json.decodeFromString(request("/suggestions/$id/accept", "POST"))
    suspend fun declineSuggestion(id: Int): Suggestion = json.decodeFromString(request("/suggestions/$id/decline", "POST"))
    suspend fun approveBooking(id: Int): Booking = json.decodeFromString(request("/bookings/$id/approve", "POST"))
    suspend fun cancelBooking(id: Int): Booking = json.decodeFromString(request("/bookings/$id/cancel", "POST"))

    suspend fun chat(message: String): ChatResponse {
        val body = buildJsonObject { put("message", message) }
        return json.decodeFromString(request("/chat", "POST", body.toString()))
    }

    suspend fun testNotification(): Boolean {
        val response = request("/notifications/test", "POST")
        return response.contains("\"sent\":true")
    }

    suspend fun registerPushEndpoint(endpoint: String) {
        val body = buildJsonObject { put("endpoint", endpoint) }
        request("/push/register", "POST", body.toString())
    }
}
