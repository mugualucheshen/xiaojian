# AGENTS.md — xiaojian 项目工作指南

> 凯利(编程首席工程师)在本项目工作时必读。

## 1. 项目身份

- **产品名**:小剪 / XiaoJian
- **类型**:跨平台桌面视频剪辑器(macOS + Windows)
- **技术栈**:Tauri 2 + React + TypeScript + FFmpeg(Rust 绑定)
- **许可证**:MIT(待定,见 PRD §6)
- **根目录**:`/Users/longxia/Projects/xiaojian/`

## 2. 目录约定

```
xiaojian/
├── docs/                 # 产品文档(PRD、架构、用户手册)
├── src/                  # 源代码
│   ├── frontend/         # React + TS 前端
│   ├── backend/          # Rust + Tauri 后端
│   └── ffmpeg-bridge/    # FFmpeg 集成层
├── assets/               # 图标、样例视频
├── tests/                # 端到端测试
├── README.md
├── LICENSE
└── AGENTS.md             # 本文件
```

## 3. 开发铁律(来自 SOUL.md,本项目专属强化)

- ✅ **可运行优先**:代码不跑通不算交付
- ✅ **真实验证**:用 ffmpeg 实测一个真实切片任务
- ✅ **借鉴思路不抄代码**:LosslessCut 是 GPL,我们用 MIT,**禁止直接复制其源码**
- ✅ **小步快跑**:每完成一个 Sprint,跑通核心命令再继续
- ❌ **不演示技术细节**:不向老板讲装饰器/生命周期
- ❌ **不擅跑破坏性操作**:rm -rf / 删除源码前必须确认

## 4. 命令速查

```bash
# 项目根
cd /Users/longxia/Projects/xiaojian

# 查看 PRD
open docs/PRD.md

# 启动 Tauri 开发(待 Tauri 装好后)
cd src/frontend && npm run tauri dev

# 跑测试
cd src/frontend && npm test
cd src/backend  && cargo test

# 🚀 一键生产构建(macOS 当前架构,.app + .dmg)
./build.sh
# 详见 docs/BUILD.md(支持 --target universal / --skip-frontend / --debug 等参数)
```

## 5. 跨角色协作

| 需要… | 转给… |
|------|------|
| 装 Rust/Node 工具链 | **IT管理员** |
| 部署到 GitHub Releases | **IT管理员** |
| 写 README 推广文案 | **内容创作** |
| 视频剪辑逻辑的具体实现 | **我(凯利)负责** |
| 选型/技术路线拍板 | **首席执行官** |

## 6. 审计要点(阶段 4 用)

- 依赖安全:`npm audit` / `cargo audit`
- 许可证合规:CI 跑 `npx license-checker --failOn 'GPL'`
- 代码质量:ESLint + Clippy
- 性能:导出 1080p 30s 视频 < 30s

## 7. 一键生产构建(老板向)

`./build.sh` 一条命令跑完:依赖检查 → Python 引擎真实验证(US-01 ffmpeg 切片)→ 前端构建 → Tauri 构建 → 打包 .app/.dmg。

| 平台 | 产物 | 实测大小 | 备注 |
|------|------|---------|------|
| macOS 当前架构 | `.app` + `.dmg` | 13M / 3.8M(压缩) | v0.1.1 在 Apple Silicon 跑通 |
| macOS 通用包 | `.app` + `.dmg` | — | `./build.sh --target universal` |
| Windows 10/11 | `.msi` + `.exe` | — | 需在 Windows / 交叉编译环境跑 |

**首次 release 编译时间**:Apple Silicon 大约 12-15 分钟(其中 wry + LTO 占大头)。**增量编译**:44 秒。

**常见踩坑**(已记入 build.sh 自动处理):

- `frontendDist` 必须用 `../../frontend/dist`(tauri.conf.json 路径基于 src-tauri 目录)
- `bundle.identifier` 不能以 `.app` 结尾(macOS 应用后缀冲突)
- `bundle.category` 必须是 Tauri LSApplicationCategory 枚举值(`Video`,`DeveloperTool`,`Music`...),自造词(如 `VideoEditor`)会报 `invalid category`
- macOS DMG 打包需要 `icons/icon.icns`(用 `tauri icon <大png> --output icons` 自动生成)
- tauri-cli 装在 `frontend/node_modules/.bin/tauri`,**不是** `cargo tauri`(项目用 npm 装的)

**已验证**:v0.1.1 在 Apple Silicon 上 `open 小剪 (XiaoJian).app` 可正常启动,进程稳定。

