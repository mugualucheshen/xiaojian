"""单元测试:ffmpeg_tools 工具函数(无需真实视频)。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from xiaojian.ffmpeg_tools import (
    fmt_time,
    Segment,
    MediaInfo,
    ExportOptions,
    FFmpegNotFoundError,
)


def test_fmt_time():
    assert fmt_time(0) == "00:00:00.000"
    assert fmt_time(1.5) == "00:00:01.500"
    assert fmt_time(65.123) == "00:01:05.123"
    assert fmt_time(3725.5) == "01:02:05.500"
    assert fmt_time(-1) == "00:00:00.000"  # 负数被夹到 0
    print("✓ test_fmt_time")


def test_segment():
    s = Segment(start=1.0, end=3.0, label="intro")
    assert s.duration == 2.0
    assert s.label == "intro"
    print("✓ test_segment")


def test_segment_zero():
    s = Segment(start=5.0, end=5.0)
    assert s.duration == 0.0
    print("✓ test_segment_zero")


def test_media_info_resolution():
    info = MediaInfo(path="x.mp4", duration=10.0, width=1920, height=1080, has_video=True)
    assert info.resolution == "1920x1080"
    assert info.is_video is True
    print("✓ test_media_info_resolution")


def test_media_info_audio_only():
    info = MediaInfo(path="x.mp3", duration=180.0, has_audio=True)
    assert info.resolution == "audio only"
    assert info.is_video is False
    print("✓ test_media_info_audio_only")


def test_export_options_default():
    opt = ExportOptions()
    assert opt.container == "mp4"
    assert opt.video_codec == "libx264"
    assert opt.crf == 23
    print("✓ test_export_options_default")


def test_ffmpeg_or_ffprobe_available():
    """真实检查:系统必须有 ffmpeg/ffprobe。"""
    import shutil
    assert shutil.which("ffmpeg") is not None, "系统缺 ffmpeg"
    assert shutil.which("ffprobe") is not None, "系统缺 ffprobe"
    print("✓ test_ffmpeg_or_ffprobe_available")


if __name__ == "__main__":
    test_fmt_time()
    test_segment()
    test_segment_zero()
    test_media_info_resolution()
    test_media_info_audio_only()
    test_export_options_default()
    test_ffmpeg_or_ffprobe_available()
    print("\n所有单元测试通过 ✅")
