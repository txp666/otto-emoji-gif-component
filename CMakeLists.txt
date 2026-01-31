# Otto robot GIF emoji component (gifs folder only)
#
# This component provides only the gifs folder with 6 GIF files.
# Use LVGL to load them from filesystem or embed in your project.

# Minimal source for component registration
set(COMPONENT_SRCS "src/otto_emoji_gif.c")

# Register component
idf_component_register(
    SRCS ${COMPONENT_SRCS}
    INCLUDE_DIRS "include"
    REQUIRES "lvgl"
)

target_compile_definitions(${COMPONENT_LIB}
    PRIVATE OTTO_EMOJI_GIF_VERSION="1.1.1"
)

message(STATUS "Otto Emoji GIF Component: gifs only at ${CMAKE_CURRENT_SOURCE_DIR}/gifs")
