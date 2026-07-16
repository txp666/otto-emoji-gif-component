# Otto Robot GIF Emoji Component

ESP-IDF component with **21 animated Otto robot expressions** for LVGL. The
visuals use a compact 240 x 240 black-and-white display style suitable for an AI
robot face.

## Emojis

| Index | GIF | Meaning |
| ---: | --- | --- |
| 0 | `neutral` | Neutral |
| 1 | `happy` | Happy |
| 2 | `laughing` | Laughing |
| 3 | `funny` | Amused |
| 4 | `sad` | Sad |
| 5 | `angry` | Angry |
| 6 | `crying` | Crying |
| 7 | `loving` | Loving |
| 8 | `embarrassed` | Embarrassed |
| 9 | `surprised` | Surprised |
| 10 | `shocked` | Shocked |
| 11 | `thinking` | Thinking |
| 12 | `winking` | Winking |
| 13 | `cool` | Cool |
| 14 | `relaxed` | Relaxed |
| 15 | `delicious` | Delicious |
| 16 | `kissy` | Kissy |
| 17 | `confident` | Confident |
| 18 | `sleepy` | Sleepy |
| 19 | `silly` | Silly |
| 20 | `confused` | Confused |

Every GIF is 240 x 240, loops continuously, and uses an 80 ms frame cadence.

## Requirements

- ESP-IDF
- LVGL >= 9.0

## Usage

Add the component to your project's `idf_component.yml`:

```yaml
dependencies:
  txp666/otto-emoji-gif-component: "^1.3.0"
```

Use the minimal C API to enumerate the available assets:

```c
#include "otto_emoji_gif.h"

printf("Version: %s, Count: %d\n",
       otto_emoji_gif_get_version(),
       otto_emoji_gif_get_count());

const char *name = otto_emoji_gif_get_name(11);  // "thinking"
```

Copy the `gifs/` folder to SPIFFS or an image partition, or embed the files in
your project. LVGL can then open them with `lv_gif_set_src()`.

## Regenerating the scripted animations

The extended Xiaozhi expressions are generated deterministically by
`tools/generate_ai_emojis.py`. With Pillow installed, run:

```sh
python tools/generate_ai_emojis.py
```

The generator preserves the project's 240 x 240 canvas, monochrome palette,
antialiased geometry, loop timing, and neutral first/last frames.

## Xiaozhi ESP32 integration

Every filename matches the corresponding Xiaozhi `EmojiCollection` name.
No legacy filename aliases are required.

## License

MIT
