import importlib.resources
import logging
import re
import sys
import traceback

from OpenGL import GL
from OpenGL.GL.shaders import ShaderCompilationError


logger = logging.getLogger(__name__)


def compile_shader(package: str, file_names: list[str], shader_type=GL.GL_VERTEX_SHADER):
    sources: list[str] = []
    file_paths: list[str] = []

    # Load all fragment files
    for file_name in file_names:
        pkg = importlib.resources.files(package)
        with pkg.joinpath(file_name).open() as f:
            sources.append(f.read())
            file_paths.append(f.name)

    # Create shader and compile using multiple strings
    shader = GL.glCreateShader(shader_type)
    GL.glShaderSource(shader, sources)
    GL.glCompileShader(shader)

    # Check compile status
    status = GL.glGetShaderiv(shader, GL.GL_COMPILE_STATUS)
    if status == GL.GL_TRUE:
        return shader

    # Retrieve error log
    log = GL.glGetShaderInfoLog(shader).decode(errors="replace")

    # Example error format:
    # Old way
    # ERROR: 0:12: 'foo' : undeclared identifier
    #   → 0 = string index
    #   → 12 = line number
    #
    # Newer way
    # 1(28) : error C1503: undefined variable "foo"

    line_no = 0
    # ERROR: 0:12: 'foo' : undeclared identifier
    match = re.search(r"ERROR:\s+(\d+):(\d+):\s*(.*)", log)
    if match:
        file_index = int(match.group(1))
        line_no = int(match.group(2))
        error_code = ""
        message = match.group(3).strip()
    else:
        # 1(28) : error C1503: undefined variable "foo"
        match = re.search(r"(\d+)\((\d+)\)\s*:\s*error\s+(\w+)\:\s+(.*)", log)
        if match:
            file_index = int(match.group(1))
            line_no = int(match.group(2))
            error_code = f"({match.group(3)})"
            message = match.group(4).strip()

    # Fallback in case regex fails
    if not match:
        logger.debug("match failed")
        # Fallback: print raw log
        print(log, file=sys.stderr)
        raise ShaderCompilationError(log)

    # Map back to correct file
    file_path = file_paths[file_index]

    # Capture full Python stack up to this point
    stack = traceback.extract_stack()[:-1]  # drop the frame inside this function
    # Append our synthetic GLSL code stack frame
    stack.append(traceback.FrameSummary(
        filename=file_paths[file_index],
        lineno=line_no,
        name="shader",
    ))
    # TODO: get this frame into the actual exception traceback
    print(f'Traceback (most recent call last)', file=sys.stderr)
    for stack_msg in traceback.format_list(stack):
        print(stack_msg, end='', file=sys.stderr)
    print(f'ShaderCompilationError: {message} {error_code}', file=sys.stderr)
    print()
    # VS Code clickable GCC-style line
    # AI hallucinated that this is necessary for links in vscode;
    # But the above synthetic traceback is just as good
    # print(f"  {file_path}:{line_no}: error: {message}", file=sys.stderr)

    raise ShaderCompilationError(
        """Shader compile failure (%s): %s""" % (
            status,
            log,
        ),
        sources[file_index],
        shader_type,
    )
