//! 小剪 (XiaoJian) Tauri 后端入口
//!
//! 这里只做"壳",真正的视频处理委托给:
//!   - 直接调 ffmpeg/ffprobe(从 .app/Contents/Resources/ 找)
//!   - Python 引擎(xiaojian_engine/)做复杂切片/混合
//!
//! 关键修复(v0.2.0):macOS .app 启动时 PATH 不含 /opt/homebrew,
//! 所以"Command::new('ffprobe')" 会 ENOENT。改用 resource_dir() 找 .app 内置的。

use std::path::PathBuf;
use std::process::Command;

use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Error, Debug)]
pub enum XiaoJianError {
    #[error("FFmpeg 未找到(应用包内缺失,请重新安装小剪)")]
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

// ---------- 路径解析:从 .app 内部找 ffmpeg/ffprobe/python 引擎 ----------

/// 拿到 .app 的 Contents/Resources 目录。
/// dev 模式 (cargo tauri dev) 时回退到当前可执行文件旁。
fn resources_dir() -> PathBuf {
    // 优先尝试 std::env::current_exe 推算 .app/Contents/Resources
    if let Ok(exe) = std::env::current_exe() {
        // 生产 .app: .../小剪.app/Contents/MacOS/xiaojian
        //          → 父目录就是 Contents
        if let Some(contents) = exe.parent() {
            // Tauri 2 把 externalBin(fireprobe/ffmpeg)放在 Contents/MacOS/
            // 把 resources(我们的 Python 包)放在 Contents/Resources/
            // 我们需要 Resources/,所以回退到 Contents/Resources
            let res = contents.join("Resources");
            if res.exists() {
                return res;
            }
            // dev: target/debug/xiaojian → 父目录 = target/debug
            return contents.to_path_buf();
        }
    }
    PathBuf::from(".")
}

/// 找到 ffprobe 绝对路径(.app 内置优先,dev 模式回退到 PATH)
///
/// Tauri 2 `bundle.externalBin` 把外部二进制放到 .app/Contents/MacOS/ 下,
/// 而不是 Resources/ 下(macOS codesign 要求)。
fn ffprobe_path() -> Option<PathBuf> {
    // 1. .app/Contents/MacOS/ffprobe (Tauri externalBin)
    if let Ok(exe) = std::env::current_exe() {
        if let Some(macos_dir) = exe.parent() {
            let p = macos_dir.join("ffprobe");
            if p.exists() {
                return Some(p);
            }
        }
    }
    // 2. dev 模式回退:which ffprobe
    which("ffprobe")
}

/// 找到 ffmpeg 绝对路径(给 Python 引擎用)
fn ffmpeg_path() -> Option<PathBuf> {
    if let Ok(exe) = std::env::current_exe() {
        if let Some(macos_dir) = exe.parent() {
            let p = macos_dir.join("ffmpeg");
            if p.exists() {
                return Some(p);
            }
        }
    }
    which("ffmpeg")
}

/// 找到 Python 引擎根目录。
///
/// `python -m xiaojian.cli` 启动时,需要 `xiaojian/` 这个包目录在 PYTHONPATH 上。
/// PYTHONPATH 应该指向**包含 xiaojian/ 包的父目录**。
///
/// Tauri 2 把 `bundle.resources` 镜像到 .app/Contents/Resources/ 下,
/// 路径里的 `../` 会被替换为 `_up_/`。所以 `../../../xiaojian_engine/xiaojian`
/// 在 .app 里变成 `Resources/_up_/_up_/_up_/xiaojian_engine/xiaojian/`。
fn engine_root() -> PathBuf {
    let res = resources_dir();
    // 候选路径(生产/开发都覆盖)
    let candidates = [
        // 生产 .app 标准镜像
        res.join("_up_")
            .join("_up_")
            .join("_up_")
            .join("xiaojian_engine"),
        res.join("_up_").join("_up_").join("xiaojian_engine"),
        res.join("_up_").join("xiaojian_engine"),
        res.join("xiaojian_engine"),
    ];
    for c in &candidates {
        if c.join("xiaojian").join("__init__.py").exists() {
            return c.clone();
        }
    }
    // dev 模式:CARGO_MANIFEST_DIR 上两级 + /xiaojian_engine
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.pop(); // src/backend
    p.pop(); // src
    p.push("xiaojian_engine");
    if p.exists() {
        return p;
    }
    // fallback:空路径,run_engine 会报错提示
    res
}

/// `which name` 等价物
fn which(name: &str) -> Option<PathBuf> {
    if let Some(paths) = std::env::var_os("PATH") {
        for dir in std::env::split_paths(&paths) {
            let candidate = dir.join(name);
            if candidate.is_file() {
                return Some(candidate);
            }
        }
    }
    None
}

/// 找到 python 解释器(系统 PATH 里)
fn python_path() -> Option<PathBuf> {
    which("python3").or_else(|| which("python"))
}

fn run_engine(args: &[&str]) -> CmdResult<String> {
    let engine = engine_root();
    if !engine.exists() {
        return Err(XiaoJianError::EngineError(format!(
            "Python 引擎目录不存在: {}",
            engine.display()
        )));
    }
    let engine_str = engine
        .to_str()
        .ok_or_else(|| XiaoJianError::EngineError("引擎路径包含非 UTF-8 字符".to_string()))?;

    let py = python_path().ok_or(XiaoJianError::FfmpegNotFound)?;

    let output = Command::new(&py)
        .args(["-m", "xiaojian.cli"])
        .args(args)
        .env("PYTHONPATH", engine_str)
        .env("LC_ALL", "en_US.UTF-8")
        // 告诉 Python 引擎 ffmpeg 在哪(否则它也会 ENOENT)
        .env(
            "XIAOJIAN_FFMPEG",
            ffmpeg_path()
                .as_ref()
                .map(|p| p.to_string_lossy().into_owned())
                .unwrap_or_default(),
        )
        .env(
            "XIAOJIAN_FFPROBE",
            ffprobe_path()
                .as_ref()
                .map(|p| p.to_string_lossy().into_owned())
                .unwrap_or_default(),
        )
        .current_dir(&engine)
        .output()?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(XiaoJianError::EngineError(stderr));
    }
    Ok(String::from_utf8_lossy(&output.stdout).to_string())
}

// ---------- Tauri 命令(给前端调用) ----------

/// 查看媒体信息
#[tauri::command]
fn cmd_probe(path: String) -> CmdResult<MediaInfoDto> {
    let ffprobe = ffprobe_path().ok_or(XiaoJianError::FfmpegNotFound)?;

    let out = Command::new(&ffprobe)
        .args([
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
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
fn cmd_split(input: String, marks: Vec<f64>, output_dir: String) -> CmdResult<JobResult> {
    let marks_str = marks
        .iter()
        .map(|v| v.to_string())
        .collect::<Vec<_>>()
        .join(",");
    let stdout = run_engine(&["split", &input, "--marks", &marks_str, "-o", &output_dir])?;
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
        "extract",
        &input,
        "-o",
        &output,
        "--format",
        &format,
        "--bitrate",
        &bitrate,
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
        "mix",
        &video,
        &bgm,
        "-o",
        &output,
        "--main-volume",
        &mv,
        "--bgm-volume",
        &bv,
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
