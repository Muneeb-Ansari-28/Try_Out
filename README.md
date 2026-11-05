# 🧥 Live Virtual Try-On (VTON) Application

A real-time, browser-based virtual try-on application inspired by Anywear / Decart, running locally on consumer hardware (**NVIDIA T550 · 4GB VRAM**) with zero paid API dependencies.

---

## 📖 Key Documentation

- 📋 **Implementation Plan:** [`VTON_IMPLEMENTATION_PLAN.md`](./VTON_IMPLEMENTATION_PLAN.md) — Comprehensive 7-day build plan covering backend setup, TPS/DM-VTON warping, FastAPI MJPEG streaming, Next.js frontend, and performance tuning.
- 🤖 **Agent Skills Guide:** [`.agents/README.md`](./.agents/README.md) — Instructions for AI agents detailing which specialized skills to activate for each domain (UI engineering, Python backend, GPU optimization, debugging, etc.).

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10, FastAPI, OpenCV, MediaPipe Pose, PyTorch (CUDA 11.7), `rembg`
- **Warping Engine:** MediaPipe Pose + TPS Homography (baseline) upgraded with DM-VTON (fabric realism)
- **Frontend:** Next.js 15, React, Tailwind CSS, Framer Motion, `@dnd-kit/core`, Lucide React
- **Streaming:** Low-latency MJPEG over HTTP (`/video-feed` → HTML `<img>` tag)
- **Hardware Target:** NVIDIA T550 (4GB VRAM) running at 15–25+ FPS

