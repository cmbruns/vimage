import importlib.resources
import re
import sys
import traceback

from OpenGL import GL
from OpenGL.GL.shaders import compileShader, ShaderCompilationError


def compile_shader(package: str, file_name: str, shader_type=GL.GL_VERTEX_SHADER):
    full_file_path = ""
    try:
        pkg = importlib.resources.files(package)
        with pkg.joinpath(file_name).open() as file:
            shader_source = file.read()
            full_file_path = file.name
        return compileShader(shader_source, shader_type)
    except ShaderCompilationError as e:
        try:
            # Try to append the glsl shader source line to the stack trace
            # ('Shader compile failure (0): b\'0(3) : error C0000: syntax error, unexpected \\\';\\\', expecting...
            msg = str(e)
            match = re.search(r"Shader compile failure \((\d+)\): b\\?'(\d+)\((\d+)\)", msg)
            if match:
                status = int(match.group(1))
                assert status == GL.GL_FALSE
                # file_no = int(match.group(2))
                line_no = int(match.group(3))
                te = traceback.TracebackException.from_exception(e)
                fs = traceback.FrameSummary(filename=full_file_path, lineno=line_no, name="shader")
                te.stack.append(fs)
                # TODO: get this frame into the actual exception traceback
                print(f'Traceback (most recent call last)\n{"".join(te.stack.format())}', file=sys.stderr)
        except Exception as e2:
            print(e2)
        raise e
