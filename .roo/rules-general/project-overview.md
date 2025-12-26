# AutoTest AIOps Agent 專案概述

## 專案背景
公司自動化測試流程基於 C# 開發，涉及手機夾持、拍攝等步驟。現有痛點包括頻繁中斷、維護負擔重、log 異質性及 SOP 存取不便。本專案旨在建構智能監控與容錯系統，提升測試站穩定性。

## 技術堆疊
- **現有系統**：C# (測試邏輯)
- **新代理系統**：Python
  - Drain3：log 解析
  - Docling：文件提取 (PPT/PDF → Markdown)
  - Chroma：向量資料庫
  - LlamaIndex：RAG 框架
  - LangChain + LangGraph：Agent 框架 (混合模式)
  - bge-large-zh-v1.5：嵌入模型
  - GPT-4o-mini：LLM
- **監控**：watchdog
- **通知**：Slack / Email

## 檔案結構
- `src/`：C# 測試程式碼
- `logs/`：各 LAB log 檔案
- `sop/`：SOP 文件 (PPT/PDF)
- `agent/`：Python 代理程式碼
  - `monitor.py`：watchdog + Drain3
  - `rag.py`：知識庫建構與查詢
  - `agent.py`：LangChain/LangGraph 邏輯
- `docs/`：專案文件

## 風格範例
### Python 程式碼風格
```python
import watchdog.events
from drain3 import TemplateMiner

class LogMonitor(watchdog.events.FileSystemEventHandler):
    def __init__(self):
        self.template_miner = TemplateMiner()

    def on_modified(self, event):
        if event.src_path.endswith('.log'):
            with open(event.src_path, 'r') as f:
                log_line = f.readline()
                result = self.template_miner.add_log_message(log_line)
                if result['change_type'] != 'none':
                    print(f"異常偵測: {result}")
```

### 專案規劃輸出格式
- 階段性任務清單
- 風險評估表格
- 時程甘特圖 (Markdown)