project(vimage NONE)
cmake_minimum_required(VERSION 2.8.12)

find_program(UIC PySide6-uic)
add_custom_command(
    OUTPUT "${CMAKE_SOURCE_DIR}/vmg/ui_vimage.py"
    COMMAND "${UIC}" vimage.ui -o ui_vimage.py
    DEPENDS "${CMAKE_SOURCE_DIR}/vmg/vimage.ui"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/vmg"
)

find_program(PYINSTALLER pyinstaller)
add_custom_target(RunPyInstaller ALL
    COMMAND ${CMAKE_COMMAND} -E remove_directory "${CMAKE_BINARY_DIR}/dist"
    COMMAND ${CMAKE_COMMAND} -E remove_directory "${CMAKE_BINARY_DIR}/build"
    COMMAND ${PYINSTALLER} ${CMAKE_SOURCE_DIR}/scripts/vimage.spec
    DEPENDS "${CMAKE_SOURCE_DIR}/scripts/vimage.spec" "${CMAKE_SOURCE_DIR}/vmg/ui_vimage.py"
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Running PyInstaller"
)

install(DIRECTORY "${CMAKE_BINARY_DIR}/dist/vimage/"
    DESTINATION "."
)

# set(CPACK_GENERATOR NSIS)

set(CPACK_GENERATOR WIX)
set(CPACK_WIX_UPGRADE_GUID F1CA83FC-4F1B-42A3-B033-4D597CAD1A37)

set(CPACK_PACKAGE_VERSION_MAJOR "0")
set(CPACK_PACKAGE_VERSION_MINOR "5")
set(CPACK_PACKAGE_VERSION_PATCH "0")
set(CPACK_PACKAGE_EXECUTABLES vimage.exe vimage)

include(CPack)
