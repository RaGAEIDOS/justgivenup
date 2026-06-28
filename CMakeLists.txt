cmake_minimum_required(VERSION 3.20)
project(JustGivenUp CXX)
set(CMAKE_CXX_STANDARD 23)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_AUTOMOC OFF)

add_compile_definitions(UNICODE _UNICODE)

# ── ONNX Runtime ──────────────────────────────────────────
set(ONNX_DIR "C:/msys64/ucrt64")
set(ONNX_INCLUDE_DIR "${ONNX_DIR}/include/onnxruntime")
set(ONNX_LIB_DIR "${ONNX_DIR}/lib")
set(ONNX_BIN_DIR "${ONNX_DIR}/bin")

# ── nlohmann/json (header-only) ───────────────────────────
find_path(JSON_INCLUDE_DIR nlohmann/json.hpp
  HINTS "C:/msys64/mingw64/include" "C:/msys64/ucrt64/include"
  REQUIRED)

# ── Guardian executable ────────────────────────────────────
add_executable(JustGivenUp
  src/main.cpp
  src/log.cpp
  src/config.cpp
  src/filter.cpp
  src/browser.cpp
  src/capture.cpp
  src/detector.cpp
  src/lock.cpp
  src/tray.cpp
  src/guardian.cpp
  src/resource.rc
)

target_include_directories(JustGivenUp PRIVATE
  src
  ${ONNX_INCLUDE_DIR}
  ${JSON_INCLUDE_DIR}
)

target_link_directories(JustGivenUp PRIVATE ${ONNX_LIB_DIR})
target_link_libraries(JustGivenUp
  onnxruntime
  gdi32
  user32
  shell32
  advapi32
  bcrypt
  ole32
  comctl32
  comdlg32
  ws2_32
  shlwapi
)
# Console subsystem keeps CLI output visible; hide window programmatically in normal mode
# (Don't use --subsystem,windows or CLI commands like --lock won't show prompts)

# Copy ONNX DLL + model + dependencies next to exe at build time
set(UCRT_DLL_DIR "${ONNX_BIN_DIR}")
add_custom_command(TARGET JustGivenUp POST_BUILD
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${ONNX_BIN_DIR}/onnxruntime.dll"
    "$<TARGET_FILE_DIR:JustGivenUp>/"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${CMAKE_SOURCE_DIR}/assets/320n.onnx"
    "$<TARGET_FILE_DIR:JustGivenUp>/"
  COMMAND ${CMAKE_COMMAND} -E copy_if_different
    "${CMAKE_SOURCE_DIR}/assets/config.json"
    "$<TARGET_FILE_DIR:JustGivenUp>/"
  COMMAND ${CMAKE_COMMAND} -E copy_directory
    "${UCRT_DLL_DIR}"
    "$<TARGET_FILE_DIR:JustGivenUp>/"
)

# ── Watchdog executable (standalone) ──────────────────────
add_executable(JustGivenUp_watchdog
  src/watchdog.cpp
  src/log.cpp
)
set_target_properties(JustGivenUp_watchdog PROPERTIES WIN32_EXECUTABLE FALSE)

target_link_libraries(JustGivenUp_watchdog
  kernel32
  user32
  shell32
  shlwapi
)

target_include_directories(JustGivenUp_watchdog PRIVATE
  src
  ${JSON_INCLUDE_DIR}
)

# ── Install rules ──────────────────────────────────────────
install(TARGETS JustGivenUp JustGivenUp_watchdog
  RUNTIME DESTINATION bin)
install(FILES
  "${ONNX_BIN_DIR}/onnxruntime.dll"
  "${CMAKE_SOURCE_DIR}/assets/320n.onnx"
  "${CMAKE_SOURCE_DIR}/assets/config.json"
  DESTINATION bin)
