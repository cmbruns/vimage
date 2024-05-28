cmake_minimum_required(VERSION 3.5)
project(vimage NONE)

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

set_property(INSTALL "vimage.exe"
    PROPERTY CPACK_START_MENU_SHORTCUTS "vimage"
)

# set(CPACK_GENERATOR NSIS)

set(CPACK_GENERATOR WIX)
set(CPACK_WIX_UPGRADE_GUID F1CA83FC-4F1B-42A3-B033-4D597CAD1A37)
set(CPACK_WIX_TEMPLATE "${CMAKE_SOURCE_DIR}/CMake/WIX.template.in")
set(CPACK_WIX_PRODUCT_ICON "${CMAKE_SOURCE_DIR}/vmg/images/cat_eye2.ico")
SET(CPACK_WIX_EXTENSIONS WixUtilExtension)

set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_SOURCE_DIR}/LICENSE.txt")
set(CPACK_PACKAGE_VERSION_MAJOR "0")
set(CPACK_PACKAGE_VERSION_MINOR "8")
set(CPACK_PACKAGE_VERSION_PATCH "0")
set(CPACK_PACKAGE_EXECUTABLES "vimage;vimage")

include(CPack)
