import asyncio
import os
import shutil
import logging
import subprocess

logger = logging.getLogger("wavora.clipper")

async def slice_audio_async(
    input_path: str, 
    output_path: str, 
    start_time: float, 
    end_time: float
) -> None:
    """
    Executes an async, non-blocking FFmpeg subprocess to accurately slice a portion of an audio file.
    Uses 'libmp3lame' to ensure standard stream-ready MP3 frame headers.
    """
    # 1. Ensure FFmpeg is accessible on system PATH
    if not shutil.which("ffmpeg"):
        error_msg = "ffmpeg binary is not installed or not present in system PATH"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # 2. Verify source audio URL exists (Removed local file check since input is remote)
    if not input_path or not input_path.startswith("http"):
        error_msg = f"Invalid source audio URL: {input_path}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # Ensure parent output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 3. Formulate precise FFmpeg command parameters
    # -y: overwrite output files without asking
    # -ss: start time offset
    # -to: end time offset
    # -i: input file path
    # -c:a libmp3lame: transcode using standard high-compatibility MP3 encoder
    # -b:a 128k: output bitrate
    cmd = [
        "ffmpeg",
        "-y",
        "-ss", f"{start_time:.3f}",
        "-to", f"{end_time:.3f}",
        "-i", input_path,
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        output_path
    ]

    logger.info(f"Launching FFmpeg async subprocess command: {' '.join(cmd)}")

    try:
        # 4. Spawn the non-blocking subprocess using threads for Windows safety
        def run_ffmpeg():
            return subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
        process = await asyncio.to_thread(run_ffmpeg)

        # 5. Handle errors if the command fails
        if process.returncode != 0:
            error_details = process.stderr.strip()
            logger.error(f"FFmpeg execution failed (Exit Code {process.returncode}): {error_details}")
            raise RuntimeError(f"FFmpeg slicing failed (exit code {process.returncode}): {error_details}")

        logger.info(f"[OK] Sliced audio successfully saved: {output_path}")

    except Exception as e:
        logger.error(f"Failed to execute FFmpeg slicing task: {e}")
        raise
