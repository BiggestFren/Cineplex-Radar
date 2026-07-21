package ca.radar.cineplex.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject

@Serializable
data class RadarItem(
    val id: Int,
    @SerialName("movie_query") val movieQuery: String,
    @SerialName("movie_id") val movieId: Int? = null,
    @SerialName("preferred_theatre_ids") val preferredTheatreIds: List<Int> = emptyList(),
    @SerialName("preferred_theatre_names") val preferredTheatreNames: List<String> = emptyList(),
    @SerialName("format_preference") val formatPreference: List<String> = emptyList(),
    @SerialName("preferred_dates") val preferredDates: List<String> = emptyList(),
    @SerialName("time_start") val timeStart: String? = null,
    @SerialName("time_end") val timeEnd: String? = null,
    @SerialName("first_day_bonus") val firstDayBonus: Boolean = true,
    @SerialName("party_size") val partySize: Int = 1,
    @SerialName("armed_mode") val armedMode: String = "notify_only",
    @SerialName("created_at") val createdAt: String = "",
    @SerialName("updated_at") val updatedAt: String = "",
)

@Serializable
data class EventItem(
    val id: Int,
    val type: String,
    val title: String,
    val message: String,
    val payload: JsonObject = JsonObject(emptyMap()),
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class Suggestion(
    val id: Int,
    @SerialName("tmdb_id") val tmdbId: Int,
    val title: String,
    @SerialName("release_date") val releaseDate: String? = null,
    val pitch: String,
    val status: String,
    val payload: JsonObject = JsonObject(emptyMap()),
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class Booking(
    val id: Int,
    @SerialName("radar_id") val radarId: Int? = null,
    val state: String,
    val showtime: JsonObject = JsonObject(emptyMap()),
    val seats: List<String> = emptyList(),
    @SerialName("deep_link") val deepLink: String? = null,
    @SerialName("hold_expires_at") val holdExpiresAt: String? = null,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
)

@Serializable
data class ChatResponse(
    val reply: String,
    @SerialName("needs_clarification") val needsClarification: Boolean = false,
    @SerialName("radar_item") val radarItem: RadarItem? = null,
)

@Serializable
data class ApiError(val detail: JsonElement? = null)

