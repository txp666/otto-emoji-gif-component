# Otto Robot GIF Emoji Component

ESP-IDF component that provides **only the gifs folder** with 6 Otto robot GIF emojis for LVGL.

## Content

- **gifs/** – 6 GIF files: `staticstate`, `sad`, `happy`, `scare`, `buxue`, `anger`
- Minimal C API: version, count, and name by index

No embedded C arrays; load GIFs from filesystem or embed them in your project.

## Requirements

- ESP-IDF
- LVGL >= 9.0

## Usage

Add to your project's `idf_component.yml`:

```yaml
dependencies:
  txp666/otto-emoji-gif-component: "^1.1.1"
```

In code:

```c
#include "otto_emoji_gif.h"

// Version and count
printf("Version: %s, Count: %d\n", otto_emoji_gif_get_version(), otto_emoji_gif_get_count());

// Get GIF filename by index (0..5)
const char *name = otto_emoji_gif_get_name(0);  // "staticstate"
```

Copy the **gifs/** folder to your SPIFFS/image partition or embed the GIF files in your app, then use LVGL to open them (e.g. `lv_gif_set_src()` from file path).

## Layout

```
otto-emoji-gif-component/
├── idf_component.yml
├── CMakeLists.txt
├── gifs/           # only content – 6 GIF files
│   ├── staticstate.gif
│   ├── sad.gif
│   ├── happy.gif
│   ├── scare.gif
│   ├── buxue.gif
│   └── anger.gif
├── include/
│   └── otto_emoji_gif.h
└── src/
    └── otto_emoji_gif.c
```

## License

MIT
