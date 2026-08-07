"""FFmpeg 工具集 — 调系统 ffmpeg 二进制,不依赖 Python FFmpeg 绑定。

设计原则:
1. 用 subprocess + 系统 ffmpeg,避免 ffmpeg-python 的 C 编译依赖
2. 用 dataclass 做数据模型,类型清晰
3. 所有时间统一为秒(float),内部按需转 HH:MM:SS.xxx
4. 抛 XiaoJianError 让上层统一处理
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional


# ---------- 错误类型 ----------

class XiaoJianError(Exception):
    """小剪业务错误,所有自定义异常继承自此。"""
    pass


class FFmpegNotFoundError(XiaoJianError):
    """系统找不到 ffmpeg 二进制。"""
    pass


class FFprobeError(XiaoJianError):
    """ffprobe 无法解析输入文件。"""
    pass


# ---------- 数据模型 ----------

@dataclass
class MediaInfo:
    """媒体文件元信息(ffprobe 结果)。"""
    path: str
    duration: float          # 秒
    width: int = 0
    height: int = 0
    has_video: bool = False
    has_audio: bool = False
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    fps: float = 0.0
    bit_rate: int = 0

    @property
    def is_video(self) -> bool:
        return self.has_video

    @property
    def resolution(self) -> str:
        if not self.has_video:
            return "audio only"
        return f"{self.width}x{self.height}"


@dataclass
class Segment:
    """视频的一个时间区间(用于分段拆解)。"""
    start: float   # 秒
    end: float     # 秒
    label: str = ""  # 可选,导出时用作文档名一部分

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ExportOptions:
    """导出参数。"""
    container: str = "mp4"               # mp4 / mkv / mov
    video_codec: str = "libx264"         # libx264 / libx265 / copy
    audio_codec: str = "aac"             # aac / copy
    crf: int = 23                        # 0-51,越低越清晰
    preset: str = "medium"               # ultrafast..veryslow
    audio_bitrate: str = "192k"          # 仅当重编码时生效
    extra_args: List[str] = field(default_factory=list)


# ---------- FFmpeg 探测 ----------

def ensure_ffmpeg() -> str:
    """检查系统 ffmpeg 是否可用,返回绝对路径。"""
    path = shutil.which("ffmpeg")
    if not path:
        raise FFmpegNotFoundError(
            "未找到 ffmpeg。请先安装:macOS: brew install ffmpeg | Windows: choco install ffmpeg"
        )
    return path


def ensure_ffprobe() -> str:
    """检查 ffprobe 可用性。"""
    path = shutil.which("ffprobe")
    if not path:
        raise FFmpegNotFoundError("未找到 ffprobe(应与 ffmpeg 同装)。")
    return path


def probe(path: str) -> MediaInfo:
    """用 ffprobe 读取媒体信息。"""
    ffprobe = ensure_ffprobe()
    p = Path(path)
    if not p.exists():
        raise XiaoJianError(f"文件不存在: {path}")

    cmd = [
        ffprobe, "-v", "error",
        "-print_format", "json",
        "-show_format", "-show_streams",
        str(p),
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=30
        )
    except subprocess.CalledProcessError as e:
        raise FFprobeError(f"ffprobe 失败: {e.stderr.strip()}") from e
    except subprocess.TimeoutExpired as e:
        raise FFprobeError("ffprobe 超时") from e

    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    fmt = data.get("format", {})

    info = MediaInfo(
        path=str(p.resolve()),
        duration=float(fmt.get("duration", 0.0)),
        bit_rate=int(fmt.get("bit_rate", 0)),
    )

    for s in streams:
        codec_type = s.get("codec_type")
        if codec_type == "video" and not info.has_video:
            info.has_video = True
            info.width = int(s.get("width", 0))
            info.height = int(s.get("height", 0))
            info.video_codec = s.get("codec_name")
            # fps: r_frame_rate = "30/1"
            rfr = s.get("r_frame_rate", "0/1")
            try:
                num, den = rfr.split("/")
                info.fps = round(int(num) / int(den), 2) if int(den) else 0.0
            except Exception:
                info.fps = 0.0
        elif codec_type == "audio" and not info.has_audio:
            info.has_audio = True
            info.audio_codec = s.get("codec_name")

    return info


# ---------- 时间格式 ----------

def fmt_time(seconds: float) -> str:
    """秒 -> ffmpeg 接受的 HH:MM:SS.xxx 字符串。"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


# ---------- 核心操作 ----------

def _run_ffmpeg(args: List[str], timeout: int = 600) -> None:
    """执行 ffmpeg,失败抛 XiaoJianError。"""
    ffmpeg = ensure_ffmpeg()
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        if result.returncode != 0:
            raise XiaoJianError(
                f"ffmpeg 失败 (exit {result.returncode}):\n{result.stderr.strip()}"
            )
    except subprocess.TimeoutExpired as e:
        raise XiaoJianError(f"ffmpeg 超时(>{timeout}s)") from e


