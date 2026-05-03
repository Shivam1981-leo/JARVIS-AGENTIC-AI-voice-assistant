<div align="center">

<img src="https://readme-typing-svg.demolab.com?font=Orbitron&size=40&duration=3000&pause=1000&color=00C8FF&center=true&vCenter=true&width=600&lines=J.A.R.V.I.S.;Just+A+Rather+Very+Intelligent+System" alt="JARVIS Typing SVG" />

<br/>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/Ollama-llama3.2-black?style=for-the-badge&logo=ollama&logoColor=white" />
  <img src="https://img.shields.io/badge/ElevenLabs-TTS-purple?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Faster--Whisper-STT-orange?style=for-the-badge" />
  <img src="https://img.shields.io/badge/Pygame-3D_UI-green?style=for-the-badge&logo=pygame&logoColor=white" />
  <img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" />
</p>

<br/>

> *"Sometimes you gotta run before you can walk."*  — Tony Stark

<br/>

A fully autonomous, voice-activated AI desktop assistant powered by a **local LLM agentic loop**, **real-time interruptible speech**, **parallel tool execution**, and a **live 3D holographic Pygame UI** — built to feel like the JARVIS from Iron Man.

</div>

---

## ✦ Showcase

<div align="center">

| State | Visual | Description |
|-------|--------|-------------|
| 💤 **Asleep** | Dim wireframe sphere | Waiting for wake word |
| 🎙️ **Listening** | Green pulsing sphere | Capturing voice input |
| 🧠 **Thinking** | Orange spinning sphere | LLM processing command |
| 🔊 **Speaking** | Cyan distorted sphere | Playing ElevenLabs audio |

</div>

---

## ⚡ Features

### 🤖 Agentic Intelligence
- **5-round tool-chaining loop** — JARVIS plans and executes multi-step tasks autonomously, calling tools in sequence and reacting to their results before proceeding
- **22 integrated tools** — from web search and Wikipedia to terminal commands, mouse control, and screen vision
- **Parallel tool execution** — compound commands ("open YouTube and search for that") are dispatched simultaneously via `ThreadPoolExecutor`
- **Follow-up detection** — when a request is ambiguous, JARVIS asks a clarifying question and recursively processes your answer

### 🎙️ Real-Time Voice Engine
- **Faster-Whisper STT** — local, offline transcription using the `medium.en` model with VAD (Voice Activity Detection) filtering to suppress hallucinations
- **ElevenLabs TTS** — premium George voice (`JBFqnCBsd6RMkjVDRZzb`) via `eleven_multilingual_v2` for a warm, JARVIS-like tone
- **Mid-speech interruption** — while JARVIS is speaking, say `"stop"`, `"quiet"`, or `"cancel"` and it instantly halts playback and begins listening

### ⚙️ Concurrency & Multitasking
- **Background task engine** — long-running commands (installs, downloads, batch jobs) are dispatched to a background `ThreadPoolExecutor` so JARVIS keeps listening; results are announced on completion
- **Proactive idle engagement** — after 5 minutes of silence, JARVIS checks in with a contextual message
- **Thread-safe state management** — all shared state guarded with locks and queues

### 🌐 3D Holographic UI
- **Real-time wireframe sphere** rendered in Pygame with depth projection (perspective divide) and X/Y-axis rotation
- **Voice-reactive distortion** — the sphere warps with a sin-wave deformation driven by the current speech amplitude
- **Depth-fade shading** — each mesh point is individually colored by its Z-depth for a true 3D holographic look
- **Live HUD subtitles** — your transcribed speech and JARVIS's response scroll in real-time at 60 FPS

---

## 🛠️ Tool Arsenal

<details>
<summary><b>Click to expand — all 22 tools</b></summary>

<br/>

