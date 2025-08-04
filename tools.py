import os
import re
import subprocess
import sys
import json
import logging
import edge_tts
import unicodedata

from deep_translator import GoogleTranslator
from pydub import AudioSegment
from pydub.utils import mediainfo
from typing import List, Dict, Optional
from pathlib import Path

from config import EDGE_TTS_VOICES, GOOGLE_LANGUAGES


def dd(data):
    try:
        print(json.dumps(data, indent=4, ensure_ascii=False))
    except TypeError as e:
        if "BufferedRandom" in str(e):
            print(data)
        else:
            raise
    exit(1)


def pp(data):
    try:
        print(json.dumps(data, indent=4, ensure_ascii=False))
    except TypeError as e:
        if "BufferedRandom" in str(e):
            print(data)
        else:
            print(None)


def live_log(text):
    sys.stdout.write(f"\r{text}")
    sys.stdout.flush()


def file_log(text):
    global logger
    logger.debug(text)


def create_logger(name, file="logs/app.log"):
    if not os.path.exists('logs'):
        os.mkdir('logs')

    logging.basicConfig(
        level=logging.DEBUG,  # INFO or DEBUG, WARNING, etc.
        filename=file,  # your log file path
        filemode="w",  # 'w' = overwrite, 'a' = append
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    return logging.getLogger(name)


logger = create_logger(__name__)


class VideoTool:
    def __init__(self):
        # self.temp_dir = tempfile.mkdtemp()

        self.temp_dir = "tmp"
        self.output_dir = "output"

        os.makedirs(self.temp_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

        self.supported_voices = EDGE_TTS_VOICES
        self.supported_languages = GOOGLE_LANGUAGES

    def extract_subtitles(self, video_path: str) -> Optional[str]:
        """Extract existing subtitles from video file"""
        subtitle_path = os.path.join(self.temp_dir, "original.srt")

        try:
            cmd = [
                "ffmpeg",
                "-i",
                video_path,
                "-map",
                "0:s:0",
                "-c:s",
                "srt",
                subtitle_path,
                "-y",
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            return subtitle_path
        except subprocess.CalledProcessError:
            logger.warning("No subtitles found in video")
            return None

    async def extract_audio(video_path: str, audio_output: str):
        process = await asyncio.create_subprocess_exec(
            'ffmpeg',
            '-y',                   # overwrite output if exists
            '-i', video_path,       # input video file
            '-vn',                  # remove video
            '-acodec', 'copy',      # copy audio codec
            audio_output,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg failed:\n{stderr.decode()}")
        else:
            print(f"Audio saved to: {audio_output}")
            
            
    def temp_path(self, path, name=None):
            tmp_path = Path(self.temp_dir) / Path(path).stem
            if name:
                tmp_path = tmp_path / name
            Path(tmp_path).mkdir(parents=True, exist_ok=True)
            return tmp_path

    def parse_srt(self, srt_path: str) -> List[Dict]:
        """Parse SRT subtitle file"""
        subtitles = []

        with open(srt_path, "r", encoding="utf-8") as f:
            content = f.read().strip()

        blocks = content.split("\n\n")

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3:
                index = lines[0]
                timestamp = lines[1]
                text = "\n".join(lines[2:])

                # Parse timestamp
                start_end = timestamp.split(" --> ")
                start_time = self.srt_time_to_seconds(start_end[0])
                end_time = self.srt_time_to_seconds(start_end[1])
                clean_text = re.sub(r'\s+', ' ', text).strip()
                subtitles.append(
                    {
                        "index": int(index),
                        "start": start_time,
                        "end": end_time,
                        # "text": text.strip(),
                        "text": clean_text,
                    }
                )

        return subtitles

    def srt_time_to_seconds(self, time_str: str) -> float:
        """Convert SRT timestamp to seconds"""
        time_str = time_str.replace(",", ".")
        parts = time_str.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    def seconds_to_srt_time(self, seconds: float) -> str:
        """Convert seconds to SRT timestamp format"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace(".", ",")

    def extract_lang_code(self, file_name: str) -> str:
        """
        Extract language code from filename like:
        'video_en.srt' → 'en', 'video_km.srt' → 'km'
        """
        match = re.search(r'[_\.]([a-z]{2,}(?:-[A-Z]{2})?)\.srt$', file_name)
        return match.group(1) if match else None

    async def merge_with_timing(self, audio_files: List[Dict], output_path: str, input_path: str = None):
        final_audio = AudioSegment.silent(duration=0)

        bitrate = "44100"
        duration = 0

        if input_path:
            info = mediainfo(input_path)
            bitrate = info.get("bit_rate", bitrate)
            duration = info.get("duration", duration)

        total_video_duration_ms = float(duration) * 1000

        for segment in audio_files:
            start_ms = int(segment["start"] * 1000)
            duration_ms = int(segment["duration"] * 1000)

            # Load audio file
            audio = AudioSegment.from_file(segment["path"])

            # Trim or pad to exact duration
            audio = audio[:duration_ms].set_frame_rate(int(bitrate))
            if len(audio) < duration_ms:
                silence_padding = AudioSegment.silent(duration=duration_ms - len(audio))
                audio += silence_padding

            # Pad with silence if needed to reach correct start time
            gap = start_ms - len(final_audio)
            if gap > 0:
                final_audio += AudioSegment.silent(duration=gap)

            final_audio += audio
            live_log(f"Merge audio segment {len(final_audio)}")

        if len(final_audio) < total_video_duration_ms:
            final_audio += AudioSegment.silent(duration=total_video_duration_ms - len(final_audio))

        file_log(f"Merged audio segment {len(final_audio)}")

        return final_audio.export(output_path, format="mp3")

    async def translate_sub_title(self, input_path: str, output_path: str):
        source_lang = self.extract_lang_code(input_path)
        target_lang = self.extract_lang_code(output_path)

        with open(input_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Count how many lines need translation (non-empty, non-time/index)
        translatable_lines = [
            line for line in lines
            if line.strip() and not line.strip().isdigit() and '-->' not in line
        ]
        total = len(translatable_lines)
        progress = 0

        translated_lines = []
        translator = GoogleTranslator(source=source_lang, target=target_lang)

        for line in lines:
            stripped = line.strip()
            if stripped == '' or stripped.isdigit() or '-->' in line:
                translated_lines.append(line)
            else:
                translated_text = translator.translate(stripped)
                translated_lines.append(translated_text + '\n')
                progress += 1

                live_log(f"Translated {progress} / {total} lines ({progress * 100 // total}%)")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(translated_lines)
        return translated_lines

    async def subtitle_to_voice(self, subtitle_path: str, output_path: str) -> str:
        target_lang = self.extract_lang_code(subtitle_path)
        voice = self.supported_voices.get(target_lang, "km-KH-PisethNeural")

        audio_files = []
        subtitles = self.parse_srt(subtitle_path)
        audio_temp = self.temp_path(output_path)

        for i, subtitle in enumerate(subtitles):
            live_log(f"Translate subtitle to [{target_lang}]")
            audio_path = os.path.join(audio_temp, f"{i:04d}.wav")

            if not os.path.exists(audio_path):
                live_log(f"Generate [{target_lang}] audio {i:04d}.wav")
                await self.generate_speech(subtitle["text"], voice, audio_path)

            audio_files.append(
                {
                    "path": audio_path,
                    "start": subtitle["start"],
                    "end": subtitle["end"],
                    "duration": subtitle["end"] - subtitle["start"],
                }
            )
            live_log(f"Generated audio for subtitle {i + 1}/{len(subtitles)}")
        file_log(f"Generated audio for subtitle {len(subtitles)}")

        if not os.path.exists(output_path):
            file_log(f"Merge audio not found")
            file_log(f"Merge audio clips to {output_path}")
            await self.merge_with_timing(audio_files, output_path)
        print(output_path)
        return output_path

    async def generate_speech(self, text: str, voice: str, output_path: str):
        """Generate speech using edge-tts"""
        # clean text ។
        text = text.strip().replace("។", "  ")
        text = unicodedata.normalize("NFC", text)
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_path)

    async def create_translated_audio(
            self, subtitles: List[Dict], target_lang: str
    ) -> str:
        """Create translated audio for all subtitles"""
        voice = self.supported_voices.get(target_lang, "en-US-AriaNeural")
        audio_files = []

        for i, subtitle in enumerate(subtitles):
            # Generate speech
            audio_path = os.path.join(self.temp_dir, f"audio_{i:04d}.wav")
            await self.generate_speech(subtitle["text"], voice, audio_path)

            audio_files.append(
                {
                    "path": audio_path,
                    "start": subtitle["start"],
                    "end": subtitle["end"],
                    "duration": subtitle["end"] - subtitle["start"],
                }
            )

            logger.info(f"Generated audio for subtitle {i + 1}/{len(subtitles)}")

        return await self.merge_audio_segments(audio_files)

    async def merge_audio_segments(self, audio_files: List[Dict]) -> str:
        """Merge audio segments with proper timing"""
        if not audio_files:
            return None

        # Get total duration
        total_duration = max(af["end"] for af in audio_files)

        # Create filter complex for ffmpeg
        inputs = []
        filters = []

        for i, af in enumerate(audio_files):
            inputs.extend(["-i", af["path"]])
            # Add delay and trim audio to fit timing
            delay = af["start"]
            duration = af["duration"]
            filters.append(f"[{i}]adelay={int(delay * 1000)}|{int(delay * 1000)}[a{i}]")

        # Mix all audio streams
        mix_filter = "+".join([f"[a{i}]" for i in range(len(audio_files))])
        filters.append(
            f"{mix_filter}amix=inputs={len(audio_files)}:duration=longest[out]"
        )

        merged_audio = os.path.join(self.temp_dir, "merged_audio.wav")

        cmd = (
                ["ffmpeg"]
                + inputs
                + [
                    "-filter_complex",
                    ";".join(filters),
                    "-map",
                    "[out]",
                    "-t",
                    str(total_duration),
                    merged_audio,
                    "-y",
                ]
        )

        subprocess.run(cmd, check=True, capture_output=True)
        return merged_audio

    def create_translated_subtitles(
            self, subtitles: List[Dict], target_lang: str
    ) -> str:
        """Create translated subtitle file"""
        translated_srt = os.path.join(self.temp_dir, f"translated_{target_lang}.srt")

        with open(translated_srt, "w", encoding="utf-8") as f:
            for subtitle in subtitles:
                # In real implementation, translate the text here
                translated_text = f"[{target_lang.upper()}] {subtitle['text']}"

                f.write(f"{subtitle['index']}\n")
                f.write(
                    f"{self.seconds_to_srt_time(subtitle['start'])} --> {self.seconds_to_srt_time(subtitle['end'])}\n"
                )
                f.write(f"{translated_text}\n\n")

        return translated_srt

    def combine_video_audio(self, video_path: str, audio_path: str, output_path: str):
        """Combine original video with translated audio"""
        cmd = [
            "ffmpeg",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest", output_path,
            "-y",
        ]

        subprocess.run(cmd, check=True, capture_output=True)

    def add_subtitles_to_video(
            self, video_path: str, subtitle_path: str, output_path: str
    ):
        """Add subtitles to video file"""
        # Soft subtitle on video / removable
        # cmd = [
        #     "ffmpeg",
        #     "-loglevel",  "debug",
        #     "-i", video_path,
        #     "-i", subtitle_path,
        #     "-c:v", "copy",
        #     "-c:a", "copy",
        #     "-c:s", "mov_text",
        #     output_path,
        #     "-y",
        # ]

        # Burn subtitle to video
        cmd = [
            "ffmpeg",
            "-loglevel", "debug",
            "-i", video_path,
            "-vf", f"subtitles={subtitle_path}",
            "-c:a", "copy",
            output_path,
            "-y",
        ]

        subprocess.run(cmd, check=True, capture_output=True)

    async def translate_video(
            self,
            video_path: str,
            target_lang: str,
            output_path: str,
            include_audio: bool = True,
            include_subtitles: bool = True,
    ) -> Dict:
        """Main method to translate video"""
        try:
            logger.info(f"Starting video translation to {target_lang}")

            # Extract existing subtitles
            subtitle_path = self.extract_subtitles(video_path)
            if not subtitle_path:
                raise ValueError("No subtitles found in video file")

            # Parse subtitles
            subtitles = self.parse_srt(subtitle_path)
            logger.info(f"Found {len(subtitles)} subtitle segments")

            result = {
                "success": True,
                "original_subtitles": len(subtitles),
                "target_language": target_lang,
                "files_created": [],
            }

            if include_audio:
                # Generate translated audio
                logger.info("Generating translated audio...")
                translated_audio = await self.create_translated_audio(
                    subtitles, target_lang
                )

                # Combine with video
                audio_output = output_path.replace(".mp4", f"_audio_{target_lang}.mp4")
                self.combine_video_audio(video_path, translated_audio, audio_output)
                result["files_created"].append(audio_output)
                logger.info(f"Created video with translated audio: {audio_output}")

            if include_subtitles:
                # Create translated subtitles
                translated_srt = self.create_translated_subtitles(
                    subtitles, target_lang
                )

                # Add subtitles to video
                subtitle_output = output_path.replace(
                    ".mp4", f"_subtitles_{target_lang}.mp4"
                )
                self.add_subtitles_to_video(video_path, translated_srt, subtitle_output)
                result["files_created"].append(subtitle_output)
                logger.info(
                    f"Created video with translated subtitles: {subtitle_output}"
                )

            return result

        except Exception as e:
            logger.error(f"Translation failed: {str(e)}")
            return {"success": False, "error": str(e)}

    def list_available_voices(self) -> Dict[str, str]:
        """List available voices for translation"""
        return self.supported_voices.copy()

    def cleanup(self):
        """Clean up temporary files"""
        # import shutil
        # if os.path.exists(self.temp_dir):
        #     shutil.rmtree(self.temp_dir)
