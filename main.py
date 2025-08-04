import os
import asyncio
from pathlib import Path
from os.path import dirname
from dotenv import load_dotenv
import argparse

from tools import create_logger, VideoTool, pp, dd

load_dotenv()

logger = create_logger(__name__)

def debug(data):
    logger.debug(data)
    print(data)

async def main(args):
    FILE_NAME = args.video_name or os.getenv("VIDEO_NAME")
    input_dir = Path(args.input_dir or os.getenv("INPUT_DIR"))
    output_dir = Path(args.output_dir or os.getenv("OUTPUT_DIR"))

    if not FILE_NAME:
        parser.error("Missing required: --video_name or VIDEO_NAME in .env")

    print("Video.AI Configuration:")
    print(f"  📼 Video Name : {FILE_NAME}")
    print(f"  📂 Input Dir  : {input_dir}")
    print(f"  💾 Output Dir : {output_dir}")

    service = VideoTool()

    en_sub_title_path = input_dir / f"{FILE_NAME}_en.srt"
    km_sub_title_path = output_dir / f"{FILE_NAME}_km.srt"

    input_video_path = input_dir / f"{FILE_NAME}.mp4"
    output_video_path = output_dir / input_video_path.name
    audio_output_path = output_video_path.with_suffix(".wav")
    ex_audio_output_path = output_video_path.with_suffix(".mp3")

    video_subtitle_path = output_dir / f"{FILE_NAME}_km.mp4"

    os.makedirs(dirname(output_video_path), exist_ok=True)
    
    
    try:
        # voices = service.list_available_voices()
        # print("Available voices:", pp(voices))
        input_video_path = str(input_video_path)
        km_sub_title_path = str(km_sub_title_path)
        audio_output_path = str(audio_output_path)
        ex_audio_output_path = str(ex_audio_output_path)
        output_video_path = str(output_video_path)
        video_subtitle_path = str(video_subtitle_path)

        # if not os.path.exists(km_sub_title_path):
        #     debug(f"Subtitle does not exist: {km_sub_title_path}")
        #     text = await service.translate_sub_title(str(en_sub_title_path), km_sub_title_path)
        #     debug(text)
        
        dd([
            input_video_path,
            ex_audio_output_path
        ])
        
        await service.extract_audio(input_video_path, ex_audio_output_path)

        if not os.path.exists(audio_output_path):
            debug(f"Audio file does not exist: {audio_output_path}")
            audio = await service.subtitle_to_voice(km_sub_title_path, audio_output_path)
            debug(audio)

        # if not os.path.exists(output_video_path):
        #     debug(f"Video file does not exist: {audio_output_path}")
        #     service.combine_video_audio(input_video_path, audio_output_path, output_video_path)

        # if not os.path.exists(video_subtitle_path):
        #     debug(f"Video with subtitle file does not exist: {video_subtitle_path}")
        #     service.add_subtitles_to_video(input_video_path, km_sub_title_path, video_subtitle_path)

    finally:
        service.cleanup()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="🎥 Video.AI - Process video input with AI options")
    parser.add_argument("--video_name", help="Vide file name")
    parser.add_argument("--input_dir", help="Input path", default=None)
    parser.add_argument("--output_dir", help="Output path", default=None)
    asyncio.run(main(parser.parse_args()))
