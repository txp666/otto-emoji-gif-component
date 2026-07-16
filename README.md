# Otto Robot GIF Emoji Component

ESP-IDF component with **12 animated Otto robot expressions** for LVGL. The
visuals use a compact 240 x 240 black-and-white display style suitable for an AI
robot face.

## Emojis

| Index | GIF | Meaning |
| ---: | --- | --- |
| 0 | `staticstate` | Neutral / idle |
| 1 | `sad` | Sad |
| 2 | `happy` | Happy |
| 3 | `scare` | Scared / surprised |
| 4 | `buxue` | Unimpressed |
| 5 | `anger` | Angry |
| 6 | `thinking` | Thinking / processing |
| 7 | `listening` | Listening to the user |
| 8 | `speaking` | Speaking / responding |
| 9 | `confused` | Confused / needs clarification |
| 10 | `loving` | Affection / appreciation |
| 11 | `sleepy` | Sleepy / low-power mode |

Every GIF is 240 x 240, loops continuously, and uses an 80 ms frame cadence.

## Requirements

- ESP-IDF
- LVGL >= 9.0

## Usage

Add the component to your project's `idf_component.yml`:

```yaml
dependencies:
  txp666/otto-emoji-gif-component: "^1.2.0"
```

Use the minimal C API to enumerate the available assets:

```c
#include "otto_emoji_gif.h"

printf("Version: %s, Count: %d\n",
       otto_emoji_gif_get_version(),
       otto_emoji_gif_get_count());

const char *name = otto_emoji_gif_get_name(6);  // "thinking"
```

Copy the `gifs/` folder to SPIFFS or an image partition, or embed the files in
your project. LVGL can then open them with `lv_gif_set_src()`.

## Regenerating the AI animations

The six AI-specific GIFs are generated deterministically by
`tools/generate_ai_emojis.py`. With Pillow installed, run:

```sh
python tools/generate_ai_emojis.py
```

The generator preserves the project's 240 x 240 canvas, monochrome palette,
antialiased geometry, loop timing, and neutral first/last frames.

## Xiaozhi ESP32 integration

The filenames follow Xiaozhi's emotion names where an exact match exists:
`thinking`, `confused`, `loving`, and `sleepy`. The `listening` and `speaking`
animations are intended for device-state transitions on both the Otto Robot and
ElectronBot boards. Legacy assets still map as follows when the Xiaozhi asset
builder provides aliases:

| Xiaozhi emotion | GIF fallback |
| --- | --- |
| `neutral`, `relaxed`, `idle` | `staticstate` |
| `laughing`, `funny`, `confident`, `winking`, `cool`, `delicious`, `kissy`, `silly` | `happy` |
| `crying` | `sad` |
| `angry` | `anger` |
| `surprised`, `shocked` | `scare` |
| `embarrassed` | `buxue` |

## License

MIT
