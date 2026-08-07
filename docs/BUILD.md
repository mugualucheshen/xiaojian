# 小剪 — 一键生产构建手册

> 老板向:不需要懂 Rust/Tauri,只需要跑一行命令。

## 一句话起步

```bash
cd /Users/longxia/Projects/xiaojian
./build.sh
```

跑完会输出:
- ✅ 引擎自检通过(真实 ffmpeg 切了一段视频)
- ✅ 前端构建完成
- ✅ Tauri 构建完成
- 产物路径

## 产物位置

```
src/backend/src-tauri/target/release/bundle/
├── macos/小剪 (XiaoJian).app         ← 双击可直接打开(13MB)
└── dmg/小剪 (XiaoJian)_0.1.1_aarch64.dmg  ← 可分发的安装包(3.8MB)
```

把 `.dmg` 双击挂载 → 把 `.app` 拖进 `/Applications` 即可。

## 常用变体

| 想干嘛 | 命令 |
|--------|------|
| macOS 通用包(Intel + Apple Silicon) | `./build.sh --target universal` |
| 只重打 Tauri(前端没改) | `./build.sh --skip-frontend` |
| 出 Windows .msi | 必须在 Windows / 交叉编译机跑;脚本本身通用 |
| 看帮助 | `./build.sh --help` |

## 实测时间

| 阶段 | 首次 | 之后 |
|------|------|------|
| 引擎自检 | 5s | 5s |
| 前端构建 | < 1s | < 1s |
| Tauri release 编译 | 12-15 分钟 | ~45 秒 |
| DMG 打包 | < 5 秒 | < 5 秒 |

首次构建会下载并编译 ~400 个 Rust crate,慢是正常的,跑一次后增量很快。

## 常见问题

**Q: 跑完没产物?**
A: 看终端末尾 `==> 产物位置` 段落,路径会列出来。

**Q: 想改图标?**
A: 把 1024×1024 的 PNG 放进 `assets/`,然后跑 `tauri icon <png> --output src/backend/src-tauri/icons` 重新生成全套。

**Q: 想换版本号?**
A: 同时改三处:
- `src/frontend/package.json` → `version`
- `src/backend/src-tauri/Cargo.toml` → `version`
- `src/backend/src-tauri/tauri.conf.json` → `version`

**Q: ffmpeg 没装?**
A: 引擎自检会报错并中止。`brew install ffmpeg` 装好后重跑。

**Q: Windows 怎么打?**
A: 在 Windows 上跑同样命令(Git Bash 或 WSL 都行,需要装 Rust + Node + WebView2)。或用 GitHub Actions 在 CI 里跑跨平台构建——这步以后接。

## 文件清单

| 文件 | 用途 |
|------|------|
| `build.sh` | 一键构建入口 |
| `src/backend/src-tauri/tauri.conf.json` | Tauri 配置(窗口、bundle、图标) |
| `src/backend/src-tauri/Cargo.toml` | Rust 依赖 |
| `src/frontend/package.json` | 前端依赖与脚本 |
| `AGENTS.md` §7 | 给 AI 工程师看的踩坑记录 |
