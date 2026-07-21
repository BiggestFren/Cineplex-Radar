package ca.radar.cineplex

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import org.junit.Rule
import org.junit.Test

class RadarSmokeTest {
    @get:Rule val compose = createAndroidComposeRule<MainActivity>()

    @Test fun showsPrimaryNavigation() {
        compose.onNodeWithText("RADAR").assertIsDisplayed()
        compose.onNodeWithText("Feed").assertIsDisplayed()
        compose.onNodeWithText("Radar").assertIsDisplayed()
        compose.onNodeWithText("Chat").assertIsDisplayed()
        compose.onNodeWithText("Settings").assertIsDisplayed()
    }
}

