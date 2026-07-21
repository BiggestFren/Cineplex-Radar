package ca.radar.cineplex

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ChatBubbleOutline
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Radar
import androidx.compose.material.icons.outlined.Settings
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.viewmodel.compose.viewModel
import ca.radar.cineplex.data.ConnectionSettings
import ca.radar.cineplex.data.EventItem
import ca.radar.cineplex.data.RadarItem
import ca.radar.cineplex.data.Suggestion
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive
import org.unifiedpush.android.connector.UnifiedPush

enum class AppScreen(val label: String) { Feed("Feed"), Radar("Radar"), Chat("Chat"), Settings("Settings") }

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent { RadarApp(initialScreen = screenFromIntent(intent)) }
    }

    private fun screenFromIntent(intent: Intent): AppScreen = when (intent.data?.host) {
        "settings" -> AppScreen.Settings
        "suggestions", "events", "bookings" -> AppScreen.Feed
        else -> AppScreen.Feed
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RadarApp(initialScreen: AppScreen = AppScreen.Feed, model: RadarViewModel = viewModel()) {
    val state by model.state.collectAsState()
    var screen by rememberSaveable { mutableStateOf(initialScreen) }
    val snackbar = remember { SnackbarHostState() }
    val context = LocalContext.current
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    LaunchedEffect(Unit) {
        if (android.os.Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) permissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
    }
    LaunchedEffect(state.error, state.message) {
        (state.error ?: state.message)?.let { snackbar.showSnackbar(it); model.clearNotice() }
    }

    MaterialTheme(colorScheme = radarColors) {
        Scaffold(
            topBar = {
                TopAppBar(
                    title = { Column { Text("RADAR", fontWeight = FontWeight.Black); Text(screen.label, style = MaterialTheme.typography.labelSmall, color = Color(0xFF9BA6B2)) } },
                    colors = TopAppBarDefaults.topAppBarColors(containerColor = Color(0xFF090B10)),
                )
            },
            snackbarHost = { SnackbarHost(snackbar) },
            bottomBar = {
                NavigationBar(containerColor = Color(0xFF10141C)) {
                    AppScreen.entries.forEach { destination ->
                        val icon = when (destination) {
                            AppScreen.Feed -> Icons.Outlined.Notifications
                            AppScreen.Radar -> Icons.Outlined.Radar
                            AppScreen.Chat -> Icons.Outlined.ChatBubbleOutline
                            AppScreen.Settings -> Icons.Outlined.Settings
                        }
                        NavigationBarItem(selected = screen == destination, onClick = { screen = destination }, icon = { androidx.compose.material3.Icon(icon, destination.label) }, label = { Text(destination.label) })
                    }
                }
            },
        ) { padding ->
            Box(Modifier.fillMaxSize().padding(padding)) {
                when (screen) {
                    AppScreen.Feed -> FeedScreen(state.events, state.suggestions, model)
                    AppScreen.Radar -> RadarScreen(state.radar, model)
                    AppScreen.Chat -> ChatScreen(state.chatReply?.reply, state.chatReply?.needsClarification == true, model)
                    AppScreen.Settings -> SettingsScreen(state.settings, model)
                }
                if (state.loading) CircularProgressIndicator(Modifier.align(Alignment.TopEnd).padding(16.dp))
            }
        }
    }
}

private val radarColors = darkColorScheme(
    primary = Color(0xFFFFC247),
    secondary = Color(0xFF44D7B6),
    background = Color(0xFF090B10),
    surface = Color(0xFF151A23),
    error = Color(0xFFFF6B6B),
)

@Composable
private fun FeedScreen(events: List<EventItem>, suggestions: List<Suggestion>, model: RadarViewModel) {
    LazyColumn(Modifier.fillMaxSize().padding(horizontal = 16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Spacer(Modifier.height(4.dp)); SectionLabel("ACTION NEEDED") }
        items(suggestions, key = { "suggestion-${it.id}" }) { SuggestionCard(it, model) }
        item { SectionLabel("LATEST SIGNALS") }
        if (events.isEmpty()) item { EmptyState("No detections yet", "Add a watch, then Radar will surface new dates, theatres, formats, and booking plans here.") }
        items(events, key = { "event-${it.id}" }) { EventCard(it, model) }
        item { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun SuggestionCard(item: Suggestion, model: RadarViewModel) {
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF19232B))) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(item.title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
            item.releaseDate?.let { Text("Opens $it", color = MaterialTheme.colorScheme.secondary) }
            Text(item.pitch)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { model.acceptSuggestion(item.id) }) { Text("Add to radar") }
                OutlinedButton(onClick = { model.declineSuggestion(item.id) }) { Text("Dismiss") }
            }
        }
    }
}

