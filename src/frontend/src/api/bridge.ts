// 小剪 - Tauri 桥接层
//
// 用途:把 Rust 后端命令包装成纯 TS 函数,前端只调这些函数,不直接碰 invoke。
// 未来如果换了后端(Rust 内部实现),只改这一个文件。

import { invoke } from "@tauri-apps/api/core";

export interface MediaInfo {
  path: string;
  duration: number;
  width: number;
  height: number;
  has_video: boolean;
  has_audio: boolean;
  video_codec: string | null;
  audio_codec: string | null;
  fps: number;
}

export interface JobResult {
  outputs: string[];
  message: string;
}

export async function probeMedia(path: string): Promise<MediaInfo> {
  return await invoke<MediaInfo>("cmd_probe", { path });
}

export async function splitVideo(
  input: string,
  marks: number[],
  outputDir: string,
): Promise<JobResult> {
  return await invoke<JobResult>("cmd_split", {
    input,
    marks,
    outputDir,
  });
}

export async function extractAudio(
  input: string,
  output: string,
  format: string,
  bitrate: string,
): Promise<JobResult> {
  return await invoke<JobResult>("cmd_extract", {
    input,
    output,
    format,
    bitrate,
  });
}

export async function mixVideo(
  video: string,
  bgm: string,
  output: string,
  mainVolume: number,
  bgmVolume: number,
): Promise<JobResult> {
  return await invoke<JobResult>("cmd_mix", {
    video,
    bgm,
    output,
    mainVolume,
    bgmVolume,
  });
}
