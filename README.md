# JustGivenUp! — Screen Guardian

A Windows PC screen guardian that detects NSFW content via screen capture + ONNX Runtime inference and force-closes browsers, with a tamper-proof time-lock that prevents stopping until release date.

## Features

- **NSFW Detection** — Captures screen every 3 seconds via GDI `BitBlt`, runs NudeNet `320n.onnx` through ONNX Runtime 1.26
- **Browser Termination** — Kills Chrome, Edge, Firefox, Brave, Opera directly via `CreateToolhelp32Snapshot` + `TerminateProcess`
- **Smart Filtering** — Whitelist for educational sites (YouTube, Udemy, Coursera, etc.) skips detection entirely; blacklist for proxy/VPN/porn/streaming/.ru sites triggers instant kill
- **Tamper-Proof Time-Lock** — SHA-256 sealed lock stored in registry; tampering extends lock by 90 days
- **Watchdog** — Separate process auto-restarts the guardian if killed
- **Minimal Footprint** — System tray icon, no console window in normal mode

## CLI Commands

```
JustGivenUp.exe                        Run with system tray
JustGivenUp.exe --install               Add to Windows startup
JustGivenUp.exe --remove                Remove from Windows startup
JustGivenUp.exe --lock--DAYS            Lock for N days (3 confirmations required)
JustGivenUp.exe --emergency-stop        Kill all JustGivenUp processes
JustGivenUp.exe --help                  Show help
```

## Quick Start

1. **Download** the latest release or build from source
2. Run `JustGivenUp.exe --lock--30` to lock for 30 days (type `YES` 3 times)
3. Reboot — the program starts automatically locked via Registry Run key
4. Tray icon shows countdown; Stop/Exit are grayed out while locked

## Building from Source

### Requirements

- MSYS2 MinGW-w64 GCC 16.1.0+
- CMake 4.3.3+
- ONNX Runtime 1.26 (automatically fetched from system `ucrt64`)

### Build

```bash
mkdir build && cd build
cmake .. -G "MinGW Makefiles"
mingw32-make -j$(nproc)
```

The build output includes all required DLLs for standalone execution.

## Configuration

Config is stored at `%APPDATA%\JustGivenUp\config.json` with these defaults:

| Key | Default | Description |
|-----|---------|-------------|
| `interval_seconds` | 3 | Seconds between screen captures |
| `nsfw_threshold` | 0.45 | Detection confidence threshold |
| `cooldown_seconds` | 10 | Cooldown after a browser kill |
| `browsers` | chrome,firefox,msedge,brave,opera | Target browser processes |
| `whitelist_skip` | youtube, udemy, coursera, ... | Sites that skip detection entirely |
| `whitelist_lenient` | (empty) | Sites with higher threshold |
| `blacklist_kill` | proxy, porn, streaming, .ru ... | Sites that trigger instant kill |

## How It Works

```
┌─────────┐    ┌──────────┐    ┌───────────┐    ┌──────────┐
│  Filter  │───▶│ Capture  │───▶│ Detector  │───▶│  Killer  │
│ (title)  │    │ (BitBlt) │    │ (ONNX RT) │    │(Terminate)│
└─────────┘    └──────────┘    └───────────┘    └──────────┘
     │                                              │
     │  SKIP/LENIENT                                │  KILL
     ▼                                              ▼
  ┌─────────┐                                  ┌──────────┐
  │  Sleep  │                                  │  Close   │
  │  3 sec  │                                  │  Browser │
  └─────────┘                                  └──────────┘
```

## Security Model

- **Time-Lock**: Lock duration is sealed with SHA-256 via BCrypt. The registry stores `lock_until` (Unix timestamp) and `lock_seal` (HMAC-SHA256). Tampering with either value is detected and adds 90 days.
- **No DNS blocking**: The program closes browser processes directly. There is no DNS or network-level blocking.
- **Watchdog**: A separate process (`JustGivenUp_watchdog.exe`) polls every 8 seconds and restarts the main process if killed.
- **Locked Exit Prevention**: When locked, the tray Exit/Stop menu items are grayed out, `Alt+F4` on the hidden window is blocked, and `--emergency-stop` is refused.

## License

MIT
