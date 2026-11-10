"""ClipConvert Shorts Studio: FFmpeg rendering for authorized source media."""
from __future__ import annotations
import json
import subprocess
from pathlib import Path

def render_short(source: str, output: str, *, logo: str | None = None,
                 title: str = "", mode: str = "fit", start: float = 0,
                 duration: float | None = None) -> dict:
    """Render a 1080x1920 branded short, preserving source audio.

    Source must be an existing local file; URLs are deliberately not accepted.
    """
    src, dst = Path(source), Path(output)
    if not src.is_file() or not src.stat().st_size:
        raise ValueError("A nonempty local source video is required")
    if src.resolve() == dst.resolve():
        raise ValueError("Output must differ from source")
    if mode not in ("fit", "fill"):
        raise ValueError("mode must be fit or fill")
    if not 0 <= start <= 86400 or duration is not None and not 0 < duration <= 14400:
        raise ValueError("Invalid trim range")
    if logo and not Path(logo).is_file():
        raise ValueError("Logo file does not exist")
    if len(title) > 120 or any(ord(c) < 32 for c in title):
        raise ValueError("Invalid title")
    if title:
        raise ValueError("Text overlay requires a configured font; use a transparent logo image instead")
    if mode == "fill":
        vf = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
    else:
        vf = "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2"
    vf += ",setsar=1"
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-y", "-v", "error"]
    if start:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(src)]
    if logo:
        cmd += ["-i", str(Path(logo)), "-filter_complex",
                f"[0:v]{vf}[base];[1:v]scale=180:-1[brand];[base][brand]overlay=W-w-36:36[v]",
                "-map", "[v]"]
    else:
        cmd += ["-vf", vf, "-map", "0:v:0"]
    cmd += ["-map", "0:a?", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac",
            "-b:a", "192k", "-movflags", "+faststart"]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += [str(dst)]
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=1800)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        dst.unlink(missing_ok=True)
        raise RuntimeError("FFmpeg could not render this video")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "stream=codec_type,width,height", "-of", "json", str(dst)],
        capture_output=True, text=True, check=True, timeout=20)
    streams = json.loads(probe.stdout).get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    if (video.get("width"), video.get("height")) != (1080, 1920):
        raise RuntimeError("Unexpected output dimensions")
    return {"path": str(dst), "width": 1080, "height": 1920,
            "audio": any(s.get("codec_type") == "audio" for s in streams)}
