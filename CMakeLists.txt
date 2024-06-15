cmake_minimum_required(VERSION 3.5)
project(vimage NONE)

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
    COMMAND ${PYINSTALLER} ${CMAKE_SOURCE_DIR}/scripts/${SPEC_FILE}
    DEPENDS "${CMAKE_SOURCE_DIR}/scripts/${SPEC_FILE}" "${CMAKE_SOURCE_DIR}/vmg/ui_vimage.py"
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
set(CPACK_PACKAGE_VERSION_MAJOR "0")
set(CPACK_PACKAGE_VERSION_MINOR "9")
set(CPACK_PACKAGE_VERSION_PATCH "0")
set(CPACK_PACKAGE_EXECUTABLES "vimage;vimage")

if (WIN32)
  set(CPACK_GENERATOR WIX)
  set(CPACK_WIX_UPGRADE_GUID F1CA83FC-4F1B-42A3-B033-4D597CAD1A37)
  set(CPACK_WIX_TEMPLATE "${CMAKE_SOURCE_DIR}/CMake/WIX.template.in")
  set(CPACK_WIX_PRODUCT_ICON "${CMAKE_SOURCE_DIR}/vmg/images/vimage2.ico")
  SET(CPACK_WIX_EXTENSIONS WixUtilExtension)
elseif(APPLE)
  set(CPACK_GENERATOR DragNDrop)
  set(CPACK_DMG_DS_STORE "${CMAKE_SOURCE_DIR}/CMake/DS_Store")
elseif(UNIX)
  set(CPACK_GENERATOR DEB)
  set(CPACK_DEBIAN_PACKAGE_MAINTAINER "Christopher Bruns")
  set(CPACK_DEBIAN_PACKAGE_DEPENDS "")
  set(CPACK_SET_DESTDIR "ON")
endif()


include(CPack)
