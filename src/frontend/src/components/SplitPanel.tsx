// 分段拆解面板
import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { probeMedia, splitVideo, type MediaInfo } from "../api/bridge";
import { Button, Card, Field } from "./Ui";

export function SplitPanel() {
  const [input, setInput] = useState<string>("");
  const [info, setInfo] = useState<MediaInfo | null>(null);
  const [marksText, setMarksText] = useState<string>("0,30,60,90");
  const [outputDir, setOutputDir] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string>("");

  async function pickInput() {
    const path = await open({
      multiple: false,
      filters: [{ name: "视频", extensions: ["mp4", "mov", "mkv", "avi", "webm"] }],
    });
    if (typeof path === "string") {
      setInput(path);
      try {
        const m = await probeMedia(path);
        setInfo(m);
        setLog(`已加载: ${m.width}×${m.height} · ${m.duration.toFixed(1)}s`);
      } catch (e) {
        setLog(`加载失败: ${e}`);
      }
    }
  }

  async function pickOutput() {
    const path = await open({ directory: true, multiple: false });
    if (typeof path === "string") setOutputDir(path);
  }

  async function run() {
    if (!input || !outputDir) {
      setLog("请先选输入和输出目录");
      return;
    }
    const marks = marksText
      .split(",")
      .map((s) => parseFloat(s.trim()))
      .filter((n) => !isNaN(n));
    if (marks.length < 2) {
      setLog("至少需要 2 个分点");
      return;
    }
    setBusy(true);
    setLog("处理中...");
    try {
      const r = await splitVideo(input, marks, outputDir);
      setLog(r.message || "完成");
    } catch (e) {
      setLog(`错误: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="① 分段拆解 (US-01)">
      <Field label="输入视频">
        <div className="row">
          <input value={input} readOnly placeholder="未选择" />
          <Button variant="ghost" onClick={pickInput}>选择...</Button>
        </div>
      </Field>
      {info && (
        <p className="meta">
          {info.has_video ? `${info.width}×${info.height}` : "纯音频"} · {info.duration.toFixed(1)}s · {info.video_codec ?? "无视频"}
        </p>
      )}
      <Field label="分点(秒,逗号分隔)">
        <input value={marksText} onChange={(e) => setMarksText(e.target.value)} />
      </Field>
      <Field label="输出目录">
        <div className="row">
          <input value={outputDir} readOnly placeholder="未选择" />
          <Button variant="ghost" onClick={pickOutput}>选择...</Button>
        </div>
      </Field>
      <Button onClick={run} disabled={busy}>
        {busy ? "处理中..." : "开始切片"}
      </Button>
      {log && <pre className="log">{log}</pre>}
    </Card>
  );
}