@Composable
private fun EventCard(item: EventItem, model: RadarViewModel) {
    val context = LocalContext.current
    val bookingId = item.payload["booking_id"]?.jsonPrimitive?.intOrNull
    val deepLink = item.payload["deep_link"]?.jsonPrimitive?.content
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF151A23))) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(item.type.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
            Text(item.title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(item.message, color = Color(0xFFD7DCE2))
            Text(item.createdAt.replace('T', ' ').take(16), style = MaterialTheme.typography.labelSmall, color = Color(0xFF87919D))
            if (bookingId != null) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        if (!deepLink.isNullOrBlank()) context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(deepLink)))
                        else model.approveBooking(bookingId)
                    }) { Text(if (deepLink != null) "Continue at Cineplex" else "Approve purchase") }
                    OutlinedButton(onClick = { model.cancelBooking(bookingId) }) { Text("Cancel") }
                }
            }
        }
    }
}

@Composable
private fun RadarScreen(items: List<RadarItem>, model: RadarViewModel) {
    var editing by remember { mutableStateOf<RadarItem?>(null) }
    LazyColumn(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { Text("Your watches", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold) }
        if (items.isEmpty()) item { EmptyState("Nothing on radar", "Use Chat to describe a movie, format, theatre, time window, and party size.") }
        items(items, key = { it.id }) { item ->
            Card(onClick = { editing = item }, colors = CardDefaults.cardColors(containerColor = Color(0xFF151A23))) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(item.movieQuery, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    Text(item.formatPreference.joinToString(" · ").ifBlank { "Any format" }, color = MaterialTheme.colorScheme.primary)
                    Text("${item.partySize} seat${if (item.partySize == 1) "" else "s"} · ${item.armedMode.replace('_', ' ')}")
                    if (item.preferredTheatreNames.isNotEmpty()) Text(item.preferredTheatreNames.joinToString(), color = Color(0xFF9BA6B2))
                }
            }
        }
    }
    editing?.let {
        RadarEditDialog(
            it,
            onDismiss = { editing = null },
            onSave = { party, mode, theatres, formats, dates, start, end ->
                model.updateRadar(it, party, mode, theatres, formats, dates, start, end)
                editing = null
            },
            onDelete = { model.deleteRadar(it.id); editing = null },
        )
    }
}

@Composable
private fun RadarEditDialog(
    item: RadarItem,
    onDismiss: () -> Unit,
    onSave: (Int, String, List<String>, List<String>, List<String>, String?, String?) -> Unit,
    onDelete: () -> Unit,
) {
    var party by remember { mutableIntStateOf(item.partySize) }
    var mode by remember { mutableStateOf(item.armedMode) }
    var theatres by remember { mutableStateOf(item.preferredTheatreNames.joinToString(", ")) }
    var formats by remember { mutableStateOf(item.formatPreference.joinToString(", ")) }
    var dates by remember { mutableStateOf(item.preferredDates.joinToString(", ")) }
    var timeStart by remember { mutableStateOf(item.timeStart.orEmpty()) }
    var timeEnd by remember { mutableStateOf(item.timeEnd.orEmpty()) }
    fun split(value: String) = value.split(',').map(String::trim).filter(String::isNotBlank)
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(item.movieQuery) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text("Party size")
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(onClick = { if (party > 1) party-- }) { Text("−") }
                    Text("$party", style = MaterialTheme.typography.titleLarge)
                    OutlinedButton(onClick = { if (party < 8) party++ }) { Text("+") }
                }
                Text("Mode")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf("notify_only", "assisted_buy").forEach { value ->
                        if (mode == value) Button(onClick = { mode = value }) { Text(value.replace('_', ' ')) }
                        else OutlinedButton(onClick = { mode = value }) { Text(value.replace('_', ' ')) }
                    }
                }
                OutlinedTextField(theatres, { theatres = it }, label = { Text("Theatres (comma separated)") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(formats, { formats = it }, label = { Text("Formats, best first") }, modifier = Modifier.fillMaxWidth())
                OutlinedTextField(dates, { dates = it }, label = { Text("Preferred dates (YYYY-MM-DD)") }, modifier = Modifier.fillMaxWidth())
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(timeStart, { timeStart = it }, label = { Text("From HH:MM") }, modifier = Modifier.weight(1f))
                    OutlinedTextField(timeEnd, { timeEnd = it }, label = { Text("To HH:MM") }, modifier = Modifier.weight(1f))
                }
            }
        },
        confirmButton = {
            Button(onClick = {
                onSave(party, mode, split(theatres), split(formats), split(dates), timeStart.ifBlank { null }, timeEnd.ifBlank { null })
            }) { Text("Save") }
        },
        dismissButton = { Row { TextButton(onClick = onDelete) { Text("Delete", color = MaterialTheme.colorScheme.error) }; TextButton(onClick = onDismiss) { Text("Close") } } },
    )
}

