import gradio as gr
import subprocess
import os
from pathlib import Path
import uuid

INPUT_DIR = Path("./tmp/input")
OUTPUT_DIR = Path("./tmp/output")

INPUT_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

def save_uploaded_file(uploaded_file):
    if uploaded_file is None:
        return None
    
    filename = Path(uploaded_file).name
    destination = INPUT_DIR / filename

    if not destination.exists():
        shutil.copy(uploaded_file, destination)
    
    return str(destination)

def remember_file(file_obj):
    return file_obj  # store file path as state

def process_video(input_video):
    if input_video_path is None:
        return None, None
    
    output_path = OUTPUT_DIR / f"{uuid.uuid4()}.mp4"

    cmd = [
        "ffmpeg", "-i", input_video, "-c", "copy", str(output_path),
        "-y"
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    return str(output_path), str(output_path)

with gr.Blocks() as demo:
    gr.Markdown("### 🎬 FFmpeg Video Editor with Memory")

    video_state = gr.State()

    with gr.Row():
        video_input = gr.Video(label="Upload Video")
        video_output = gr.Video(label="Processed Video", interactive=False)

    download = gr.File(label="Download Edited Video")
    btn = gr.Button("Run FFmpeg Edit")

    # On file upload, store in gr.State
    # video_input.change(fn=remember_file, inputs=video_input, outputs=video_state)
    video_input.change(fn=save_uploaded_file, inputs=video_input, outputs=video_state)

    # On button click, use remembered file path
    btn.click(fn=process_video, inputs=video_state, outputs=video_output)
    # btn.click(fn=process_video, inputs=video_state, outputs=[video_output, download])

demo.launch(server_name="0.0.0.0", server_port=7779, share=True)
