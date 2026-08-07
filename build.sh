#!/usr/bin/env bash
# 小剪 (XiaoJian) 一键生产构建
# 用法:
#   ./build.sh                # 默认 macOS 当前架构(.app + .dmg)
#   ./build.sh --target universal   # macOS 通用包(Intel + Apple Silicon)
#   ./build.sh --skip-frontend      # 跳过 npm build(只跑 Tauri)
#   ./build.sh --debug              # 跑 debug 模式,不产出发布包
#
# 产物位置:src/backend/src-tauri/target/release/bundle/{dmg,macos}/

set -euo pipefail

# ---------- 参数解析 ----------
SKIP_FRONTEND=0
DEBUG_BUILD=0
TARGET_FLAG=""
PLATFORM_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --skip-frontend) SKIP_FRONTEND=1; shift ;;
    --debug)         DEBUG_BUILD=1; shift ;;
    --target)
      TARGET_FLAG="--target $2"
      shift 2
      ;;
    --platform)      PLATFORM_FLAG="$2"; shift 2 ;;
    -h|--help)
      cat <<'EOF'
小剪 (XiaoJian) 一键生产构建

用法:
  ./build.sh                          默认 macOS 当前架构(.app + .dmg)
  ./build.sh --target universal       macOS 通用包(Intel + Apple Silicon)
  ./build.sh --platform dmg,msi       指定打包格式
  ./build.sh --skip-frontend          跳过 npm build(只跑 Tauri)
  ./build.sh --debug                  跑 debug 模式,不产出发布包

产物位置:
  src/backend/src-tauri/target/release/bundle/
EOF
      exit 0
      ;;
    *)
      echo "未知参数: $1"; exit 1 ;;
  esac
done

# ---------- 路径 ----------
ROOT="$(cd "$(dirname "$0")" && pwd)"
FRONTEND="$ROOT/src/frontend"
TAURI="$ROOT/src/backend/src-tauri"

cd "$ROOT"

# ---------- 颜色 ----------
B="\033[1m"; G="\033[32m"; Y="\033[33m"; R="\033[31m"; X="\033[0m"
say()   { printf "${B}==>${X} %s\n" "$*"; }
ok()    { printf "${G}✓${X} %s\n" "$*"; }
warn()  { printf "${Y}!${X} %s\n" "$*"; }
fail()  { printf "${R}✗${X} %s\n" "$*"; exit 1; }

# ---------- 环境检查 ----------
say "检查依赖"
for cmd in cargo node npm python3 ffmpeg ffprobe; do
  command -v "$cmd" >/dev/null 2>&1 || fail "缺少依赖: $cmd"
  ok "$cmd: $(command -v "$cmd")"
done

# ---------- 引擎自检(真实验证 ffmpeg 跑通) ----------
say "引擎自检:跑一次 US-01 分段拆解(真 ffmpeg)"
mkdir -p "$ROOT/test_assets/out/build_check"
PYTHONPATH="$ROOT/xiaojian_engine" python3 -m xiaojian.cli split \
  "$ROOT/test_assets/sample.mp4" \
  --marks 5,10,15,20,25 \
  -o "$ROOT/test_assets/out/build_check" >/dev/null
N=$(ls "$ROOT/test_assets/out/build_check" | wc -l | tr -d ' ')
[[ "$N" -gt 0 ]] || fail "引擎自检失败:没有产出任何片段"
ok "引擎自检通过:产出 $N 段"

# ---------- 前端构建 ----------
if [[ $SKIP_FRONTEND -eq 0 ]]; then
  say "构建前端"
  cd "$FRONTEND"
  if [[ ! -d node_modules ]]; then
    warn "node_modules 不存在,先 npm ci"
    npm ci
  fi
  npm run build
  cd "$ROOT"
  ok "前端构建完成"
else
  warn "跳过前端构建(--skip-frontend)"
fi

# ---------- Tauri 构建 ----------
say "构建 Tauri(可能耗时几分钟)"
cd "$TAURI"

if [[ $DEBUG_BUILD -eq 1 ]]; then
  cargo build --release=false
  ok "Debug 构建完成(无安装包)"
  exit 0
fi

# tauri-cli 装在 frontend/node_modules/.bin/tauri(项目用 npm 装的)
TAURI_CLI="$FRONTEND/node_modules/.bin/tauri"
[[ -x "$TAURI_CLI" ]] || fail "找不到 tauri-cli: $TAURI_CLI(先 cd src/frontend && npm install)"

cd "$TAURI"
"$TAURI_CLI" build $TARGET_FLAG ${PLATFORM_FLAG:+--bundles "$PLATFORM_FLAG"}
cd "$ROOT"
ok "Tauri 构建完成"

# ---------- 产物汇总 ----------
say "产物位置"
BUNDLE="$TAURI/target/release/bundle"
if [[ -d "$BUNDLE" ]]; then
  find "$BUNDLE" -maxdepth 3 -type f \( -name "*.dmg" -o -name "*.app" -o -name "*.msi" -o -name "*.exe" -o -name "*.deb" -o -name "*.AppImage" \) 2>/dev/null | while read f; do
    size=$(du -h "$f" | cut -f1)
    printf "  %s  (%s)\n" "$f" "$size"
  done
fi

echo
ok "� 全部完成"
