# Video Tools with AI

```bash

git clone https://github.com/ravuthz/video.ai.git

# Using UV
uv sync

# Or virtualenv

# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate it (on Unix/macOS)
source venv/bin/activate

# On Windows (PowerShell):
# .\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

```

## Developing

```bash

uv init video.ai --python=3.11

uv python pin 3.11

uv venv

source .venv/bin/activate

uv pip list

uv add pydub edge_tts deep_translator

uv add argparse python-dotenv unicodedata

uv remove edge_tts edge-srt-to-speech
uv add "edge-srt-to-speech>=0.0.24"

uv add gradio

uv lock

uv pip freeze > requirements.txt

```

Usage:

```bash

# Using UV

uv run main.py -h

uv run main.py --video_name demo.mp4 --input_dir ./in --output_dir ./out

uv run edge-tts --list-voices

uv run edge-srt-to-speech 

# Virtualenv

source venv/bin/activate

python main.py -h

python main.py --video_name demo.mp4 --input_dir ./in --output_dir ./out

```
