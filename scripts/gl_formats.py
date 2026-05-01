"""
Gather information about preferred OpenGL texture formats
"""

import glfw
from OpenGL import GL


gl_const_index = dict()
for constant in (
    GL.GL_NONE,
    GL.GL_RED,
    GL.GL_RG,
    GL.GL_RGB,
    GL.GL_RGBA,
    GL.GL_UNSIGNED_BYTE,
    GL.GL_UNSIGNED_INT_8_8_8_8_REV,
):
    gl_const_index[int(constant)] = constant


assert glfw.init()
glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 4)
glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 1)  # Use 4.1 for Mac compatibility
glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
window = glfw.create_window(640, 480, "gl_formats", None, None)
glfw.make_context_current(window)
for internal_format in GL.GL_RED, GL.GL_RG, GL.GL_RGB, GL.GL_RGBA:
    print(f"internal format: {internal_format.name}")
    optimal_format = GL.glGetInternalformativ(
        GL.GL_TEXTURE_2D,
        internal_format,
        GL.GL_TEXTURE_IMAGE_FORMAT,
        1,
    )
    optimal_type = GL.glGetInternalformativ(
        GL.GL_TEXTURE_2D,
        internal_format,
        GL.GL_TEXTURE_IMAGE_TYPE,
        1,
    )
    print(f"  optimal format = {gl_const_index[optimal_format].name}")
    print(f"  optimal type = {gl_const_index[optimal_type].name}")
glfw.terminate()
