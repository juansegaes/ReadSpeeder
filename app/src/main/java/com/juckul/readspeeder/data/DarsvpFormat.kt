package com.juckul.readspeeder.data

import org.json.JSONArray
import org.json.JSONObject

internal const val DarsvpFormatVersion = 1
internal const val MinWordWeight = 10
internal const val MaxWordWeight = 1_000

internal data class DarsvpContent(
    val title: String?,
    val author: String?,
    val text: String,
    val chapters: List<DocumentChapter>,
    val weights: ShortArray,
    val coverBase64: String?,
)

internal fun countReaderWords(text: String): Int {
    var count = 0
    var index = 0
    while (index < text.length) {
        while (index < text.length && text[index].isWhitespace()) index++
        if (index == text.length) break
        count++
        while (index < text.length && !text[index].isWhitespace()) index++
    }
    return count
}

internal fun parseDarsvp(json: String): DarsvpContent {
    val root = try {
        JSONObject(json)
    } catch (error: Exception) {
        throw IllegalArgumentException("This is not a valid daRSVP file", error)
    }

    require(root.optString("format") == "darsvp") { "This is not a daRSVP file" }
    val version = root.optInt("version", -1)
    require(version <= DarsvpFormatVersion) {
        "This file was made by a newer darsvp-scorer"
    }
    require(version == DarsvpFormatVersion) { "Unsupported daRSVP file" }

    val text = root.optString("text", "")
    require(text.isNotBlank()) { "The daRSVP file has no text" }
    require(text.length <= MaxExtractedCharacters) {
        "The document contains too much text to import"
    }

    val expectedWords = countReaderWords(text)
    val weightArray = root.optJSONArray("weights")
        ?: throw IllegalArgumentException("This is not a valid daRSVP file")
    require(weightArray.length() == expectedWords) {
        "Word count mismatch: text has $expectedWords words but the file has " +
            "${weightArray.length()} weights"
    }
    val weights = ShortArray(expectedWords) { index ->
        val weight = try {
            weightArray.getInt(index)
        } catch (error: Exception) {
            throw IllegalArgumentException("This is not a valid daRSVP file", error)
        }
        weight.coerceIn(MinWordWeight, MaxWordWeight).toShort()
    }

    val chapters = buildList {
        val chapterArray = root.optJSONArray("chapters") ?: JSONArray()
        var previousStart = -1
        for (index in 0 until chapterArray.length()) {
            val chapter = chapterArray.optJSONObject(index) ?: continue
            val title = stringOrNull(chapter, "title") ?: "Chapter ${size + 1}"
            val start = chapter.optInt("startWord", 0).coerceIn(0, expectedWords - 1)
            if (start > previousStart) {
                add(DocumentChapter(title, start))
                previousStart = start
            }
        }
    }

    return DarsvpContent(
        title = stringOrNull(root, "title"),
        author = stringOrNull(root, "author"),
        text = text,
        chapters = chapters,
        weights = weights,
        coverBase64 = stringOrNull(root, "cover"),
    )
}

private fun stringOrNull(json: JSONObject, key: String): String? {
    if (json.isNull(key)) return null
    return json.optString(key).trim().takeIf(String::isNotEmpty)
}
