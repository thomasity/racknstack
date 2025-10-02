# RacknStack – Full-Stack Telemetry & Control Dashboard for NASA Lunar EXPRESS Racks

**RacknStack** is a full-stack telemetry and control system developed as part of a NASA X-Hab Academic Innovation Challenge. Its purpose is to support the redesign of the International Space Station’s EXPRESS (EXpedite the PRocessing of Experiments to the Space Station) racks for use in lunar surface habitats.

The system combines a browser-based frontend with embedded control and telemetry hardware to visualize, manage, and test rack-mounted experiments in lunar analog conditions.

## 🧭 Project Context

This project was part of a **NASA-funded X-Hab challenge**. It supports:
- Modular equipment control
- Environmental monitoring
- Rack-level system diagnostics
- Adaptation of ISS EXPRESS racks to lunar mission needs

## 🔧 System Overview

- **Frontend (React)**:
  - User inputs remote IP and port
  - Live MJPEG video feed from onboard Pi camera
  - Real-time telemetry UI (fed by downstream microcontrollers)

- **Backend (Python on Raspberry Pi)**:
  - Manages power relay to activate/deactivate rack modules
  - Reads telemetry from Raspberry Pi Picos via UART
  - Streams MJPEG video feed over HTTP
  - Uses multithreading to handle concurrent tasks

## 📁 Project Structure

- `src/`
- `App.js` - Remote Control Application
- `components/`
  - `IpPortForm.js` – IP/Port config form
  - `MjpegStream.js` – Video stream UI
  - `Telemetry.js` – Displays numeric sensor values
- `main.py` – Backend script handling telemetry, power, and video
- `public/` – Static web assets for front end

## 🛠️ Technologies

- React
- Python 3
- `threading`, `serial`, `picamera` or MJPEG-compatible streaming
- Raspberry Pi (central control)
- Raspberry Pi Picos (telemetry sources)
- Relay module (GPIO-controlled switching)

## 🚀 Getting Started

### Frontend

```bash
npm install
npm start
```
Navigate to the local frontend and connect to the Pi using its IP/port.

**Backend (on Raspberry Pi)**
```bash
python3 main.py
```
Ensure:

- UART is enabled and receiving from Pi Picos
- Relay and camera are connected
- MJPEG server is available
