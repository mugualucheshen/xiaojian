// 混合剪辑面板
import { useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { mixVideo } from "../api/bridge";
import { Button, Card, Field } from "./Ui";

export function MixPanel() {
  const [video, setVideo] = useState<string>("");
  const [bgm, setBgm] = useState<string>("");
  const [output, setOutput] = useState<string>("");
  const [mainVol, setMainVol] = useState<number>(1.0);
  const [bgmVol, setBgmVol] = useState<number>(0.3);
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string>("");

  async function pickVideo() {
    const p = await open({
      multiple: false,
      filters: [{ name: "视频", extensions: ["mp4", "mov", "mkv"] }],
    });
    if (typeof p === "string") setVideo(p);
  }
  async function pickBgm() {
    const p = await open({
      multiple: false,
      filters: [{ name: "音频", extensions: ["mp3", "aac", "wav", "flac", "m4a"] }],
    });
    if (typeof p === "string") setBgm(p);
  }
  async function pickOutput() {
    const p = await save({
      defaultPath: "mixed.mp4",
      filters: [{ name: "MP4", extensions: ["mp4"] }],
    });
    if (typeof p === "string") setOutput(p);
  }

  async function run() {
    if (!video || !bgm || !output) {
      setLog("请先选视频、BGM、输出");
      return;
    }
    setBusy(true);
    setLog("处理中...");
    try {
      const r = await mixVideo(video, bgm, output, mainVol, bgmVol);
      setLog(r.message || "完成");
    } catch (e) {
      setLog(`错误: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="③ 混合剪辑 (US-03)">
      <Field label="视频">
        <div className="row">
          <input value={video} readOnly />
          <Button variant="ghost" onClick={pickVideo}>选择...</Button>
        </div>
      </Field>
      <Field label="背景音乐">
        <div className="row">
          <input value={bgm} readOnly />
          <Button variant="ghost" onClick={pickBgm}>选择...</Button>
        </div>
      </Field>
      <Field label="输出">
        <div className="row">
          <input value={output} readOnly />
          <Button variant="ghost" onClick={pickOutput}>选择...</Button>
        </div>
      </Field>
      <div className="row">
        <Field label="原声音量 (0-2)">
          <input
            type="number" step="0.1" min="0" max="2"
            value={mainVol}
            onChange={(e) => setMainVol(parseFloat(e.target.value))}
          />
        </Field>
        <Field label="BGM 音量 (0-2)">
          <input
            type="number" step="0.1" min="0" max="2"
            value={bgmVol}
            onChange={(e) => setBgmVol(parseFloat(e.target.value))}
          />
        </Field>
      </div>
      <Button onClick={run} disabled={busy}>
        {busy ? "合成中..." : "开始混合"}
      </Button>
      {log && <pre className="log">{log}</pre>}
    </Card>
  );
}
