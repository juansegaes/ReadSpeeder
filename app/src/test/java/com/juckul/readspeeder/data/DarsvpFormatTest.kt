package com.juckul.readspeeder.data

import com.juckul.readspeeder.ui.screens.parseReaderText
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Test

class DarsvpFormatTest {
    private fun fixture(): String =
        javaClass.classLoader!!.getResource("darsvp/sample.darsvp.json")!!.readText()

    private fun json(
        text: String,
        weights: String,
        format: String = "darsvp",
        version: Int = 1,
        author: String = "\"Test Author\"",
        title: String = "\"Test Book\"",
    ): String = """
        {
          "format": "$format",
          "version": $version,
          "title": $title,
          "author": $author,
          "text": "$text",
          "chapters": [{"title": "Chapter One", "startWord": 0}],
          "weights": [$weights]
        }
    """.trimIndent()

    @Test
    fun sampleFixtureParses() {
        val content = parseDarsvp(fixture())

        assertEquals("Sample Book", content.title)
        assertEquals("Test Author", content.author)
        assertEquals(
            listOf(
                DocumentChapter("Chapter One", 0),
                DocumentChapter("Chapter Two", 19),
            ),
            content.chapters,
        )
        assertEquals(
            parseReaderText(content.text, splitHyphenatedWords = false).words.size,
            content.weights.size,
        )
        assertNull(content.coverBase64)
    }

    @Test
    fun rejectsWrongFormat() {
        val error = assertThrows(IllegalArgumentException::class.java) {
            parseDarsvp(json("a", "100", format = "other"))
        }
        assertTrue(error.message!!.contains("not a daRSVP file"))
    }

    @Test
    fun rejectsNewerVersion() {
        val error = assertThrows(IllegalArgumentException::class.java) {
            parseDarsvp(json("a", "100", version = 2))
        }
        assertTrue(error.message!!.contains("newer darsvp-scorer"))
    }

    @Test
    fun rejectsWordCountMismatch() {
        val error = assertThrows(IllegalArgumentException::class.java) {
            parseDarsvp(json("a b", "100"))
        }
        assertTrue(error.message!!.contains("Word count mismatch"))
    }

    @Test
    fun rejectsEmptyText() {
        assertThrows(IllegalArgumentException::class.java) {
            parseDarsvp(json("   ", ""))
        }
    }

    @Test
    fun clampsWeights() {
        val content = parseDarsvp(json("a b", "5, 5000"))
        assertArrayEquals(shortArrayOf(10, 1_000), content.weights)
    }

    @Test
    fun countReaderWordsTreatsUnicodeSpacesAsSeparators() {
        assertEquals(2, countReaderWords("a\u00a0b"))
    }

    @Test
    fun nullAuthorBecomesNull() {
        val content = parseDarsvp(json("a", "100", author = "null"))
        assertNull(content.author)
    }
}