def cut_segment(
    src: str,
    dst: str,
    start: float,
    end: float,
    options: Optional[ExportOptions] = None,
) -> str:
    """裁剪 [start, end] 区间,无重编码(极速)。

    - 默认 stream copy,几乎瞬时完成
    - 若 options.video_codec != 'copy',则重编码
    返回输出路径。
    """
    opts = options or ExportOptions()
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    if end <= start:
        raise XiaoJianError(f"end ({end}) 必须 > start ({start})")

    duration = end - start
    args = [
        "-ss", fmt_time(start),
        "-i", src,
        "-t", fmt_time(duration),
    ]

    if opts.video_codec == "copy":
        args += ["-c", "copy"]
    else:
        args += [
            "-c:v", opts.video_codec,
            "-preset", opts.preset,
            "-crf", str(opts.crf),
            "-c:a", opts.audio_codec,
            "-b:a", opts.audio_bitrate,
        ]

    args += ["-avoid_negative_ts", "make_zero", dst]
    args += opts.extra_args

    _run_ffmpeg(args)
    return dst


def split_video(
    src: str,
    segments: List[Segment],
    out_dir: str,
    name_template: str = "{base}_{index:03d}",
    options: Optional[ExportOptions] = None,
) -> List[str]:
    """按 segments 列表批量切片导出。返回输出文件路径列表。"""
    if not segments:
        raise XiaoJianError("segments 不能为空")

    info = probe(src)
    base = Path(src).stem
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    outputs = []
    for i, seg in enumerate(segments, start=1):
        if seg.end > info.duration + 0.1:
            raise XiaoJianError(
                f"第 {i} 段结束时间 {seg.end:.2f}s 超出视频总长 {info.duration:.2f}s"
            )
        name = name_template.format(base=base, index=i, label=seg.label)
        dst = str(out_path / f"{name}.{options.container if options else 'mp4'}")
        cut_segment(src, dst, seg.start, seg.end, options)
        outputs.append(dst)
    return outputs


def extract_audio(
    src: str,
    dst: str,
    format: str = "mp3",
    bitrate: str = "192k",
    start: Optional[float] = None,
    end: Optional[float] = None,
) -> str:
    """从视频提取音轨。format: mp3 / aac / wav / flac。"""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    args = []
    if start is not None:
        args += ["-ss", fmt_time(start)]
    args += ["-i", src]
    if end is not None:
        args += ["-to", fmt_time(end - (start or 0))]
    args += ["-vn", "-acodec", _audio_codec_for(format), "-b:a", bitrate, dst]
    _run_ffmpeg(args)
    return dst


def _audio_codec_for(fmt: str) -> str:
    return {
        "mp3": "libmp3lame",
        "aac": "aac",
        "wav": "pcm_s16le",
        "flac": "flac",
    }.get(fmt.lower(), "aac")


def mix_audio(
    video_src: str,
    bgm_src: str,
    dst: str,
    *,
    main_volume: float = 1.0,
    bgm_volume: float = 0.3,
    bgm_loop: bool = True,
) -> str:
    """混合剪辑:视频原声 + 背景音乐。

    - main_volume: 原声音量倍数(0-2,1=原音量)
    - bgm_volume: BGM 音量倍数
    - bgm_loop: BGM 比视频短时是否用 aloop 滤镜循环到视频时长
    """
    if not (0.0 <= main_volume <= 2.0):
        raise XiaoJianError("main_volume 必须在 0-2")
    if not (0.0 <= bgm_volume <= 2.0):
        raise XiaoJianError("bgm_volume 必须在 0-2")

    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    info = probe(video_src)
    vdur = info.duration

    if bgm_loop:
        # 用 aloop 滤镜把 BGM 循环到视频时长,比 -stream_loop 稳
        filter_complex = (
            f"[1:a]aloop=loop=-1:size=2e9,atrim=0:{vdur},asetpts=PTS-STARTPTS,"
            f"volume={bgm_volume}[bgm];"
            f"[0:a]volume={main_volume}[main];"
            f"[main][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]"
        )
    else:
        filter_complex = (
            f"[0:a]volume={main_volume}[main];"
            f"[1:a]volume={bgm_volume}[bgm];"
            f"[main][bgm]amix=inputs=2:duration=shortest[aout]"
        )

    args = [
        "-i", video_src,
        "-i", bgm_src,
        "-filter_complex", filter_complex,
        "-map", "0:v",
        "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        dst,
    ]
    _run_ffmpeg(args, timeout=1200)
    return dst


def replace_audio(
    video_src: str,
    new_audio_src: str,
    dst: str,
) -> str:
    """替换视频音轨为新的音频。"""
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    args = [
        "-i", video_src,
        "-i", new_audio_src,
        "-map", "0:v",
        "-map", "1:a",
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        dst,
    ]
    _run_ffmpeg(args)
    return dst