@Composable
private fun ChatScreen(reply: String?, clarify: Boolean, model: RadarViewModel) {
    var text by rememberSaveable { mutableStateOf("") }
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Tell Radar what to watch", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        Text("Try: “Watch the new Villeneuve movie, IMAX only, any Friday evening, two seats.”", color = Color(0xFF9BA6B2))
        OutlinedTextField(value = text, onValueChange = { text = it }, modifier = Modifier.fillMaxWidth().weight(1f), label = { Text("Message") }, minLines = 5)
        reply?.let { Card(colors = CardDefaults.cardColors(containerColor = if (clarify) Color(0xFF32291A) else Color(0xFF173028))) { Text(it, Modifier.padding(16.dp)) } }
        Button(onClick = { if (text.isNotBlank()) model.sendChat(text) }, modifier = Modifier.fillMaxWidth()) { Text("Send to Radar") }
    }
}

@Composable
private fun SettingsScreen(current: ConnectionSettings, model: RadarViewModel) {
    var backend by remember(current.backendUrl) { mutableStateOf(current.backendUrl) }
    var token by remember(current.bearerToken) { mutableStateOf(current.bearerToken) }
    var topic by remember(current.ntfyTopic) { mutableStateOf(current.ntfyTopic) }
    val context = LocalContext.current
    Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Connection", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
        OutlinedTextField(value = backend, onValueChange = { backend = it }, label = { Text("Backend HTTPS URL") }, placeholder = { Text("https://radar.example.com") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        OutlinedTextField(value = token, onValueChange = { token = it }, label = { Text("Bearer token") }, modifier = Modifier.fillMaxWidth(), singleLine = true, visualTransformation = PasswordVisualTransformation())
        OutlinedTextField(value = topic, onValueChange = { topic = it }, label = { Text("Private ntfy topic") }, modifier = Modifier.fillMaxWidth(), singleLine = true)
        Button(onClick = { model.saveSettings(ConnectionSettings(backend, token, topic)) }, modifier = Modifier.fillMaxWidth()) { Text("Save and connect") }
        OutlinedButton(
            onClick = {
                UnifiedPush.tryUseCurrentOrDefaultDistributor(context) { success ->
                    if (success) UnifiedPush.register(context, messageForDistributor = "Radar movie alerts")
                }
            },
            modifier = Modifier.fillMaxWidth(),
        ) { Text("Connect ntfy / UnifiedPush") }
        OutlinedButton(onClick = model::testNotification, modifier = Modifier.fillMaxWidth()) { Text("Send test notification") }
        Text("Account login and checkout remain disabled on the server until redacted authenticated Cineplex traffic is captured.", color = Color(0xFF9BA6B2))
    }
}

@Composable private fun SectionLabel(text: String) = Text(text, style = MaterialTheme.typography.labelMedium, color = Color(0xFF87919D), modifier = Modifier.padding(top = 8.dp))

@Composable
private fun EmptyState(title: String, detail: String) {
    Card(colors = CardDefaults.cardColors(containerColor = Color(0xFF11151D))) {
        Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, fontWeight = FontWeight.Bold)
            Text(detail, color = Color(0xFF9BA6B2))
        }
    }
}
