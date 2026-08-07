# 小剪 / XiaoJian

> 轻量、跨平台、开源视频剪辑器。把视频拆开,再随意拼回去。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: macOS | Windows](https://img.shields.io/badge/Platform-macOS%20%7C%20Windows-blue)](#下载)

## ✨ 核心功能

- 🎬 **视频分段拆解** — 按时间点 / 场景自动切片,一键批量导出
- ✂️ **基础剪辑** — 裁剪、删除、拼接多段视频
- 🎵 **音频拆分** — 从视频提取音轨,按区间切分
- 🎚️ **混合剪辑** — 替换音轨、叠加背景音乐、调音量
- 📤 **多格式导出** — MP4 (H.264/HEVC) / MP3 / WAV

## 📥 下载

| 平台 | 安装包 | 状态 |
|------|--------|------|
| macOS 11+ (Intel/Apple Silicon) | `.dmg` | 🚧 v0.2.0 开发中 |
| Windows 10/11 (64-bit) | `.msi` | 🚧 v0.2.0 开发中 |

## 🛠️ 技术栈

- **前端**:React 18 + TypeScript + Vite
- **后端**:Rust + Tauri 2
- **音视频引擎**:FFmpeg 6.x

## 🚀 快速开始(开发者)

```bash
git clone https://github.com/<your-username>/xiaojian.git
cd xiaojian
# 详见 docs/DEV.md
```

## 📖 文档

- [产品说明文档 (PRD)](docs/PRD.md)
- [开发指南](docs/DEV.md)(待写)
- [用户手册](docs/USER.md)(待写)

## 🙏 致谢

本项目参考了以下开源项目(仅借鉴设计思想,未复用其源码):

- [LosslessCut](https://github.com/mifi/lossless-cut) — 分段导出 UX
- [ffmpeg-explorer](https://github.com/antiboredom/ffmpeg-explorer) — 节点式剪辑

## 📄 许可证

[MIT](LICENSE)
