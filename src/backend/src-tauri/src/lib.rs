//! 小剪 (XiaoJian) Tauri 后端入口
//!
//! 这里只做"壳",真正的视频处理委托给 Python 引擎(xiaojian_engine),
//! 通过子进程调用,避免 Rust 重写 FFmpeg 命令。
//! 后期若性能要求高,再把热路径迁到 Rust。

use std::path::PathBuf;
use std::process::Command;

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum XiaoJianError {
    #[error("FFmpeg 未找到,请先安装系统 FFmpeg")]
    FfmpegNotFound,
    #[error("Python 引擎错误: {0}")]
    EngineError(String),
    #[error("参数错误: {0}")]
    InvalidArgument(String),
    #[error("IO 错误: {0}")]
    Io(#[from] std::io::Error),
}

// Tauri 的 invoke handler 需要错误能序列化为 String,这里手动 impl
impl Serialize for XiaoJianError {
    fn serialize<S: serde::Serializer>(&self, s: S) -> std::result::Result<S::Ok, S::Error> {
        s.serialize_str(&self.to_string())
    }
}

type CmdResult<T> = std::result::Result<T, XiaoJianError>;

// ---------- 与前端交互的数据类型 ----------

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct MediaInfoDto {
    pub path: String,
    pub duration: f64,
    pub width: u32,
    pub height: u32,
    pub has_video: bool,
    pub has_audio: bool,
    pub video_codec: Option<String>,
    pub audio_codec: Option<String>,
    pub fps: f64,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct SegmentDto {
    pub start: f64,
    pub end: f64,
    pub label: Option<String>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct JobResult {
    pub outputs: Vec<String>,
    pub message: String,
}

// ---------- 引擎调用 ----------

/// 找到 Python 引擎根目录(xiaojian_engine/)
fn engine_root() -> PathBuf {
    // 开发时 CARGO_MANIFEST_DIR = src/backend/src-tauri
    // 引擎在 <project>/xiaojian_engine
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.pop(); // src/backend
    p.pop(); // src
    p.push("xiaojian_engine");
    p
}

fn run_engine(args: &[&str]) -> CmdResult<String> {
    let engine = engine_root();
    let engine_str = engine.to_str().ok_or_else(|| {
        XiaoJianError::EngineError("引擎路径包含非 UTF-8 字符".to_string())
    })?;

    // 优先 python3,再试 python
    let py = which_python().ok_or(XiaoJianError::FfmpegNotFound)?; // 这里简化,后续会拆

    let output = Command::new(&py)
        .args(["-m", "xiaojian.cli"])
        .args(args)
        .env("PYTHONPATH", engine_str)
        .env("LC_ALL", "en_US.UTF-8")
        .current_dir(engine)
        .output()?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(XiaoJianError::EngineError(stderr));
    }
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

fn which_python() -> Option<String> {
    for cand in ["python3", "python"] {
        if let Ok(out) = Command::new("which").arg(cand).output() {
            if out.status.success() {
                if let Ok(s) = String::from_utf8(out.stdout) {
                    let s = s.trim().to_string();
                    if !s.is_empty() {
                        return Some(s);
                    }
                }
            }
        }
    }
    None
}

// ---------- Tauri 命令(给前端调用) ----------

/// 查看媒体信息
#[tauri::command]
fn cmd_probe(path: String) -> CmdResult<MediaInfoDto> {
    // 让 Python 走 probe,再以 JSON 返回(简化:本版只返回 path 解析)
    // stdout 这里不直接用,真正拿数据走下面 ffprobe
    let _ = run_engine(&["probe", &path])?;
    // stdout 是纯文本,我们用 probe JSON 模式更稳——这里先用 ffprobe 直接拿
    let out = Command::new("ffprobe")
        .args([
            "-v", "error",
            "-print_format", "json",
            "-show_format", "-show_streams",
            &path,
        ])
        .output()?;
    if !out.status.success() {
        return Err(XiaoJianError::EngineError(
            String::from_utf8_lossy(&out.stderr).to_string(),
        ));
    }
    let v: serde_json::Value = serde_json::from_slice(&out.stdout)
        .map_err(|e| XiaoJianError::EngineError(format!("JSON 解析失败: {e}")))?;
    parse_probe(&v, &path)
}

fn parse_probe(v: &serde_json::Value, path: &str) -> CmdResult<MediaInfoDto> {
    let fmt = &v["format"];
    let duration = fmt["duration"]
        .as_str()
        .and_then(|s| s.parse::<f64>().ok())
        .unwrap_or(0.0);

    let mut info = MediaInfoDto {
        path: path.to_string(),
        duration,
        width: 0,
        height: 0,
        has_video: false,
        has_audio: false,
        video_codec: None,
        audio_codec: None,
        fps: 0.0,
    };

    if let Some(streams) = v["streams"].as_array() {
        for s in streams {
            match s["codec_type"].as_str() {
                Some("video") if !info.has_video => {
                    info.has_video = true;
                    info.width = s["width"].as_u64().unwrap_or(0) as u32;
                    info.height = s["height"].as_u64().unwrap_or(0) as u32;
                    info.video_codec = s["codec_name"].as_str().map(String::from);
                    if let Some(rfr) = s["r_frame_rate"].as_str() {
                        if let Some((n, d)) = rfr.split_once('/') {
                            if let (Ok(n), Ok(d)) = (n.parse::<f64>(), d.parse::<f64>()) {
                                if d != 0.0 {
                                    info.fps = (n / d * 100.0).round() / 100.0;
                                }
                            }
                        }
                    }
                }
                Some("audio") if !info.has_audio => {
                    info.has_audio = true;
                    info.audio_codec = s["codec_name"].as_str().map(String::from);
                }
                _ => {}
            }
        }
    }
    Ok(info)
}

/// 分段导出
#[tauri::command]
fn cmd_split(
    input: String,
    marks: Vec<f64>,
    output_dir: String,
) -> CmdResult<JobResult> {
    let marks_str = marks
        .iter()
        .map(|v| v.to_string())
        .collect::<Vec<_>>()
        .join(",");
    let stdout = run_engine(&[
        "split", &input, "--marks", &marks_str, "-o", &output_dir,
    ])?;
    Ok(JobResult {
        outputs: vec![],
        message: stdout,
    })
}

/// 提取音频
#[tauri::command]
fn cmd_extract(
    input: String,
    output: String,
    format: String,
    bitrate: String,
) -> CmdResult<JobResult> {
    let stdout = run_engine(&[
        "extract", &input, "-o", &output, "--format", &format, "--bitrate", &bitrate,
    ])?;
    Ok(JobResult {
        outputs: vec![output],
        message: stdout,
    })
}

/// 混合剪辑
#[tauri::command]
fn cmd_mix(
    video: String,
    bgm: String,
    output: String,
    main_volume: f32,
    bgm_volume: f32,
) -> CmdResult<JobResult> {
    let mv = main_volume.to_string();
    let bv = bgm_volume.to_string();
    let stdout = run_engine(&[
        "mix", &video, &bgm, "-o", &output, "--main-volume", &mv, "--bgm-volume", &bv,
    ])?;
    Ok(JobResult {
        outputs: vec![output],
        message: stdout,
    })
}

// ---------- 入口 ----------

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            cmd_probe,
            cmd_split,
            cmd_extract,
            cmd_mix,
        ])
        .run(tauri::generate_context!())
        .expect("启动 Tauri 应用失败");
}
