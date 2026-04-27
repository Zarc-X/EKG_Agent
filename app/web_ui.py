from __future__ import annotations


def render_home_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>EKG Agent Refactor</title>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono:wght@400;600&display=swap');

    :root {
      --bg-top: #edf4f1;
      --bg-bottom: #dce8e2;
      --ink: #17271f;
      --muted: #51695c;
      --surface: rgba(255, 255, 255, 0.86);
      --surface-strong: #ffffff;
      --line: rgba(23, 39, 31, 0.14);
      --primary: #0f7a5a;
      --primary-dark: #09513c;
      --ok: #1a8455;
      --warn: #a24a2e;
      --error: #bb2d46;
      --loading: #9a5a1a;
      --shadow-1: 0 10px 30px rgba(23, 39, 31, 0.12);
      --shadow-2: 0 16px 48px rgba(23, 39, 31, 0.16);
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100svh;
      font-family: "Space Grotesk", "Noto Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif;
      color: var(--ink);
      background:
        radial-gradient(48rem 28rem at 12% 0%, rgba(255, 255, 255, 0.9), transparent 62%),
        radial-gradient(38rem 22rem at 88% 10%, rgba(167, 219, 195, 0.62), transparent 58%),
        linear-gradient(165deg, var(--bg-top), var(--bg-bottom));
      padding: 18px;
    }

    body::before {
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      background-image:
        linear-gradient(rgba(23, 39, 31, 0.028) 1px, transparent 1px),
        linear-gradient(90deg, rgba(23, 39, 31, 0.028) 1px, transparent 1px);
      background-size: 42px 42px;
      mask-image: radial-gradient(circle at center, #000 35%, transparent 100%);
      z-index: -1;
    }

    .app {
      max-width: 1240px;
      margin: 0 auto;
      display: grid;
      gap: 16px;
      animation: fade-up 460ms ease-out;
    }

    .hero {
      border-radius: 20px;
      border: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(255, 255, 255, 0.9), rgba(239, 250, 245, 0.86));
      box-shadow: var(--shadow-1);
      padding: 18px 20px;
      display: grid;
      grid-template-columns: 1.5fr 1fr;
      gap: 16px;
      position: relative;
      overflow: hidden;
    }

    .hero::after {
      content: "";
      position: absolute;
      width: 290px;
      height: 290px;
      border-radius: 50%;
      right: -120px;
      top: -170px;
      background: radial-gradient(circle, rgba(15, 122, 90, 0.2), rgba(15, 122, 90, 0));
      pointer-events: none;
    }

    .hero-title {
      margin: 0;
      font-size: 32px;
      line-height: 1.12;
      letter-spacing: 0.16px;
      font-weight: 700;
    }

    .hero-sub {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 14px;
      max-width: 78ch;
      line-height: 1.55;
    }

    .hero-flow {
      margin-top: 12px;
      display: inline-flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .flow-chip {
      border-radius: 999px;
      border: 1px solid rgba(15, 122, 90, 0.25);
      background: #f4fbf8;
      color: #134935;
      padding: 6px 10px;
      font-size: 12px;
      font-weight: 600;
    }

    .hero-right {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      justify-content: center;
      gap: 10px;
    }

    .status-pill {
      border-radius: 999px;
      border: 1px solid rgba(23, 39, 31, 0.18);
      background: #f8fbfa;
      color: #2a4137;
      padding: 7px 12px;
      font-size: 12px;
      font-weight: 700;
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }

    .status-pill.ok {
      border-color: rgba(26, 132, 85, 0.3);
      background: #eaf8f1;
      color: var(--ok);
    }

    .status-pill.warn {
      border-color: rgba(162, 74, 46, 0.3);
      background: #fff3ef;
      color: var(--warn);
    }

    .status-pill.error {
      border-color: rgba(187, 45, 70, 0.3);
      background: #fff2f5;
      color: var(--error);
    }

    .status-pill.loading {
      border-color: rgba(154, 90, 26, 0.3);
      background: #fff7ed;
      color: var(--loading);
    }

    .hero-meta {
      font-size: 13px;
      color: var(--muted);
      display: grid;
      gap: 6px;
    }

    .hero-meta strong { color: var(--ink); }

    .workspace {
      display: grid;
      grid-template-columns: 0.9fr 1.42fr 1fr;
      gap: 16px;
      align-items: start;
    }

    .version-tree {
      min-height: calc(100svh - 186px);
      display: grid;
      grid-template-rows: auto auto 1fr auto;
      gap: 10px;
      padding: 15px 14px;
      animation: card-up 420ms ease-out 40ms both;
    }

    .version-tree h3 {
      margin: 0;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }

    .tree-controls {
      display: grid;
      gap: 8px;
    }

    .branch-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
    }

    .branch-row.dual {
      grid-template-columns: 1fr auto auto;
    }

    .input-like {
      width: 100%;
      border-radius: 9px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
      font-size: 12px;
      padding: 8px 9px;
      outline: none;
      font-family: inherit;
    }

    .input-like:focus {
      border-color: #2f8f72;
      box-shadow: 0 0 0 3px rgba(47, 143, 114, 0.16);
    }

    .mini-btn {
      border: 1px solid rgba(15, 122, 90, 0.26);
      border-radius: 9px;
      background: #f4fbf8;
      color: #164637;
      font-family: inherit;
      font-size: 12px;
      font-weight: 700;
      padding: 0 10px;
      min-height: 34px;
      cursor: pointer;
      transition: transform 0.14s ease, filter 0.14s ease;
    }

    .mini-btn:hover { filter: brightness(1.03); }
    .mini-btn:active { transform: translateY(1px); }

    .tree-list {
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.76);
      padding: 8px;
      overflow: auto;
      max-height: calc(100svh - 350px);
      display: grid;
      align-content: start;
      gap: 6px;
    }

    .tree-empty {
      padding: 10px;
      border: 1px dashed var(--line);
      border-radius: 9px;
      color: var(--muted);
      font-size: 12px;
      background: rgba(255, 255, 255, 0.7);
    }

    .tree-item {
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fbfefd;
      padding: 8px;
      display: grid;
      gap: 6px;
      position: relative;
    }

    .tree-item.head {
      border-color: rgba(26, 132, 85, 0.34);
      box-shadow: inset 0 0 0 1px rgba(26, 132, 85, 0.16);
      background: #f2fbf6;
    }

    .tree-item::before {
      content: "";
      position: absolute;
      left: -1px;
      top: -1px;
      bottom: -1px;
      width: 3px;
      border-radius: 10px 0 0 10px;
      background: transparent;
    }

    .tree-item.head::before {
      background: linear-gradient(180deg, rgba(26, 132, 85, 0.82), rgba(26, 132, 85, 0.22));
    }

    .tree-top {
      display: flex;
      gap: 6px;
      align-items: center;
      justify-content: space-between;
    }

    .tree-label {
      font-size: 12px;
      font-weight: 600;
      color: var(--ink);
      max-width: 100%;
      word-break: break-word;
      line-height: 1.35;
    }

    .tree-tags {
      display: inline-flex;
      gap: 6px;
      align-items: center;
      flex-wrap: wrap;
    }

    .tree-tag {
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f8fbfa;
      color: #335145;
      padding: 1px 8px;
      font-size: 11px;
      font-weight: 600;
    }

    .tree-tag.head {
      border-color: rgba(26, 132, 85, 0.34);
      background: #eaf8f1;
      color: var(--ok);
    }

    .tree-meta {
      font-size: 11px;
      color: var(--muted);
      line-height: 1.4;
      word-break: break-word;
    }

    .tree-actions {
      display: flex;
      justify-content: flex-end;
    }

    .tree-rollback-btn {
      border: 1px solid rgba(162, 74, 46, 0.28);
      border-radius: 8px;
      background: #fff5f1;
      color: #87402a;
      font-family: inherit;
      font-size: 11px;
      font-weight: 700;
      min-height: 30px;
      padding: 0 8px;
      cursor: pointer;
    }

    .tree-rollback-btn:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }

    .card {
      border-radius: 18px;
      border: 1px solid var(--line);
      background: var(--surface);
      box-shadow: var(--shadow-1);
      backdrop-filter: blur(7px);
    }

    .chat-card {
      min-height: calc(100svh - 186px);
      display: flex;
      flex-direction: column;
      animation: card-up 420ms ease-out 70ms both;
    }

    .chat-head {
      padding: 16px 18px;
      border-bottom: 1px solid var(--line);
      display: grid;
      gap: 10px;
    }

    .chat-title {
      margin: 0;
      font-size: 20px;
      font-weight: 700;
    }

    .chat-sub {
      margin: 0;
      color: var(--muted);
      font-size: 13px;
    }

    .examples {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }

    .example-btn {
      border-radius: 999px;
      border: 1px solid rgba(15, 122, 90, 0.24);
      background: #f6fbf9;
      color: #164a38;
      font-family: inherit;
      font-size: 12px;
      font-weight: 600;
      padding: 5px 10px;
      cursor: pointer;
      transition: transform 140ms ease, background 140ms ease;
    }

    .example-btn:hover {
      background: #ebf8f2;
      transform: translateY(-1px);
    }

    .chat-log {
      flex: 1;
      overflow: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.38), rgba(247, 251, 249, 0.62));
    }

    .msg {
      max-width: 90%;
      display: flex;
      flex-direction: column;
      gap: 5px;
      animation: msg-in 220ms ease-out;
    }

    .msg.user {
      margin-left: auto;
      align-items: flex-end;
    }

    .msg.assistant {
      margin-right: auto;
      align-items: flex-start;
    }

    .msg-body {
      border-radius: 12px;
      border: 1px solid var(--line);
      padding: 11px 13px;
      background: var(--surface-strong);
      color: var(--ink);
      white-space: pre-wrap;
      line-height: 1.56;
      font-size: 14px;
      letter-spacing: 0.1px;
    }

    .msg.user .msg-body {
      background: linear-gradient(145deg, var(--primary), #188765);
      color: #fff;
      border: none;
    }

    .msg-meta {
      font-size: 11px;
      color: var(--muted);
    }

    .composer {
      padding: 14px;
      border-top: 1px solid var(--line);
      display: grid;
      gap: 10px;
    }

    textarea {
      width: 100%;
      min-height: 92px;
      resize: vertical;
      border-radius: 12px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.9);
      color: var(--ink);
      font-size: 14px;
      line-height: 1.52;
      font-family: inherit;
      padding: 12px 13px;
      outline: none;
    }

    textarea:focus {
      border-color: #2f8f72;
      box-shadow: 0 0 0 3px rgba(47, 143, 114, 0.16);
    }

    .composer-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
    }

    .composer-left {
      display: flex;
      align-items: center;
      gap: 12px;
      flex-wrap: wrap;
    }

    .toggle {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      font-size: 12px;
      color: var(--muted);
      user-select: none;
    }

    .toggle input { accent-color: var(--primary); }

    .composer-hint {
      font-size: 12px;
      color: var(--muted);
    }

    .send {
      border: none;
      border-radius: 10px;
      height: 42px;
      padding: 0 16px;
      font-family: inherit;
      font-weight: 700;
      color: #fff;
      background: linear-gradient(160deg, var(--primary), var(--primary-dark));
      cursor: pointer;
      transition: filter 0.15s ease, transform 0.15s ease;
    }

    .send:hover { filter: brightness(1.05); }
    .send:active { transform: translateY(1px); }
    .send:disabled { opacity: 0.68; cursor: not-allowed; }

    .side {
      min-height: calc(100svh - 186px);
      display: grid;
      grid-template-rows: auto auto auto auto auto;
      gap: 14px;
      animation: card-up 420ms ease-out 120ms both;
    }

    .panel { padding: 15px 16px; }

    .panel h3 {
      margin: 0 0 10px;
      font-size: 15px;
      font-weight: 700;
      letter-spacing: 0.2px;
    }

    .kv {
      display: grid;
      grid-template-columns: 120px 1fr;
      gap: 8px;
      font-size: 13px;
      line-height: 1.48;
    }

    .k { color: var(--muted); }
    .v { color: var(--ink); word-break: break-word; }

    .summary-grid {
      margin-top: 10px;
      display: grid;
      gap: 10px;
      grid-template-columns: 1fr 1fr;
    }

    .summary-cell {
      border-radius: 10px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.74);
      padding: 9px;
    }

    .summary-cell-label {
      font-size: 11px;
      color: var(--muted);
      margin-bottom: 4px;
    }

    .summary-cell-value {
      font-size: 13px;
      font-weight: 600;
      color: var(--ink);
      word-break: break-word;
    }

    .panel-tip {
      margin-top: 8px;
      font-size: 12px;
      color: var(--muted);
    }

    .evidence-list {
      display: flex;
      flex-direction: column;
      gap: 9px;
      max-height: 252px;
      overflow: auto;
    }

    .evidence-item {
      padding: 10px;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fcfffd;
    }

    .evidence-title {
      margin: 0;
      font-size: 13px;
      font-weight: 600;
    }

    .evidence-meta {
      margin-top: 4px;
      font-size: 12px;
      color: var(--muted);
      line-height: 1.45;
      word-break: break-word;
    }

    .divider {
      width: 100%;
      height: 1px;
      background: var(--line);
      margin: 10px 0;
    }

    .mono {
      margin: 0;
      font-family: "JetBrains Mono", Consolas, "SFMono-Regular", Menlo, Monaco, monospace;
      font-size: 12px;
      line-height: 1.45;
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #f7fbf9;
      color: #1f3229;
      padding: 10px;
      overflow: auto;
      max-height: 172px;
      white-space: pre-wrap;
      word-break: break-word;
    }

    .approval-toolbar {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 8px;
      margin-bottom: 9px;
    }

    .approval-list {
      display: grid;
      gap: 7px;
      max-height: 190px;
      overflow: auto;
      margin-bottom: 10px;
    }

    .approval-item {
      width: 100%;
      text-align: left;
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fcfffd;
      padding: 9px;
      cursor: pointer;
      display: grid;
      gap: 5px;
      transition: transform 0.14s ease, border-color 0.14s ease, background 0.14s ease;
    }

    .approval-item:hover {
      transform: translateY(-1px);
      border-color: rgba(15, 122, 90, 0.32);
      background: #f7fcfa;
    }

    .approval-item.active {
      border-color: rgba(15, 122, 90, 0.4);
      box-shadow: inset 0 0 0 1px rgba(15, 122, 90, 0.2);
      background: #eefaf4;
    }

    .approval-item-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }

    .approval-item-title {
      margin: 0;
      font-size: 12px;
      font-weight: 700;
      color: var(--ink);
      line-height: 1.45;
      word-break: break-word;
    }

    .approval-item-meta {
      font-size: 11px;
      color: var(--muted);
      line-height: 1.4;
      word-break: break-word;
    }

    .ticket-badge {
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f8fbfa;
      color: #355347;
      padding: 1px 7px;
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }

    .ticket-badge.pending { background: #fff4ef; color: #955437; border-color: rgba(162, 74, 46, 0.32); }
    .ticket-badge.approved { background: #ebf8f1; color: #1a8455; border-color: rgba(26, 132, 85, 0.32); }
    .ticket-badge.rejected { background: #fff2f5; color: #bb2d46; border-color: rgba(187, 45, 70, 0.32); }
    .ticket-badge.executed { background: #e8f6ef; color: #18774d; border-color: rgba(24, 119, 77, 0.32); }
    .ticket-badge.failed { background: #fff0f0; color: #b83333; border-color: rgba(184, 51, 51, 0.32); }

    .approval-detail,
    .copilot-card {
      border-radius: 10px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.78);
      padding: 9px;
      display: grid;
      gap: 7px;
    }

    .approval-detail-grid {
      display: grid;
      grid-template-columns: 96px 1fr;
      gap: 6px;
      font-size: 12px;
      line-height: 1.4;
    }

    .approval-detail-label { color: var(--muted); }
    .approval-detail-value { color: var(--ink); word-break: break-word; }

    .copilot-head {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }

    .copilot-chip {
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f7fbfa;
      color: #315145;
      font-size: 11px;
      font-weight: 700;
      padding: 2px 8px;
    }

    .copilot-list {
      margin: 0;
      padding-left: 16px;
      display: grid;
      gap: 4px;
      font-size: 12px;
      color: var(--ink);
      line-height: 1.4;
    }

    .copilot-policy-row {
      border-radius: 8px;
      border: 1px solid var(--line);
      background: #f8fbfa;
      padding: 6px;
      font-size: 11px;
      color: #2f4d40;
      line-height: 1.45;
      word-break: break-word;
    }

    .approval-decision {
      margin-top: 10px;
      display: grid;
      gap: 7px;
    }

    .approval-reason {
      min-height: 68px;
      font-size: 12px;
      padding: 9px;
      border-radius: 10px;
    }

    .decision-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
    }

    .decision-btn {
      min-height: 34px;
      border-radius: 9px;
      border: 1px solid transparent;
      font-family: inherit;
      font-size: 12px;
      font-weight: 700;
      cursor: pointer;
      transition: transform 0.14s ease, filter 0.14s ease;
    }

    .decision-btn:active { transform: translateY(1px); }
    .decision-btn:disabled { opacity: 0.52; cursor: not-allowed; }

    .decision-btn.approve {
      background: #eaf8f1;
      color: #166a47;
      border-color: rgba(26, 132, 85, 0.34);
    }

    .decision-btn.reject {
      background: #fff2f5;
      color: #9a2f48;
      border-color: rgba(187, 45, 70, 0.34);
    }

    .change-explain-toolbar {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 9px;
    }

    .change-explain-list {
      display: grid;
      gap: 8px;
      max-height: 260px;
      overflow: auto;
    }

    .change-explain-item {
      border-radius: 10px;
      border: 1px solid var(--line);
      background: #fcfffd;
      padding: 9px;
      display: grid;
      gap: 6px;
    }

    .change-explain-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 8px;
    }

    .change-explain-title {
      margin: 0;
      font-size: 12px;
      font-weight: 700;
      color: var(--ink);
      line-height: 1.4;
      word-break: break-word;
    }

    .risk-badge {
      border-radius: 999px;
      border: 1px solid var(--line);
      background: #f8fbfa;
      color: #355347;
      padding: 1px 8px;
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }

    .risk-badge.low { background: #ebf8f1; color: #1a8455; border-color: rgba(26, 132, 85, 0.32); }
    .risk-badge.medium { background: #fff7ed; color: #9a5a1a; border-color: rgba(154, 90, 26, 0.32); }
    .risk-badge.high { background: #fff2f5; color: #a53a4f; border-color: rgba(165, 58, 79, 0.34); }
    .risk-badge.critical { background: #ffecee; color: #b83333; border-color: rgba(184, 51, 51, 0.35); }
    .risk-badge.unknown { background: #f3f6f5; color: #50695d; border-color: rgba(80, 105, 93, 0.28); }

    .change-explain-meta {
      font-size: 11px;
      color: var(--muted);
      line-height: 1.45;
      word-break: break-word;
    }

    @keyframes fade-up {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @keyframes card-up {
      from { opacity: 0; transform: translateY(12px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @keyframes msg-in {
      from { opacity: 0; transform: translateY(6px); }
      to { opacity: 1; transform: translateY(0); }
    }

    @media (max-width: 980px) {
      body { padding: 12px; }
      .hero { grid-template-columns: 1fr; gap: 12px; }
      .workspace { grid-template-columns: 1fr; }
      .version-tree, .chat-card, .side { min-height: auto; }
      .hero-title { font-size: 27px; }
      .summary-grid { grid-template-columns: 1fr; }
      .tree-list { max-height: 320px; }
    }

    @media (max-width: 640px) {
      .hero-title { font-size: 24px; }
      .msg { max-width: 96%; }
      .chat-log { padding: 12px; }
      .composer { padding: 11px; }
      .composer-row { flex-wrap: wrap; }
      .send { width: 100%; }
      .kv { grid-template-columns: 96px 1fr; }
      .branch-row,
      .branch-row.dual { grid-template-columns: 1fr; }
      .mini-btn { width: 100%; }
      .approval-toolbar { grid-template-columns: 1fr; }
      .decision-row { grid-template-columns: 1fr; }
      .approval-detail-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <main class="app">
    <header class="hero">
      <div>
        <h1 class="hero-title">EKG Agent Refactor 业务控制台</h1>
        <p class="hero-sub">强化可读性、可审计性与实时反馈。自然语言请求会经过图谱检索、SQL 生成、安全防护与执行摘要，最终在同一页面完整呈现。</p>
        <div class="hero-flow">
          <span class="flow-chip">入口检查</span>
          <span class="flow-chip">图谱检索</span>
          <span class="flow-chip">SQL 生成</span>
          <span class="flow-chip">三层安全</span>
          <span class="flow-chip">执行与审计</span>
        </div>
      </div>
      <div class="hero-right">
        <span id="topStatus" class="status-pill">等待请求</span>
        <div class="hero-meta">
          <div>API 前缀: <strong>/v1</strong></div>
          <div>健康检查: <strong>/health</strong> · 文档: <strong>/docs</strong></div>
          <div>会话: <strong id="sessionMeta">web-user / web-thread</strong></div>
        </div>
      </div>
    </header>

    <div class="workspace">
      <aside class="card version-tree">
        <h3>版本树与分支</h3>
        <div class="tree-controls">
          <div class="branch-row">
            <input id="branchInput" class="input-like" type="text" placeholder="新分支名，例如 feature-ui" />
            <button id="createBranchBtn" class="mini-btn">创建分支</button>
          </div>
          <div class="branch-row dual">
            <select id="branchSelect" class="input-like"></select>
            <button id="checkoutBranchBtn" class="mini-btn">切换</button>
            <button id="refreshTreeBtn" class="mini-btn">刷新</button>
          </div>
        </div>
        <div id="versionTree" class="tree-list">
          <div class="tree-empty">暂无版本记录。执行写操作后会自动生成版本节点。</div>
        </div>
        <div class="panel-tip">记录每次写操作的修改摘要（影响行、触表、trace），不展示整表预览；点击节点可回滚。</div>
      </aside>

      <section class="card chat-card">
        <header class="chat-head">
          <h2 class="chat-title">实时对话区</h2>
          <p class="chat-sub">支持拼写容错、图谱增强问答与审批流程。可以直接点击示例填充输入框。</p>
          <div class="examples">
            <button class="example-btn" data-example="查询型号 STM32F103C8T6 的库存">库存查询</button>
            <button class="example-btn" data-example="GRM1555C1HR40BA01D的厂商">厂商查询</button>
            <button class="example-btn" data-example="厂商为YAGEO(国巨)的所有电子元件">厂商筛选</button>
            <button class="example-btn" data-example="查询采购单号 C167969 对应物料编码和库存">采购单联查</button>
          </div>
        </header>

        <div id="chatLog" class="chat-log">
          <div class="msg assistant">
            <div class="msg-body">服务已就绪。可以直接提问，例如：查询型号 STM32F103C8T6 的库存。</div>
            <div class="msg-meta">系统</div>
          </div>
        </div>

        <footer class="composer">
          <textarea id="input" placeholder="输入电子元件管理需求，例如：厂商为 cjiagn(长江微电) 的所有电子元件"></textarea>
          <div class="composer-row">
            <div class="composer-left">
              <label class="toggle"><input id="autoApprove" type="checkbox" /> 自动审批写操作</label>
              <span class="composer-hint">快捷键: Ctrl/Command + Enter 发送</span>
            </div>
            <button id="sendBtn" class="send">发送请求</button>
          </div>
        </footer>
      </section>

      <aside class="side">
        <section class="card panel">
          <h3>执行状态</h3>
          <div class="kv">
            <div class="k">当前状态</div><div class="v"><span id="statusPill" class="status-pill">等待请求</span></div>
            <div class="k">Trace ID</div><div id="traceId" class="v">-</div>
            <div class="k">审批单</div><div id="approvalId" class="v">-</div>
            <div class="k">返回行数</div><div id="rowsCount" class="v">-</div>
          </div>

          <div class="summary-grid">
            <div class="summary-cell">
              <div class="summary-cell-label">决策结果</div>
              <div id="decisionText" class="summary-cell-value">-</div>
            </div>
            <div class="summary-cell">
              <div class="summary-cell-label">风险等级</div>
              <div id="riskText" class="summary-cell-value">-</div>
            </div>
          </div>
          <div class="panel-tip">写操作被拦截或需人工确认时，将在这里显示状态变化。</div>
        </section>

        <section class="card panel">
          <h3>人工审批台</h3>
          <div class="approval-toolbar">
            <select id="approvalFilter" class="input-like">
              <option value="all">全部审批单</option>
              <option value="pending" selected>待审批</option>
              <option value="approved">已批准</option>
              <option value="rejected">已拒绝</option>
              <option value="executed">已执行</option>
              <option value="failed">执行失败</option>
            </select>
            <button id="refreshApprovalsBtn" class="mini-btn">刷新</button>
          </div>

          <div id="approvalsList" class="approval-list">
            <div class="tree-empty">暂无审批单。</div>
          </div>

          <div class="approval-detail" id="approvalDetailCard">
            <div class="summary-cell-label">审批单详情</div>
            <div class="approval-detail-grid">
              <div class="approval-detail-label">审批单 ID</div><div id="approvalDetailId" class="approval-detail-value">-</div>
              <div class="approval-detail-label">状态</div><div id="approvalDetailStatus" class="approval-detail-value">-</div>
              <div class="approval-detail-label">申请人</div><div id="approvalDetailRequester" class="approval-detail-value">-</div>
              <div class="approval-detail-label">摘要</div><div id="approvalDetailSummary" class="approval-detail-value">-</div>
              <div class="approval-detail-label">Trace</div><div id="approvalDetailTrace" class="approval-detail-value">-</div>
              <div class="approval-detail-label">创建时间</div><div id="approvalDetailCreated" class="approval-detail-value">-</div>
            </div>
          </div>

          <div class="copilot-card" id="approvalCopilotCard">
            <div class="summary-cell-label">副驾驶摘要</div>
            <div class="approval-item-meta">请选择审批单查看风险点、策略映射与建议动作。</div>
          </div>

          <div class="approval-decision">
            <input id="approvalApproverInput" class="input-like" type="text" placeholder="审批人，例如 security.lead" value="web-approver" />
            <textarea id="approvalReasonInput" class="approval-reason" placeholder="审批理由（可选）"></textarea>
            <div class="decision-row">
              <button id="approveTicketBtn" class="decision-btn approve" disabled>通过并执行</button>
              <button id="rejectTicketBtn" class="decision-btn reject" disabled>拒绝</button>
            </div>
          </div>
        </section>

        <section class="card panel">
          <h3>变更解释器</h3>
          <div class="change-explain-toolbar">
            <button id="refreshChangeExplainBtn" class="mini-btn">刷新解释</button>
          </div>
          <div id="changeExplainList" class="change-explain-list">
            <div class="tree-empty">暂无变更解释。执行写操作后会自动生成管理摘要。</div>
          </div>
        </section>

        <section class="card panel">
          <h3>图谱证据</h3>
          <div id="evidenceList" class="evidence-list">
            <div class="evidence-item">
              <p class="evidence-title">暂无证据</p>
              <div class="evidence-meta">发送请求后展示 Graph RAG 命中节点和关系摘要。</div>
            </div>
          </div>
        </section>

        <section class="card panel">
          <h3>调试与审计摘要</h3>
          <div class="summary-cell-label">SQL</div>
          <pre id="sqlView" class="mono">尚无执行结果</pre>
          <div class="divider"></div>
          <div class="summary-cell-label">安全摘要</div>
          <pre id="securityView" class="mono">尚无执行结果</pre>
          <div class="divider"></div>
          <div class="summary-cell-label">审批副驾驶建议</div>
          <pre id="approvalCopilotView" class="mono">尚无审批建议</pre>
          <div class="divider"></div>
          <div class="summary-cell-label">Python 执行草案</div>
          <pre id="pyView" class="mono">尚无执行结果</pre>
        </section>
      </aside>
    </div>
  </main>

  <script>
    const chatLog = document.getElementById('chatLog');
    const input = document.getElementById('input');
    const sendBtn = document.getElementById('sendBtn');
    const autoApprove = document.getElementById('autoApprove');
    const topStatus = document.getElementById('topStatus');
    const statusPill = document.getElementById('statusPill');

    const traceId = document.getElementById('traceId');
    const approvalId = document.getElementById('approvalId');
    const rowsCount = document.getElementById('rowsCount');
    const decisionText = document.getElementById('decisionText');
    const riskText = document.getElementById('riskText');

    const evidenceList = document.getElementById('evidenceList');
    const sqlView = document.getElementById('sqlView');
    const securityView = document.getElementById('securityView');
    const approvalCopilotView = document.getElementById('approvalCopilotView');
    const pyView = document.getElementById('pyView');
    const branchInput = document.getElementById('branchInput');
    const branchSelect = document.getElementById('branchSelect');
    const createBranchBtn = document.getElementById('createBranchBtn');
    const checkoutBranchBtn = document.getElementById('checkoutBranchBtn');
    const refreshTreeBtn = document.getElementById('refreshTreeBtn');
    const versionTree = document.getElementById('versionTree');
    const approvalFilter = document.getElementById('approvalFilter');
    const refreshApprovalsBtn = document.getElementById('refreshApprovalsBtn');
    const approvalsList = document.getElementById('approvalsList');
    const approvalDetailId = document.getElementById('approvalDetailId');
    const approvalDetailStatus = document.getElementById('approvalDetailStatus');
    const approvalDetailRequester = document.getElementById('approvalDetailRequester');
    const approvalDetailSummary = document.getElementById('approvalDetailSummary');
    const approvalDetailTrace = document.getElementById('approvalDetailTrace');
    const approvalDetailCreated = document.getElementById('approvalDetailCreated');
    const approvalApproverInput = document.getElementById('approvalApproverInput');
    const approvalReasonInput = document.getElementById('approvalReasonInput');
    const approveTicketBtn = document.getElementById('approveTicketBtn');
    const rejectTicketBtn = document.getElementById('rejectTicketBtn');
    const approvalCopilotCard = document.getElementById('approvalCopilotCard');
    const refreshChangeExplainBtn = document.getElementById('refreshChangeExplainBtn');
    const changeExplainList = document.getElementById('changeExplainList');

    const session = {
      userId: 'web-user',
      threadId: 'web-thread',
      branch: 'main',
    };

    const approvalState = {
      selectedTicketId: null,
      tickets: [],
      currentDetail: null,
    };

    const statusMap = {
      waiting: { label: '等待请求', cls: '' },
      working: { label: '处理中', cls: 'loading' },
      completed: { label: '执行完成', cls: 'ok' },
      pending_approval: { label: '等待审批', cls: 'warn' },
      blocked: { label: '已阻断', cls: 'warn' },
      error: { label: '执行错误', cls: 'error' },
    };

    function updateSessionMeta() {
      document.getElementById('sessionMeta').textContent = `${session.userId} / ${session.threadId} @ ${session.branch}`;
    }

    updateSessionMeta();

    document.querySelectorAll('.example-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        input.value = btn.dataset.example || '';
        input.focus();
      });
    });

    function nowText() {
      return new Date().toLocaleTimeString('zh-CN', { hour12: false });
    }

    function formatDateTime(v) {
      if (!v) return '-';
      const dt = new Date(v);
      if (Number.isNaN(dt.getTime())) return String(v);
      return dt.toLocaleString('zh-CN', { hour12: false });
    }

    function shortId(v) {
      if (!v) return '-';
      const s = String(v);
      if (s.length <= 12) return s;
      return `${s.slice(0, 8)}...${s.slice(-4)}`;
    }

    function setStatus(status) {
      const key = status || 'waiting';
      const conf = statusMap[key] || { label: key, cls: '' };
      [topStatus, statusPill].forEach((el) => {
        el.className = `status-pill ${conf.cls}`.trim();
        el.textContent = conf.label;
      });
    }

    function appendMessage(role, text, meta) {
      const wrap = document.createElement('div');
      wrap.className = `msg ${role}`;

      const body = document.createElement('div');
      body.className = 'msg-body';
      body.textContent = text;
      wrap.appendChild(body);

      const info = document.createElement('div');
      info.className = 'msg-meta';
      info.textContent = `${meta || (role === 'user' ? '你' : '系统')} · ${nowText()}`;
      wrap.appendChild(info);

      chatLog.appendChild(wrap);
      chatLog.scrollTop = chatLog.scrollHeight;
    }

    function escapeHtml(s) {
      return String(s)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    async function requestJson(url, options = {}) {
      const resp = await fetch(url, options);
      let data = {};
      try {
        data = await resp.json();
      } catch {
        data = {};
      }

      if (!resp.ok) {
        const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data);
        throw new Error(`${resp.status} ${detail}`.trim());
      }
      return data;
    }

    function approvalStatusLabel(status) {
      const map = {
        pending: '待审批',
        approved: '已批准',
        rejected: '已拒绝',
        executed: '已执行',
        failed: '执行失败',
      };
      return map[status] || String(status || '-');
    }

    function approvalBadgeClass(status) {
      const s = String(status || '').toLowerCase();
      if (['pending', 'approved', 'rejected', 'executed', 'failed'].includes(s)) {
        return s;
      }
      return '';
    }

    function riskLevelLabel(level) {
      const map = {
        low: '低风险',
        medium: '中风险',
        high: '高风险',
        critical: '严重风险',
        unknown: '风险未知',
      };
      const key = String(level || 'unknown').toLowerCase();
      return map[key] || `风险:${key}`;
    }

    function riskBadgeClass(level) {
      const key = String(level || 'unknown').toLowerCase();
      if (['low', 'medium', 'high', 'critical', 'unknown'].includes(key)) {
        return key;
      }
      return 'unknown';
    }

    function renderChangeExplanations(items) {
      const rows = Array.isArray(items) ? items : [];
      if (!rows.length) {
        changeExplainList.innerHTML = '<div class="tree-empty">暂无变更解释。执行写操作后会自动生成管理摘要。</div>';
        return;
      }

      changeExplainList.innerHTML = rows.map((item) => {
        const level = String(item.risk_level || 'unknown').toLowerCase();
        const impactScope = Array.isArray(item.impact_scope) ? item.impact_scope : [];
        const checks = Array.isArray(item.checks) ? item.checks : [];
        const scopeText = impactScope.length ? impactScope.slice(0, 3).join('；') : '影响范围信息不足';
        const checksText = checks.length ? checks.slice(0, 2).join('；') : '建议人工抽样核验';
        const rollbackTarget = item.rollback_target_version_id ? shortId(item.rollback_target_version_id) : '-';

        return `
          <div class="change-explain-item">
            <div class="change-explain-top">
              <p class="change-explain-title">${escapeHtml(item.summary || item.label || '变更记录')}</p>
              <span class="risk-badge ${riskBadgeClass(level)}">${escapeHtml(riskLevelLabel(level))}</span>
            </div>
            <div class="change-explain-meta">管理摘要: ${escapeHtml(item.management_summary || '-')}</div>
            <div class="change-explain-meta">影响范围: ${escapeHtml(scopeText)}</div>
            <div class="change-explain-meta">回滚建议: ${escapeHtml(item.rollback_recommendation || '-')}</div>
            <div class="change-explain-meta">建议回滚点: ${escapeHtml(rollbackTarget)} · 检查项: ${escapeHtml(checksText)}</div>
            <div class="change-explain-meta">trace: ${escapeHtml(shortId(item.trace_id || '-'))} · 时间: ${escapeHtml(formatDateTime(item.created_at))}</div>
          </div>
        `;
      }).join('');
    }

    async function loadChangeExplanations({ silent = false } = {}) {
      const query = [
        `thread_id=${encodeURIComponent(session.threadId)}`,
        `branch=${encodeURIComponent(session.branch)}`,
        'limit=30',
      ].join('&');

      try {
        const data = await requestJson(`/v1/admin/change-explanations?${query}`);
        renderChangeExplanations(data);
      } catch (err) {
        changeExplainList.innerHTML = `<div class="tree-empty">变更解释加载失败：${escapeHtml(err)}</div>`;
        if (!silent) {
          appendMessage('assistant', `变更解释加载失败: ${err}`, '系统');
        }
      }
    }

    function renderApprovalCopilotCard(copilot) {
      if (!copilot || typeof copilot !== 'object') {
        approvalCopilotCard.innerHTML = `
          <div class="summary-cell-label">副驾驶摘要</div>
          <div class="approval-item-meta">当前审批单暂无副驾驶建议。</div>
        `;
        return;
      }

      const confidence = Number(copilot.confidence);
      const confidenceText = Number.isFinite(confidence) ? confidence.toFixed(2) : '-';
      const riskPoints = Array.isArray(copilot.risk_points) ? copilot.risk_points : [];
      const actions = Array.isArray(copilot.suggested_actions) ? copilot.suggested_actions : [];
      const policies = Array.isArray(copilot.policy_mappings) ? copilot.policy_mappings : [];

      const riskHtml = riskPoints.length
        ? `<ul class="copilot-list">${riskPoints.slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '<div class="approval-item-meta">无显著风险点。</div>';

      const actionHtml = actions.length
        ? `<ul class="copilot-list">${actions.slice(0, 5).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`
        : '<div class="approval-item-meta">暂无建议动作。</div>';

      const policyHtml = policies.length
        ? policies.slice(0, 4).map((item) => {
            const policy = escapeHtml(item.policy || '-');
            const status = escapeHtml(item.status || '-');
            const evidence = escapeHtml(item.evidence || '-');
            return `<div class="copilot-policy-row"><strong>${policy}</strong> · ${status}<br/>${evidence}</div>`;
          }).join('')
        : '<div class="approval-item-meta">暂无策略映射。</div>';

      approvalCopilotCard.innerHTML = `
        <div class="summary-cell-label">副驾驶摘要</div>
        <div class="copilot-head">
          <span class="copilot-chip">最终决策: ${escapeHtml(copilot.final_decision || '-')}</span>
          <span class="copilot-chip">建议: ${escapeHtml(copilot.recommendation || '-')}</span>
          <span class="copilot-chip">风险: ${escapeHtml(copilot.risk_level || '-')}</span>
          <span class="copilot-chip">置信度: ${escapeHtml(confidenceText)}</span>
        </div>
        ${copilot.rationale ? `<div class="approval-item-meta">判定依据: ${escapeHtml(copilot.rationale)}</div>` : ''}
        <div class="summary-cell-label">风险点</div>
        ${riskHtml}
        <div class="summary-cell-label">建议动作</div>
        ${actionHtml}
        <div class="summary-cell-label">策略映射</div>
        ${policyHtml}
      `;
    }

    function setApprovalDetail(detail) {
      approvalState.currentDetail = detail;

      if (!detail || typeof detail !== 'object' || !detail.ticket) {
        approvalDetailId.textContent = '-';
        approvalDetailStatus.textContent = '-';
        approvalDetailRequester.textContent = '-';
        approvalDetailSummary.textContent = '-';
        approvalDetailTrace.textContent = '-';
        approvalDetailCreated.textContent = '-';
        approveTicketBtn.disabled = true;
        rejectTicketBtn.disabled = true;
        renderApprovalCopilotCard(null);
        return;
      }

      const ticket = detail.ticket;
      const payload = detail.payload && typeof detail.payload === 'object' ? detail.payload : {};
      const copilot = detail.approval_copilot || payload.approval_copilot || null;
      const action = payload.action && typeof payload.action === 'object' ? payload.action : {};

      approvalDetailId.textContent = ticket.ticket_id || '-';
      approvalDetailStatus.textContent = approvalStatusLabel(ticket.status);
      approvalDetailRequester.textContent = ticket.requester || '-';
      approvalDetailSummary.textContent = ticket.summary || action.summary || '-';
      approvalDetailTrace.textContent = ticket.trace_id || '-';
      approvalDetailCreated.textContent = formatDateTime(ticket.created_at);

      const canDecide = String(ticket.status || '').toLowerCase() === 'pending';
      approveTicketBtn.disabled = !canDecide;
      rejectTicketBtn.disabled = !canDecide;
      renderApprovalCopilotCard(copilot);
    }

    async function selectApproval(ticketId, { silent = false } = {}) {
      if (!ticketId) return;

      approvalState.selectedTicketId = ticketId;
      approvalsList.querySelectorAll('.approval-item').forEach((item) => {
        item.classList.toggle('active', item.getAttribute('data-ticket-id') === ticketId);
      });

      try {
        const detail = await requestJson(`/v1/approvals/${encodeURIComponent(ticketId)}`);
        setApprovalDetail(detail);
      } catch (err) {
        setApprovalDetail(null);
        if (!silent) {
          appendMessage('assistant', `审批单详情加载失败: ${err}`, '系统');
        }
      }
    }

    function renderApprovals(tickets, { keepSelection = true } = {}) {
      const rows = Array.isArray(tickets) ? tickets : [];
      approvalState.tickets = rows;

      if (!rows.length) {
        approvalsList.innerHTML = '<div class="tree-empty">暂无审批单。</div>';
        approvalState.selectedTicketId = null;
        setApprovalDetail(null);
        return;
      }

      approvalsList.innerHTML = rows.map((ticket) => {
        const status = String(ticket.status || '').toLowerCase();
        return `
          <button class="approval-item" data-ticket-id="${escapeHtml(ticket.ticket_id || '')}">
            <div class="approval-item-top">
              <p class="approval-item-title">${escapeHtml(ticket.summary || '-')}</p>
              <span class="ticket-badge ${approvalBadgeClass(status)}">${escapeHtml(approvalStatusLabel(status))}</span>
            </div>
            <div class="approval-item-meta">ID: ${escapeHtml(shortId(ticket.ticket_id))} · 申请人: ${escapeHtml(ticket.requester || '-')}</div>
            <div class="approval-item-meta">创建时间: ${escapeHtml(formatDateTime(ticket.created_at))}</div>
          </button>
        `;
      }).join('');

      approvalsList.querySelectorAll('.approval-item').forEach((item) => {
        item.addEventListener('click', async () => {
          const ticketId = item.getAttribute('data-ticket-id');
          if (!ticketId) return;
          await selectApproval(ticketId);
        });
      });

      let targetId = keepSelection ? approvalState.selectedTicketId : null;
      if (!targetId || !rows.some((t) => t.ticket_id === targetId)) {
        const preferred = rows.find((t) => String(t.status || '').toLowerCase() === 'pending') || rows[0];
        targetId = preferred ? preferred.ticket_id : null;
      }

      if (targetId) {
        selectApproval(targetId, { silent: true });
      } else {
        setApprovalDetail(null);
      }
    }

    async function loadApprovals({ silent = false, keepSelection = true } = {}) {
      const status = String(approvalFilter.value || 'all').trim();
      const query = status && status !== 'all' ? `?status=${encodeURIComponent(status)}` : '';

      try {
        const rows = await requestJson(`/v1/approvals${query}`);
        renderApprovals(rows, { keepSelection });
      } catch (err) {
        approvalsList.innerHTML = `<div class="tree-empty">审批单加载失败：${escapeHtml(err)}</div>`;
        setApprovalDetail(null);
        if (!silent) {
          appendMessage('assistant', `审批单加载失败: ${err}`, '系统');
        }
      }
    }

    async function decideApproval(approved) {
      const ticketId = approvalState.selectedTicketId;
      if (!ticketId) {
        appendMessage('assistant', '请先选择一个审批单。', '系统');
        return;
      }

      const approver = (approvalApproverInput.value || '').trim();
      if (!approver) {
        appendMessage('assistant', '请填写审批人。', '系统');
        approvalApproverInput.focus();
        return;
      }

      const reason = (approvalReasonInput.value || '').trim();
      approveTicketBtn.disabled = true;
      rejectTicketBtn.disabled = true;

      try {
        const data = await requestJson(`/v1/approvals/${encodeURIComponent(ticketId)}/decision`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            approved,
            approver,
            reason: reason || null,
          }),
        });

        appendMessage('assistant', data.answer || (approved ? '审批通过并执行。' : '审批已拒绝。'), '审批台');
        setStatus(data.status || 'waiting');
        renderSummary(data);
        renderEvidence(data.evidence || []);
        renderDebug(data);
        await loadVersionTree({ silent: true });
        await loadChangeExplanations({ silent: true });
        await loadApprovals({ silent: true, keepSelection: true });
      } catch (err) {
        appendMessage('assistant', `审批操作失败: ${err}`, '系统');
        setStatus('error');
      } finally {
        if (approvalState.currentDetail) {
          setApprovalDetail(approvalState.currentDetail);
        } else {
          approveTicketBtn.disabled = true;
          rejectTicketBtn.disabled = true;
        }
      }
    }

    async function loadVersionTree({ silent = false } = {}) {
      try {
        const data = await requestJson(`/v1/admin/version-tree?thread_id=${encodeURIComponent(session.threadId)}&limit=200`);
        renderVersionTree(data);
      } catch (err) {
        versionTree.innerHTML = `<div class="tree-empty">版本树加载失败：${escapeHtml(err)}</div>`;
        if (!silent) {
          appendMessage('assistant', `版本树加载失败: ${err}`, '系统');
        }
      }
    }

    function renderVersionTree(payload) {
      const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
      const heads = payload.heads && typeof payload.heads === 'object' ? payload.heads : {};

      const branchSet = new Set(Object.keys(heads));
      nodes.forEach((n) => branchSet.add((n.branch || 'main').trim() || 'main'));
      if (!branchSet.size) {
        branchSet.add(session.branch || 'main');
      }

      const branchList = Array.from(branchSet).sort((a, b) => a.localeCompare(b));
      if (!branchList.includes(session.branch)) {
        session.branch = branchList[0] || 'main';
      }

      branchSelect.innerHTML = branchList
        .map((branch) => `<option value="${escapeHtml(branch)}" ${branch === session.branch ? 'selected' : ''}>${escapeHtml(branch)}</option>`)
        .join('');

      if (!nodes.length) {
        versionTree.innerHTML = '<div class="tree-empty">暂无版本记录。执行写操作后会自动生成版本节点。</div>';
        updateSessionMeta();
        return;
      }

      const idMap = new Map();
      nodes.forEach((n) => idMap.set(n.version_id, n));

      const depthMemo = new Map();
      function calcDepth(node) {
        if (!node || !node.parent_version_id) return 0;
        if (depthMemo.has(node.version_id)) return depthMemo.get(node.version_id);

        let depth = 0;
        let cur = node;
        let guard = 0;
        while (cur && cur.parent_version_id && guard < 60) {
          const parent = idMap.get(cur.parent_version_id);
          if (!parent) {
            depth += 1;
            break;
          }
          depth += 1;
          cur = parent;
          guard += 1;
        }
        depthMemo.set(node.version_id, depth);
        return depth;
      }

      const sorted = [...nodes].sort((a, b) => {
        const ta = new Date(a.created_at).getTime();
        const tb = new Date(b.created_at).getTime();
        return tb - ta;
      });

      versionTree.innerHTML = sorted.map((node) => {
        const branch = (node.branch || 'main').trim() || 'main';
        const depth = Math.min(calcDepth(node), 8);
        const isHead = heads[branch] === node.version_id;
        const style = depth > 0 ? ` style="margin-left:${depth * 12}px"` : '';
        const metadata = node.metadata && typeof node.metadata === 'object' ? node.metadata : {};
        const changeLog = metadata.change_log && typeof metadata.change_log === 'object' ? metadata.change_log : null;
        const summary = changeLog && changeLog.summary
          ? String(changeLog.summary)
          : String(metadata.operation_summary || '版本快照');
        const rowcount = changeLog && Number.isFinite(changeLog.rowcount)
          ? Number(changeLog.rowcount)
          : '-';
        const touchedTables = Array.isArray(changeLog?.touched_tables)
          ? changeLog.touched_tables
          : (Array.isArray(metadata.touched_tables) ? metadata.touched_tables : []);
        const touchedText = touchedTables.length ? touchedTables.join(', ') : '';
        const traceId = metadata.trace_id || '-';
        return `
          <div class="tree-item ${isHead ? 'head' : ''}"${style}>
            <div class="tree-top">
              <div class="tree-label">${escapeHtml(node.label || '-')}</div>
              <div class="tree-tags">
                <span class="tree-tag">${escapeHtml(branch)}</span>
                ${isHead ? '<span class="tree-tag head">HEAD</span>' : ''}
              </div>
            </div>
            <div class="tree-meta">id: ${escapeHtml(shortId(node.version_id))} · parent: ${escapeHtml(shortId(node.parent_version_id))}</div>
            <div class="tree-meta">修改: ${escapeHtml(summary)} · 影响行: ${escapeHtml(String(rowcount))}</div>
            ${touchedText ? `<div class="tree-meta">触表: ${escapeHtml(touchedText)}</div>` : ''}
            <div class="tree-meta">trace: ${escapeHtml(shortId(traceId))}</div>
            <div class="tree-meta">${escapeHtml(formatDateTime(node.created_at))}</div>
            <div class="tree-actions">
              <button class="tree-rollback-btn" data-version-id="${escapeHtml(node.version_id)}" ${isHead ? 'disabled' : ''}>回滚到此版本</button>
            </div>
          </div>
        `;
      }).join('');

      versionTree.querySelectorAll('.tree-rollback-btn').forEach((btn) => {
        btn.addEventListener('click', async () => {
          const versionId = btn.getAttribute('data-version-id');
          if (!versionId) return;
          await rollbackToVersion(versionId);
        });
      });

      updateSessionMeta();
    }

    async function rollbackToVersion(versionId) {
      if (!window.confirm(`确认回滚到版本 ${shortId(versionId)} 吗？`)) {
        return;
      }

      setStatus('working');
      try {
        await requestJson(`/v1/admin/rollback/${encodeURIComponent(versionId)}?thread_id=${encodeURIComponent(session.threadId)}&branch=${encodeURIComponent(session.branch)}`, {
          method: 'POST',
        });
        appendMessage('assistant', `已回滚到版本 ${shortId(versionId)}（分支 ${session.branch}）。`, '系统');
        setStatus('completed');
        await loadVersionTree({ silent: true });
        await loadChangeExplanations({ silent: true });
      } catch (err) {
        appendMessage('assistant', `回滚失败: ${err}`, '系统');
        setStatus('error');
      }
    }

    async function createBranch() {
      const branch = (branchInput.value || '').trim();
      if (!branch) return;

      try {
        await requestJson('/v1/admin/branches', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            thread_id: session.threadId,
            branch,
            from_branch: session.branch,
          }),
        });

        branchInput.value = '';
        await checkoutBranch(branch, { silentMessage: true });
        appendMessage('assistant', `分支 ${branch} 创建成功，并已切换。`, '系统');
      } catch (err) {
        appendMessage('assistant', `创建分支失败: ${err}`, '系统');
      }
    }

    async function checkoutBranch(branch, { silentMessage = false } = {}) {
      const target = (branch || '').trim();
      if (!target) return;

      try {
        await requestJson('/v1/admin/checkout', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            thread_id: session.threadId,
            branch: target,
          }),
        });
        session.branch = target;
        await loadVersionTree({ silent: true });
        await loadChangeExplanations({ silent: true });
        if (!silentMessage) {
          appendMessage('assistant', `已切换到分支 ${target}。`, '系统');
        }
      } catch (err) {
        appendMessage('assistant', `切换分支失败: ${err}`, '系统');
      }
    }

    function renderEvidence(evidence) {
      if (!Array.isArray(evidence) || evidence.length === 0) {
        evidenceList.innerHTML = '<div class="evidence-item"><p class="evidence-title">暂无证据</p><div class="evidence-meta">本次未命中图谱节点。</div></div>';
        return;
      }

      evidenceList.innerHTML = evidence.map((e) => {
        const score = Number(e.score || 0).toFixed(4);
        return `
          <div class="evidence-item">
            <p class="evidence-title">${escapeHtml(e.title || '-')}</p>
            <div class="evidence-meta">node: ${escapeHtml(e.node_id || '-')} · score: ${score}</div>
            <div class="evidence-meta">${escapeHtml(e.relation_summary || 'no relation summary')}</div>
          </div>
        `;
      }).join('');
    }

    function renderSummary(resp) {
      traceId.textContent = resp.trace_id || '-';
      approvalId.textContent = resp.approval_ticket_id || '-';
      rowsCount.textContent = String(((resp.execution || {}).rowcount ?? '-'));

      const pre = (resp.security || {}).pre || {};
      const rule = pre.rule_decision || {};
      const copilot = resp.approval_copilot || {};
      decisionText.textContent = copilot.final_decision || pre.final_decision || '-';
      riskText.textContent = copilot.risk_level || rule.risk_level || '-';
    }

    function renderDebug(resp) {
      sqlView.textContent = resp.generated_sql || '无 SQL';
      pyView.textContent = resp.generated_python_code || '无 Python 草案';
      securityView.textContent = JSON.stringify(resp.security || {}, null, 2);
      const copilot = resp.approval_copilot || (resp.security || {}).approval_copilot || null;
      approvalCopilotView.textContent = copilot ? JSON.stringify(copilot, null, 2) : '尚无审批建议';
    }

    async function send() {
      const text = input.value.trim();
      if (!text) return;

      appendMessage('user', text, '用户');
      input.value = '';
      sendBtn.disabled = true;
      sendBtn.textContent = '发送中...';
      setStatus('working');

      try {
        const resp = await fetch('/v1/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: session.userId,
            thread_id: session.threadId,
            branch: session.branch,
            message: text,
            auto_approve: autoApprove.checked,
          }),
        });

        const data = await resp.json();
        if (!resp.ok) {
          appendMessage('assistant', `请求失败: ${resp.status} ${JSON.stringify(data)}`, '系统');
          setStatus('error');
          return;
        }

        appendMessage('assistant', data.answer || '无返回内容', '助手');
        setStatus(data.status || 'waiting');
        renderSummary(data);
        renderEvidence(data.evidence || []);
        renderDebug(data);
        await loadVersionTree({ silent: true });
        await loadChangeExplanations({ silent: true });
        await loadApprovals({ silent: true, keepSelection: false });
        if (data.approval_ticket_id) {
          await selectApproval(String(data.approval_ticket_id), { silent: true });
        }
      } catch (err) {
        appendMessage('assistant', `网络错误: ${err}`, '系统');
        setStatus('error');
      } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = '发送请求';
      }
    }

    sendBtn.addEventListener('click', send);
    input.addEventListener('keydown', (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
        send();
      }
    });

    createBranchBtn.addEventListener('click', createBranch);
    branchInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        createBranch();
      }
    });

    checkoutBranchBtn.addEventListener('click', async () => {
      await checkoutBranch(branchSelect.value);
    });

    refreshTreeBtn.addEventListener('click', async () => {
      await loadVersionTree();
    });

    refreshChangeExplainBtn.addEventListener('click', async () => {
      await loadChangeExplanations();
    });

    refreshApprovalsBtn.addEventListener('click', async () => {
      await loadApprovals({ keepSelection: true });
    });

    approvalFilter.addEventListener('change', async () => {
      await loadApprovals({ keepSelection: false });
    });

    approveTicketBtn.addEventListener('click', async () => {
      await decideApproval(true);
    });

    rejectTicketBtn.addEventListener('click', async () => {
      await decideApproval(false);
    });

    setStatus('waiting');
    setApprovalDetail(null);
    loadVersionTree({ silent: true });
    loadChangeExplanations({ silent: true });
    loadApprovals({ silent: true, keepSelection: false });
  </script>
</body>
</html>
"""
