/**
 * @file otto_emoji_gif.h
 * @brief Otto robot GIF emoji component - gifs folder only
 *
 * This component provides 6 GIF files in the gifs/ directory.
 * Load them via LVGL from filesystem or embed in your project.
 */

#ifndef OTTO_EMOJI_GIF_H
#define OTTO_EMOJI_GIF_H

#ifdef __cplusplus
extern "C" {
#endif

/** Component version string */
const char *otto_emoji_gif_get_version(void);

/** Number of GIF emojis (6) */
int otto_emoji_gif_get_count(void);

/** Get GIF filename by index (0..5): staticstate, sad, happy, scare, buxue,
 * anger */
const char *otto_emoji_gif_get_name(int index);

#ifdef __cplusplus
}
#endif

#endif /* OTTO_EMOJI_GIF_H */
