package ca.radar.cineplex

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import ca.radar.cineplex.data.AppSettings
import ca.radar.cineplex.data.ChatResponse
import ca.radar.cineplex.data.ConnectionSettings
import ca.radar.cineplex.data.EventItem
import ca.radar.cineplex.data.RadarApi
import ca.radar.cineplex.data.RadarItem
import ca.radar.cineplex.data.Suggestion
import ca.radar.cineplex.data.TheatrePreference
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class RadarUiState(
    val settings: ConnectionSettings = ConnectionSettings(),
    val radar: List<RadarItem> = emptyList(),
    val events: List<EventItem> = emptyList(),
    val suggestions: List<Suggestion> = emptyList(),
    val theatrePreferences: List<TheatrePreference> = emptyList(),
    val loading: Boolean = false,
    val error: String? = null,
    val message: String? = null,
    val chatReply: ChatResponse? = null,
)

class RadarViewModel(application: Application) : AndroidViewModel(application) {
    private val store = AppSettings(application)
    private val _state = MutableStateFlow(RadarUiState(settings = store.load()))
    val state: StateFlow<RadarUiState> = _state.asStateFlow()
    private val api = RadarApi(settingsProvider = { store.load() })

    init {
        if (_state.value.settings.backendUrl.isNotBlank()) refresh()
    }

    fun refresh() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        runCatching {
            val radar = async { api.radar() }
            val events = async { api.events() }
            val suggestions = async { api.suggestions() }
            val theatres = async { api.theatrePreferences() }
            RadarRefresh(radar.await(), events.await(), suggestions.await(), theatres.await())
        }.onSuccess { result ->
            _state.update {
                it.copy(
                    radar = result.radar,
                    events = result.events,
                    suggestions = result.suggestions,
                    theatrePreferences = result.theatres,
                    loading = false,
                )
            }
        }.onFailure { failure ->
            _state.update { it.copy(loading = false, error = failure.message ?: "Connection failed") }
        }
    }

    fun saveSettings(value: ConnectionSettings) {
        store.save(value)
        _state.update { it.copy(settings = store.load(), message = "Settings saved", error = null) }
        refresh()
    }

    fun saveTheatrePreferences(enabledNames: List<String>) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        runCatching { api.updateTheatrePreferences(enabledNames) }
            .onSuccess { theatres ->
                _state.update {
                    it.copy(
                        theatrePreferences = theatres,
                        loading = false,
                        message = "Theatre watch list saved",
                    )
                }
            }
            .onFailure { failure ->
                _state.update { it.copy(loading = false, error = failure.message) }
            }
    }

    fun updateRadar(
        item: RadarItem,
        partySize: Int,
        armedMode: String,
        theatreNames: List<String>,
        formats: List<String>,
        dates: List<String>,
        timeStart: String?,
        timeEnd: String?,
    ) = action("Radar updated") {
        api.updateRadar(item.id, partySize, armedMode, theatreNames, formats, dates, timeStart, timeEnd)
    }

    fun deleteRadar(id: Int) = action("Watch removed") { api.deleteRadar(id) }
    fun acceptSuggestion(id: Int) = action("Added to radar") { api.acceptSuggestion(id) }
    fun declineSuggestion(id: Int) = action("Suggestion dismissed") { api.declineSuggestion(id) }
    fun approveBooking(id: Int) = action("Purchase approved") { api.approveBooking(id) }
    fun cancelBooking(id: Int) = action("Booking cancelled") { api.cancelBooking(id) }

    fun sendChat(text: String) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null, chatReply = null) }
        runCatching { api.chat(text) }
            .onSuccess { response ->
                _state.update { it.copy(loading = false, chatReply = response) }
                if (response.radarItem != null) refresh()
            }
            .onFailure { failure -> _state.update { it.copy(loading = false, error = failure.message) } }
    }

    fun testNotification() = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        runCatching { api.testNotification() }
            .onSuccess { sent ->
                _state.update {
                    it.copy(
                        loading = false,
                        message = if (sent) "Test notification sent" else "Backend has no active ntfy topic",
                    )
                }
            }
            .onFailure { failure -> _state.update { it.copy(loading = false, error = failure.message) } }
    }

    fun clearNotice() = _state.update { it.copy(error = null, message = null) }

    private fun action(success: String, block: suspend () -> Any) = viewModelScope.launch {
        _state.update { it.copy(loading = true, error = null) }
        runCatching { block() }
            .onSuccess { _state.update { it.copy(loading = false, message = success) }; refresh() }
            .onFailure { failure -> _state.update { it.copy(loading = false, error = failure.message) } }
    }
}

private data class RadarRefresh(
    val radar: List<RadarItem>,
    val events: List<EventItem>,
    val suggestions: List<Suggestion>,
    val theatres: List<TheatrePreference>,
)
