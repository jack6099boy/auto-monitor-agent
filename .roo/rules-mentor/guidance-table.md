# Roo Code 代理生成專業指導表格

這是 8 項推理來源與 5 大核心原則的對應框架（基於 GitHub agents.md 分析與 Roo Code 實務）。

| 八項來源（推理時讀進的上下文） | 對應的核心原則（超簡版口訣） | 是否需要手寫 | 寫在哪裡（具體位置） | 範例內容（直接 copy 可改） |
|--------------------------------|-------------------------------|--------------|----------------------|-----------------------------|
| 1. System Prompt（固定）       | 1. 明確角色                  | 是          | .roomodes 的 roleDefinition | `roleDefinition: 你是資深 React 測試工程師，專門寫 Jest 測試，永不修改 src/ 程式碼` |
| 2. AGENTS.md / .roo/rules-xxx/ | 2. 給足上下文                | 是          | .roo/rules-general/ 的 Markdown（如 project-overview.md） | ```markdown<br>## 技術堆疊<br>React 18 + TypeScript 5 + Vite<br>## 檔案結構<br>src/ → 程式碼<br>tests/ → 測試<br>## 風格範例<br>// 好範例<br>export const Button = () => <button>Click</button>;<br>``` |
| 3. Mode-specific 規則          | 2+4. 上下文與界限            | 是          | .roomodes 的 customInstructions 或 mode 專屬 rules 資料夾 | `customInstructions: |`<br>`  - ✅ 永遠寫入 docs/`<br>`  - 🚫 絕對不要改程式碼` |
| 4. Conversation History        | 5. 從小迭代                  | 否（自動）  | 無需手寫（Roo Code 自動記錄） | 無需寫（用 Boomerang 觀察聊天 log 找 bug） |
| 5. Workspace Context           | 2. 給足上下文                | 否（自動）  | 無需手寫（自動讀取開啟檔案） | 無需寫（VS Code 開 src/ 讓代理看到實際程式碼） |
| 6. Sub-task Results            | 5. 從小迭代                  | 部分        | customInstructions 引導 summary 格式 | `customInstructions: |`<br>`  - 子任務完成後回傳 summary 如 "測試通過，覆蓋率 95%"` |
| 7. MCP Tools / External        | 3. 提供工具                  | 是          | .roomodes 的 groups + customInstructions | `groups: ["read", "edit", "command"]`<br>`customInstructions: |`<br>`  - 使用 npm test 驗證`<br>`  - 使用 git commit 提交` |
| 8. Memory Bank                 | 5. 從小迭代（持久記憶）      | 部分        | groups: ["mcp"] + customInstructions 引導 | `groups: ["mcp"]`<br>`customInstructions: |`<br>`  - 啟用 Memory Bank`<br>`  - 每次迭代更新 progress.md` |

**使用建議**：把這個表格當 checklist。先填靜態部分（1-3,7-8），再用 Boomerang 測試動態部分（4-6）。