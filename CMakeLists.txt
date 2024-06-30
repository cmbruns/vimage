cmake_minimum_required(VERSION 3.5)
project(vimage NONE)

# Remember to manually update version here every build
set(VIMAGE_VERSION_SUFFIX "a"
    CACHE STRING
    "vimage version suffix (empty string for official releases, 'a' for pre-releases)"
)
set(CPACK_PACKAGE_VERSION_MAJOR "0")
set(CPACK_PACKAGE_VERSION_MINOR "9")
set(CPACK_PACKAGE_VERSION_PATCH "5")

message(STATUS "vimage version = ${CPACK_PACKAGE_VERSION_MAJOR}.${CPACK_PACKAGE_VERSION_MINOR}.${CPACK_PACKAGE_VERSION_PATCH}${VIMAGE_VERSION_SUFFIX}")

configure_file(
    "${CMAKE_SOURCE_DIR}/CMake/version.py.in"
    "${CMAKE_SOURCE_DIR}/vmg/version.py"
    @ONLY
    NEWLINE_STYLE UNIX
)

mark_as_advanced(
    CMAKE_BACKWARDS_COMPATIBILITY
    CMAKE_CONFIGURATION_TYPES
    EXECUTABLE_OUTPUT_PATH
    LIBRARY_OUTPUT_PATH
)

# Compute git hash to identify exact code version
find_package(Git REQUIRED)
if(GIT_FOUND)
    # First refresh the cache
    execute_process(COMMAND ${GIT_EXECUTABLE} -C ${CMAKE_SOURCE_DIR} diff --quiet HEAD)
    # Then get the hash
    execute_process(COMMAND ${GIT_EXECUTABLE}
        -C ${CMAKE_SOURCE_DIR} describe --always --dirty --broken
        OUTPUT_VARIABLE GIT_HASH
        OUTPUT_STRIP_TRAILING_WHITESPACE
    )
    message(STATUS "vimage git hash = ${GIT_HASH}")
    # Put one copy in the scripts folder for dev use
    # This file will be git ignored, to avoid endless loop
    configure_file(
        "${CMAKE_SOURCE_DIR}/CMake/git_hash.txt.in"
        "${CMAKE_SOURCE_DIR}/vmg/git_hash.txt"
        @ONLY
        NEWLINE_STYLE UNIX
    )
    # Put another next to the installed executable for installed use
    install(FILES "${CMAKE_SOURCE_DIR}/vmg/git_hash.txt"
      DESTINATION "."
    )
endif()

find_program(UIC PySide6-uic
  HINTS
    /Library/Frameworks/Python.framework/Versions/3.9/bin/
    /usr/local/bin/
)
add_custom_command(
    OUTPUT "${CMAKE_SOURCE_DIR}/vmg/ui_vimage.py"
    COMMAND "${UIC}" vimage.ui -o ui_vimage.py
    DEPENDS "${CMAKE_SOURCE_DIR}/vmg/vimage.ui"
    WORKING_DIRECTORY "${CMAKE_SOURCE_DIR}/vmg"
)

find_program(PYINSTALLER pyinstaller
    HINTS
      /Library/Frameworks/Python.framework/Versions/3.9/bin/
      /usr/local/bin/
)
if (WIN32)
  set(SPEC_FILE vimage_win32.spec)
elseif(APPLE)
  set(SPEC_FILE vimage_macos.spec)
elseif(UNIX)
  set(SPEC_FILE vimage_linux.spec)
endif()
add_custom_target(RunPyInstaller ALL
    COMMAND ${CMAKE_COMMAND} -E remove_directory "${CMAKE_BINARY_DIR}/dist"
    COMMAND ${CMAKE_COMMAND} -E remove_directory "${CMAKE_BINARY_DIR}/build"
    COMMAND ${PYINSTALLER} ${CMAKE_SOURCE_DIR}/CMake/${SPEC_FILE}
    DEPENDS "${CMAKE_SOURCE_DIR}/CMake/${SPEC_FILE}" "${CMAKE_SOURCE_DIR}/vmg/ui_vimage.py"
    WORKING_DIRECTORY ${CMAKE_BINARY_DIR}
    COMMENT "Running PyInstaller"
)

if (WIN32)
  install(DIRECTORY "${CMAKE_BINARY_DIR}/dist/vimage/"
      DESTINATION "."
  )
  set_property(INSTALL "vimage.exe"
      PROPERTY CPACK_START_MENU_SHORTCUTS "vimage"
  )
elseif(APPLE)
  install(DIRECTORY "${CMAKE_BINARY_DIR}/dist/vimage.app"
      DESTINATION "."
      USE_SOURCE_PERMISSIONS
  )
 elseif(UNIX)
  install(DIRECTORY "${CMAKE_BINARY_DIR}/dist/vimage"
      DESTINATION "."
  )
endif()

set(CPACK_RESOURCE_FILE_LICENSE "${CMAKE_SOURCE_DIR}/LICENSE.txt")
set(CPACK_PACKAGE_EXECUTABLES "vimage;vimage")
set(CPACK_PACKAGE_CONTACT "zeo1@rotatingpenguin.com")
set(CPACK_PACKAGE_DESCRIPTION_SUMMARY "vimage desktop image file viewer")
set(CPACK_PACKAGE_DESCRIPTION "vimage desktop image file viewer")

if (WIN32)
  set(CPACK_GENERATOR WIX)
  set(CPACK_WIX_UPGRADE_GUID F1CA83FC-4F1B-42A3-B033-4D597CAD1A37)
  set(CPACK_WIX_TEMPLATE "${CMAKE_SOURCE_DIR}/CMake/WIX.template.in")
  set(CPACK_WIX_PRODUCT_ICON "${CMAKE_SOURCE_DIR}/vmg/images/vimage2.ico")
  SET(CPACK_WIX_EXTENSIONS WixUtilExtension)
  set(CPACK_WIX_PATCH_FILE "${CMAKE_SOURCE_DIR}/CMake/wix_patch.xml")
elseif(APPLE)
  set(CPACK_GENERATOR DragNDrop)
  set(CPACK_DMG_DS_STORE "${CMAKE_SOURCE_DIR}/CMake/DS_Store")
elseif(UNIX)
  set(CPACK_GENERATOR DEB)
  set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Christopher Bruns")
  set(CPACK_DEBIAN_PACKAGE_DEPENDS "")
  set(CPACK_DEBIAN_PACKAGE_RELEASE 1)
  set(CPACK_SET_DESTDIR "ON")
endif()


include(CPack)
