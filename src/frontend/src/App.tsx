// 小剪 (XiaoJian) 主入口
import { useState } from "react";
import { SplitPanel } from "./components/SplitPanel";
import { ExtractPanel } from "./components/ExtractPanel";
import { MixPanel } from "./components/MixPanel";
import "./App.css";

type Tab = "split" | "extract" | "mix";

export default function App() {
  const [tab, setTab] = useState<Tab>("split");
  return (
    <div className="app">
      <header className="header">
        <h1>🎬 小剪 XiaoJian</h1>
        <p className="tagline">把视频拆开,再随意拼回去</p>
      </header>
      <nav className="tabs">
        <button
          className={tab === "split" ? "active" : ""}
          onClick={() => setTab("split")}
        >分段</button>
        <button
          className={tab === "extract" ? "active" : ""}
          onClick={() => setTab("extract")}
        >音频</button>
        <button
          className={tab === "mix" ? "active" : ""}
          onClick={() => setTab("mix")}
        >混合</button>
      </nav>
      <main>
        {tab === "split" && <SplitPanel />}
        {tab === "extract" && <ExtractPanel />}
        {tab === "mix" && <MixPanel />}
      </main>
      <footer className="footer">
        v0.1.0 · MIT · 仅供学习与合法用途使用
      </footer>
    </div>
  );
}