| Tool | Description |
|------|-------------|
| `get_time` | Returns current local time |
| `search_wikipedia` | Fetches a 2-sentence Wikipedia summary |
| `open_application` | Launches a desktop app by name |
| `close_application` | Closes a running desktop app |
| `open_website` | Opens a URL in Google Chrome |
| `type_text` | Types text into the active window |
| `write_text_to_file` | Creates/overwrites a file with content |
| `run_terminal_command` | Executes a Windows CMD command |
| `run_background_task` | Runs a command in the background; announces on completion |
| `check_background_tasks` | Reports status of all background tasks |
| `web_search_and_summarize` | Live DuckDuckGo search with summarized results |
| `system_control` | Volume, mute, lock, play/pause, next track |
| `take_screenshot` | Saves a timestamped screenshot |
| `analyze_screen` | Uses LLaVA vision model to describe what's on screen |
| `mouse_click` | Click, double-click, right-click at coordinates |
| `press_key` | Presses any key or hotkey combo (`ctrl+c`, `alt+tab`) |
| `get_clipboard` | Reads current clipboard contents |
| `remember_information` | Saves a fact to persistent `memory.json` |
| `fetch_memory` | Retrieves all saved memories with indices |
| `update_memory` | Updates a memory entry by index |
| `delete_memory` | Removes a memory entry by index |
| `clear_all_memories` | Wipes the entire memory bank |

</details>

---

## 🚀 Getting Started

### Prerequisites

- Python **3.10+**
- [Ollama](https://ollama.com) installed and running locally
- An [ElevenLabs](https://elevenlabs.io) API key (free tier works)
- Windows OS (some tools use `os.system` with Windows commands)

### 1 · Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/jarvis-ai.git
cd jarvis-ai
```

### 2 · Install dependencies

```bash
pip install -r requirements.txt
```

> **Note:** `pyaudio` may require a pre-built wheel on Windows. If the install fails, use:
> ```bash
> pip install pipwin && pipwin install pyaudio
> ```

### 3 · Pull the required Ollama models

```bash
ollama pull llama3.2       # Core reasoning model
ollama pull llava          # Vision model (for screen analysis)
```

### 4 · Configure environment variables

Create a `.env` file in the project root:

```env
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
```

### 5 · Run JARVIS

```bash
python jarvis.py
```

JARVIS will calibrate ambient noise, greet you with a real-time weather briefing, and enter standby mode.

---

## 🗣️ Usage

| Wake Word | Command |
|-----------|---------|
| `"Wake up Jarvis"` | Activates JARVIS from sleep |
| `"Jarvis, [command]"` | Issue any voice command |
| `"Sleep"` / `"Go to sleep"` | Returns to standby |
| `"Stop"` / `"Shut up"` | Interrupts mid-speech |
| `"Exit"` / `"Shut down"` | Closes the application |

### Example Commands

```
"Open VS Code and Chrome at the same time"
"Search Wikipedia for quantum computing"
"Write an essay on machine learning and open it"
"Remember that my standup is at 10 AM every day"
"What's on my screen right now?"
"Run a git pull in the background"
"Volume up and play the next track"
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    JARVIS System                         │
│                                                          │
│  ┌──────────┐    ┌──────────────┐    ┌───────────────┐  │
│  │  Pygame  │    │  Brain Thread│    │  BG Executor  │  │
│  │  3D UI   │◄───│  (Main Loop) │───►│  ThreadPool   │  │
│  │  60 FPS  │    │              │    │  (4 workers)  │  │
│  └──────────┘    └──────┬───────┘    └───────────────┘  │
│                         │                                │
│              ┌──────────▼──────────┐                     │
│              │   Faster-Whisper    │                     │
│              │   (STT / VAD)       │                     │
│              └──────────┬──────────┘                     │
│                         │                                │
│              ┌──────────▼──────────┐                     │
│              │  Ollama (llama3.2)  │                     │
│              │  Agentic Loop ×5    │                     │
│              │  Parallel Tools     │                     │
│              └──────────┬──────────┘                     │
│                         │                                │
│              ┌──────────▼──────────┐                     │
│              │   ElevenLabs TTS    │                     │
│              │   Interruptible     │                     │
│              └─────────────────────┘                     │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 Requirements

```
SpeechRecognition
pyaudio
wikipedia
requests
pygame
ollama
elevenlabs
python-dotenv
AppOpener
faster-whisper
duckduckgo-search
pyautogui
pyperclip
```

---

## 🗺️ Roadmap

- [ ] Multi-monitor support for the 3D UI
- [ ] LLaVA vision integration for real-time screen understanding during commands
- [ ] Custom wake word training (replace keyword matching)
- [ ] Spotify & media control via API
- [ ] Gmail / calendar integration
- [ ] Mobile companion app (remote voice commands)
- [ ] GPU-accelerated Whisper inference

---

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

<div align="center">

**Built with ❤️ by [Shivam Shirsat](https://github.com/Shivam1981-leo)**

<br/>

*"I am Iron Man."*

<br/>

⭐ Star this repo if JARVIS impressed you!

</div>
