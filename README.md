# 🛡️ EXCODE Sentinel — Async Event-Driven Discord Moderation System

> **Problem:** Modern Discord communities struggle with fragmented moderation tools and manual oversight fatigue.  
> **Solution:** EXCODE Sentinel is a rule-based + AI-assisted moderation pipeline that integrates real-time Discord message processing with a Flask-based admin dashboard for centralized community management.

[![System Status](https://img.shields.io/badge/System--State-Stable-00FF41?style=for-the-badge&logo=probot&logoColor=white)](https://github.com/miz-dev)
[![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Discord](https://img.shields.io/badge/Framework-discord.py-blueviolet?style=for-the-badge&logo=discord&logoColor=white)](https://github.com/Rapptz/discord.py)
[![Flask](https://img.shields.io/badge/Dashboard-Flask-black?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

---

## 🎥 Live System Demo

<p align="center">
  <img src="assets/demo.gif" width="95%" alt="EXCODE Sentinel Live Demo">
</p>

<p align="center"><i>Full async moderation pipeline — detection, escalation, and AI response in real-time.</i></p>

---

## 📊 Admin Dashboard

<p align="center">
  <img src="assets/dashbooard.png" width="90%" alt="Sentinel Intelligence Layer Dashboard">
</p>

<p align="center"><i>Real-time telemetry — VADER sentiment scoring, AI interventions log, and detection sensitivity controls.</i></p>

---

## 🛡️ Moderation Pipeline in Action

<p align="center">
  <img src="assets/muted.png" width="85%" alt="Automated User Mute Notification">
</p>

<p align="center"><i>Automated escalation logic — user muted after exceeding warning threshold. Reason and duration injected by the state machine.</i></p>

<p align="center">
  <img src="assets/kick.png" width="85%" alt="Conduct Alert and Anti-Spam Detection">
</p>

<p align="center"><i>Conduct alerts and Anti-Spam detection firing simultaneously — rule-based and AI layers working in parallel.</i></p>

---

## 🤖 AI-Assisted Interaction

<p align="center">
  <img src="assets/ai%20response.png" width="85%" alt="AI Contextual Response in Discord">
</p>

<p align="center"><i>LLM-powered contextual response handling — the bot interprets natural language, executes code, and delivers formatted output inline.</i></p>

---

## ⚙️ Server Settings Panel

<p align="center">
  <img src="assets/settings.png" width="90%" alt="Flask Admin Settings Panel">
</p>

<p align="center"><i>Dynamic server configuration — update welcome messages, moderation thresholds, and role assignments without restarting the bot.</i></p>

---

## 🏗️ System Architecture

Sentinel is built as a fully asynchronous system designed for real-time response and persistent data storage.

```mermaid
graph TD
    A[Discord Gateway] <--> B[Sentinel Async Engine]
    B --> C{Moderation Pipeline}
    C -->|Rule-Based| D[Pattern Matching Logic]
    C -->|AI-Assisted| E[LLM Classification Layer]
    C -->|Sentiment| F[VADER Analysis Engine]
    B <--> G[(SQLite Persistence Layer)]
    H[Flask Admin Dashboard] <--> G
    H <--> B
```

---

## ⚙️ Engineering Implementation

### 🛡️ Async Moderation Pipeline
- **Real-Time Message Processing:** Leverages `discord.py`'s async event loop for zero-latency message filtering.
- **Rule-Based Fallback:** Strict heuristic checks for spam, caps, and blacklisted patterns — reliable without API connectivity.
- **Automated Escalation Logic:** Programmable state machine handling warnings → mutes → bans based on persistent infraction counts.

### 🧠 AI-Assisted Intelligence
- **Neural Sentiment Scoring:** Integrates VADER to quantify community sentiment and detect toxicity spikes.
- **LLM Integration:** Gemini/OpenRouter for natural language command parsing and intelligent auto-responses.
- **Fuzzy Intent Matching:** `thefuzz` library for high-accuracy command recognition, reducing invalid command friction.

### 🌐 Flask-Based Admin Dashboard
- **Real-Time Telemetry:** Monitors system vitals (CPU/RAM/Latency) via `psutil` for infrastructure health visibility.
- **SQLite-Backed Persistence:** Structured database for moderation history, ticket transcripts, and server configurations.
- **Dynamic Settings Management:** Responsive UI for updating bot config without requiring process restarts.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| Async Framework | Python 3.10+, discord.py |
| Web Dashboard | Flask, HTML5, Vanilla CSS |
| Persistence | SQLite via SQLAlchemy |
| AI / NLP | Google Generative AI, OpenRouter, vaderSentiment |
| System Monitoring | psutil |
| Fuzzy Matching | thefuzz |

---

## 📥 Installation & Setup

1. **Clone Repository:**
   ```bash
   git clone https://github.com/miz-dev/excode-sentinel.git
   cd excode-sentinel
   ```

2. **Environment Configuration:**
   Configure your keys in a `.env` file (see `.env.example`):
   ```env
   DISCORD_BOT_TOKEN=your_token_here
   GEMINI_API_KEY=your_key_here
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Launch Unified System:**
   ```bash
   python run_all.py
   ```

> The `run_all.py` launcher starts both the Discord bot and the Flask dashboard concurrently in a single process.

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for details.

---

### 👨‍💻 Engineered by [Mr. Miz](https://github.com/miz-dev)
> *"Focusing on robust, event-driven community infrastructure."*
