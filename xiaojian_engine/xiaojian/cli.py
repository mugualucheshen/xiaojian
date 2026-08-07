"""小剪 (XiaoJian) CLI — 视频分段、音频提取、混合剪辑。

对应 PRD 用户故事:
  US-01  split      视频分段拆解
  US-02  extract    音频提取
  US-03  mix        混合剪辑(视频 + 背景音乐)
  US-04  replace    替换音轨
  US-05  probe      查看媒体信息

用法:
  xiaojian split  <视频>  -o 输出目录  --marks 0,30,60,90
  xiaojian extract <视频> -o 输出.mp3   --format mp3 --bitrate 192k
  xiaojian mix    <视频> <BGM> -o 输出.mp4  --bgm-volume 0.3
  xiaojian replace <视频> <新音频> -o 输出.mp4
  xiaojian probe  <媒体文件>
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import List

from xiaojian import __version__
from xiaojian.ffmpeg_tools import (
    Segment,
    ExportOptions,
    XiaoJianError,
    FFmpegNotFoundError,
    probe,
    split_video,
    cut_segment,
    extract_audio,
    mix_audio,
    replace_audio,
    fmt_time,
)


# ---------- 子命令实现 ----------

def cmd_probe(args: argparse.Namespace) -> int:
    """查看媒体元信息。"""
    info = probe(args.input)
    print(f"路径:     {info.path}")
    print(f"时长:     {info.duration:.2f}s  ({fmt_time(info.duration)})")
    print(f"分辨率:   {info.resolution}")
    if info.has_video:
        print(f"视频编码: {info.video_codec}  FPS: {info.fps}")
    if info.has_audio:
        print(f"音频编码: {info.audio_codec}")
    print(f"码率:     {info.bit_rate / 1000:.0f} kbps")
    return 0


def cmd_split(args: argparse.Namespace) -> int:
    """按时间点/片段列表分段导出。"""
    marks = [float(x.strip()) for x in args.marks.split(",") if x.strip()]
    if not marks:
        print("错误: --marks 不能为空,示例: --marks 0,30,60,90", file=sys.stderr)
        return 2

    marks = sorted(set([0.0] + marks + [probe(args.input).duration]))
    segments: List[Segment] = []
    for i in range(len(marks) - 1):
        if marks[i + 1] > marks[i]:
            segments.append(Segment(start=marks[i], end=marks[i + 1]))

    options = ExportOptions(
        container=args.container,
        video_codec=args.vcodec,
        audio_codec=args.acodec,
        crf=args.crf,
    )

    out_dir = args.output or (Path(args.input).stem + "_segments")
    outputs = split_video(
        src=args.input,
        segments=segments,
        out_dir=out_dir,
        name_template=args.template,
        options=options,
    )
    print(f"✅ 已切 {len(outputs)} 段,输出目录: {out_dir}")
    for o in outputs:
        print(f"  • {o}")
    return 0


def cmd_extract(args: argparse.Namespace) -> int:
    """从视频提取音频。"""
    start = args.start
    end = args.end
    out = extract_audio(
        src=args.input,
        dst=args.output,
        format=args.format,
        bitrate=args.bitrate,
        start=start,
        end=end,
    )
    print(f"✅ 音频已导出: {out}")
    return 0


def cmd_mix(args: argparse.Namespace) -> int:
    """混合剪辑:视频 + 背景音乐。"""
    out = mix_audio(
        video_src=args.video,
        bgm_src=args.bgm,
        dst=args.output,
        main_volume=args.main_volume,
        bgm_volume=args.bgm_volume,
        bgm_loop=args.loop,
    )
    print(f"✅ 混合剪辑完成: {out}")
    return 0


def cmd_replace(args: argparse.Namespace) -> int:
    """替换音轨。"""
    out = replace_audio(
        video_src=args.video,
        new_audio_src=args.audio,
        dst=args.output,
    )
    print(f"✅ 音轨已替换: {out}")
    return 0


def cmd_cut(args: argparse.Namespace) -> int:
    """单段裁剪(US-01 内部用,也可独立使用)。"""
    options = ExportOptions(video_codec=args.vcodec, crf=args.crf)
    out = cut_segment(
        src=args.input,
        dst=args.output,
        start=args.start,
        end=args.end,
        options=options,
    )
    print(f"✅ 已裁剪: {out}")
    return 0


# ---------- 参数解析 ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="xiaojian",
        description="小剪 (XiaoJian) — 轻量跨平台视频剪辑 CLI",
    )
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    # probe
    sp = sub.add_parser("probe", help="查看媒体元信息")
    sp.add_argument("input", help="媒体文件路径")
    sp.set_defaults(func=cmd_probe)

    # split
    sp = sub.add_parser("split", help="按时间点分段导出")
    sp.add_argument("input", help="视频文件")
    sp.add_argument("-o", "--output", help="输出目录(默认: <原名>_segments)")
    sp.add_argument(
        "--marks", required=True,
        help="分段时间点(秒),逗号分隔,示例: '30,90,180'",
    )
    sp.add_argument("--container", default="mp4", help="容器格式,默认 mp4")
    sp.add_argument("--vcodec", default="copy", help="视频编码,默认 copy(不重编码)")
    sp.add_argument("--acodec", default="aac", help="音频编码,默认 aac")
    sp.add_argument("--crf", type=int, default=23, help="质量,0-51,默认 23")
    sp.add_argument(
        "--template", default="{base}_{index:03d}",
        help="文件命名模板,默认 {base}_{index:03d}",
    )
    sp.set_defaults(func=cmd_split)

    # extract
    sp = sub.add_parser("extract", help="从视频提取音频")
    sp.add_argument("input", help="视频文件")
    sp.add_argument("-o", "--output", required=True, help="输出音频路径")
    sp.add_argument("--format", default="mp3", choices=["mp3", "aac", "wav", "flac"])
    sp.add_argument("--bitrate", default="192k")
    sp.add_argument("--start", type=float, default=None, help="起始时间(秒)")
    sp.add_argument("--end", type=float, default=None, help="结束时间(秒)")
    sp.set_defaults(func=cmd_extract)

    # mix
    sp = sub.add_parser("mix", help="视频 + BGM 混合剪辑")
    sp.add_argument("video", help="视频文件")
    sp.add_argument("bgm", help="背景音乐文件")
    sp.add_argument("-o", "--output", required=True, help="输出视频路径")
    sp.add_argument("--main-volume", type=float, default=1.0, help="原声音量,0-2")
    sp.add_argument("--bgm-volume", type=float, default=0.3, help="BGM 音量,0-2")
    sp.add_argument("--no-loop", dest="loop", action="store_false")
    sp.set_defaults(func=cmd_mix)

    # replace
    sp = sub.add_parser("replace", help="替换视频音轨")
    sp.add_argument("video", help="视频文件")
    sp.add_argument("audio", help="新音频文件")
    sp.add_argument("-o", "--output", required=True, help="输出视频路径")
    sp.set_defaults(func=cmd_replace)

    # cut (单段)
    sp = sub.add_parser("cut", help="单段裁剪")
    sp.add_argument("input", help="视频文件")
    sp.add_argument("-o", "--output", required=True, help="输出视频路径")
    sp.add_argument("--start", type=float, required=True, help="起始时间(秒)")
    sp.add_argument("--end", type=float, required=True, help="结束时间(秒)")
    sp.add_argument("--vcodec", default="copy")
    sp.add_argument("--crf", type=int, default=23)
    sp.set_defaults(func=cmd_cut)

    return p


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FFmpegNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 3
    except XiaoJianError as e:
        print(f"❌ 错误: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
