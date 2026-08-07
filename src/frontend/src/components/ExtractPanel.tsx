// 音频提取面板
import { useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { extractAudio } from "../api/bridge";
import { Button, Card, Field } from "./Ui";

export function ExtractPanel() {
  const [input, setInput] = useState<string>("");
  const [output, setOutput] = useState<string>("");
  const [format, setFormat] = useState<"mp3" | "aac" | "wav" | "flac">("mp3");
  const [bitrate, setBitrate] = useState<string>("192k");
  const [busy, setBusy] = useState(false);
  const [log, setLog] = useState<string>("");

  async function pickInput() {
    const p = await open({
      multiple: false,
      filters: [{ name: "视频", extensions: ["mp4", "mov", "mkv", "avi"] }],
    });
    if (typeof p === "string") setInput(p);
  }

  async function pickOutput() {
    const p = await save({
      defaultPath: `audio.${format}`,
      filters: [{ name: format.toUpperCase(), extensions: [format] }],
    });
    if (typeof p === "string") setOutput(p);
  }

  async function run() {
    if (!input || !output) {
      setLog("请先选输入和输出");
      return;
    }
    setBusy(true);
    setLog("处理中...");
    try {
      const r = await extractAudio(input, output, format, bitrate);
      setLog(r.message || "完成");
    } catch (e) {
      setLog(`错误: ${e}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card title="② 音频提取 (US-02)">
      <Field label="输入视频">
        <div className="row">
          <input value={input} readOnly placeholder="未选择" />
          <Button variant="ghost" onClick={pickInput}>选择...</Button>
        </div>
      </Field>
      <Field label="输出文件">
        <div className="row">
          <input value={output} readOnly placeholder="未选择" />
          <Button variant="ghost" onClick={pickOutput}>选择...</Button>
        </div>
      </Field>
      <div className="row">
        <Field label="格式">
          <select value={format} onChange={(e) => setFormat(e.target.value as "mp3" | "aac" | "wav" | "flac")}>
            <option value="mp3">MP3</option>
            <option value="aac">AAC</option>
            <option value="wav">WAV</option>
            <option value="flac">FLAC</option>
          </select>
        </Field>
        <Field label="码率">
          <input value={bitrate} onChange={(e) => setBitrate(e.target.value)} />
        </Field>
      </div>
      <Button onClick={run} disabled={busy}>
        {busy ? "提取中..." : "提取音频"}
      </Button>
      {log && <pre className="log">{log}</pre>}
    </Card>
  );
}
