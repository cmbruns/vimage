message(STATUS "Configuring C++ source files")

# Force C++20 standard globally
set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF) # Set to ON if you want compiler-specific extensions (e.g., gnu++20)

add_library(vimage_util SHARED sin_from_eqr.cpp)

# Cross-platform configurations
if(MSVC)
    # Windows: Optimize for speed, strip debug info in release mode
    target_compile_options(vimage_util PRIVATE /W4)
else()
    # Linux & macOS: Use -O3, enable Position Independent Code (-fPIC), and hide internal symbols
    target_compile_options(vimage_util PRIVATE -O3 -Wall -Wextra)
    set_target_properties(vimage_util PROPERTIES 
        POSITION_INDEPENDENT_CODE ON
        CXX_VISIBILITY_PRESET hidden
        VISIBILITY_INLINES_HIDDEN ON
    )
endif()

# Output clean library names across platforms (removes 'lib' prefix on Windows if using GCC/MinGW)
set_target_properties(vimage_util PROPERTIES
    PREFIX ""
    OUTPUT_NAME "vimage_util"
)

install(TARGETS vimage_util
    RUNTIME DESTINATION "${CMAKE_SOURCE_DIR}/vmg/lib"
    LIBRARY DESTINATION "${CMAKE_SOURCE_DIR}/vmg/lib"  # Linux/Mac
)
