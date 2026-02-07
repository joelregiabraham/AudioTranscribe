# Audio Transcriber

A local, offline audio transcription desktop app powered by [faster-whisper](https://github.com/SYSTRAN/faster-whisper) with a modern dark-themed GUI.

Built for transcribing long lecture recordings (2–3 hours) with GPU acceleration.

---

## Features

- **Offline & free** — runs entirely on your machine, no API keys or internet needed
- **GPU-accelerated** — leverages your NVIDIA RTX GPU via CUDA for fast transcription
- **Multiple formats** — MP3, WAV, FLAC, M4A, MP4, OGG, AAC, Opus, WebM, WMA
- **Cancel** — stop a transcription at any time
- **Live preview** — watch the transcript build in real time
- **Clean .txt output** — save the transcript wherever you want
- **Model selection** — choose from tiny to large-v3 based on your accuracy/speed needs
- **Dark theme** — easy on the eyes

## Requirements

- **Python 3.12.x** (strongly recommended over 3.13 for CUDA compatibility)
- **NVIDIA GPU with CUDA** (optional but recommended — falls back to CPU)

## Setup

### 1. Create a virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac
```

### 2. Install PyTorch with CUDA (for GPU acceleration)

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

> Skip this step if you only want CPU mode. Transcription will be slower but still works.

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run

```bash
python main.py
```

## Usage

1. Click **Browse Audio File** and select your lecture recording
2. Choose a model (default: `large-v3` for best accuracy)
3. Click **Start Transcription**
4. Use **Cancel** if you need to stop early
5. When done, click **Save Transcript** to export as `.txt`

## Model Guide

| Model | Size | Speed | Accuracy | Best For |
|-------|------|-------|----------|----------|
| tiny | ~75 MB | Very fast | Low | Quick drafts |
| base | ~140 MB | Fast | Fair | Short clips |
| small | ~460 MB | Moderate | Good | General use |
| medium | ~1.5 GB | Slower | Very good | Important content |
| large-v3 | ~3 GB | Slowest | Best | Lectures, accuracy-critical |
| distil-large-v3 | ~1.5 GB | Fast | Very good | Best speed/accuracy balance |

With an RTX GPU + large-v3, expect a **3-hour lecture** to take roughly **10–20 minutes**.

## Project Structure

```
audio-transcriber/
├── main.py                # Entry point
├── requirements.txt       # Dependencies
├── ui/
│   ├── app.py             # Main window
│   ├── components.py      # Reusable widgets
│   └── theme.py           # Colors, fonts, spacing
├── core/
│   ├── transcriber.py     # faster-whisper engine
│   └── file_handler.py    # File I/O and validation
└── utils/
    └── logger.py          # Logging configuration
```

## Troubleshooting

**"CUDA not available" / running on CPU**
- Ensure you installed PyTorch with CUDA (step 2 above)
- Check that your NVIDIA drivers are up to date
- Run `python -c "import torch; print(torch.cuda.is_available())"` — should print `True`

**CTranslate2 compatibility issues on Python 3.13**
- Use Python 3.12.x instead — CTranslate2 (which faster-whisper depends on) has known issues with 3.13

**Model download is slow**
- First run downloads the model (~3 GB for large-v3). This is a one-time download cached in `~/.cache/huggingface/`.

## License

Personal use project — not distributed.