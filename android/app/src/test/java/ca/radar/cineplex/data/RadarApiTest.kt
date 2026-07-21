package ca.radar.cineplex.data

import kotlinx.coroutines.test.runTest
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class RadarApiTest {
    private lateinit var server: MockWebServer

    @Before fun setUp() { server = MockWebServer(); server.start() }
    @After fun tearDown() { server.shutdown() }

    @Test fun parsesRadarAndSendsBearerToken() = runTest {
        server.enqueue(MockResponse().setBody("""[{"id":7,"movie_query":"Dune","party_size":2,"armed_mode":"notify_only","created_at":"2026-07-21T00:00:00Z","updated_at":"2026-07-21T00:00:00Z"}]""").setHeader("Content-Type", "application/json"))
        val api = RadarApi({ ConnectionSettings(server.url("/").toString(), "secret", "topic") })
        val result = api.radar()
        assertEquals("Dune", result.single().movieQuery)
        assertEquals(2, result.single().partySize)
        val request = server.takeRequest()
        assertEquals("Bearer secret", request.headers["Authorization"])
        assertEquals("/radar", request.path)
    }

    @Test fun reportsUnauthorizedResponseClearly() = runTest {
        server.enqueue(MockResponse().setResponseCode(401).setBody("""{"detail":"Invalid bearer token"}"""))
        val api = RadarApi({ ConnectionSettings(server.url("/").toString(), "wrong", "") })
        val failure = runCatching { api.events() }.exceptionOrNull()
        assertTrue(failure is RadarApiException)
        assertEquals(401, (failure as RadarApiException).status)
    }

    @Test fun loadsAndUpdatesTheatrePreferences() = runTest {
        val response = """[{"name":"Scotiabank Theatre Toronto","address":"259 Richmond Street West","city":"Toronto","province":"ON","slug":"scotiabank-theatre-toronto","enabled":true}]"""
        server.enqueue(MockResponse().setBody(response).setHeader("Content-Type", "application/json"))
        server.enqueue(MockResponse().setBody(response).setHeader("Content-Type", "application/json"))
        val api = RadarApi({ ConnectionSettings(server.url("/").toString(), "secret", "topic") })

        val theatres = api.theatrePreferences()
        val updated = api.updateTheatrePreferences(listOf("Scotiabank Theatre Toronto"))

        assertTrue(theatres.single().enabled)
        assertEquals(theatres, updated)
        assertEquals("/settings/theatres", server.takeRequest().path)
        val updateRequest = server.takeRequest()
        assertEquals("PUT", updateRequest.method)
        assertTrue(updateRequest.body.readUtf8().contains("Scotiabank Theatre Toronto"))
    }

    @Test fun rejectsMissingConfigurationWithoutNetwork() = runTest {
        val api = RadarApi({ ConnectionSettings() })
        val failure = runCatching { api.radar() }.exceptionOrNull()
        assertTrue(failure?.message?.contains("Settings") == true)
        assertEquals(0, server.requestCount)
    }
}
