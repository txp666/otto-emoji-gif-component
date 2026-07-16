/**
 * @file otto_emoji_gif.c
 * @brief Otto robot GIF emoji component - minimal API, content is gifs/ folder
 * only
 */

#include "otto_emoji_gif.h"
#include <stddef.h>

#ifndef OTTO_EMOJI_GIF_VERSION
#define OTTO_EMOJI_GIF_VERSION "1.3.0"
#endif

static const char *const gif_names[] = {
    "neutral",    "happy",      "laughing",  "funny",      "sad",
    "angry",      "crying",     "loving",    "embarrassed", "surprised",
    "shocked",    "thinking",   "winking",   "cool",       "relaxed",
    "delicious",  "kissy",      "confident", "sleepy",     "silly",
    "confused"};

#define GIF_COUNT ((int)(sizeof(gif_names) / sizeof(gif_names[0])))

const char *otto_emoji_gif_get_version(void) { return OTTO_EMOJI_GIF_VERSION; }

int otto_emoji_gif_get_count(void) { return GIF_COUNT; }

const char *otto_emoji_gif_get_name(int index) {
  if (index < 0 || index >= GIF_COUNT) {
    return NULL;
  }
  return gif_names[index];
}
