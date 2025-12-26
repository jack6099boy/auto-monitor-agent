#!/usr/bin/env python3
"""
AutoTest AIOps Agent 演示腳本

此腳本展示系統功能：
1. 創建假的 SOP 文件到 sop/ 目錄
2. 創建假的 log 文件到 logs/ 目錄
3. 初始化 RAG 系統、監控模組和 Agent
4. 模擬異常檢測和通知發送
5. 運行 Agent 處理異常並查詢 SOP
"""

import os
import time
import threading
from dotenv import load_dotenv
from agent.rag import RAGSystem
from agent.monitor import LogMonitor
from agent.agent import agent as ai_agent
from langchain_core.messages import HumanMessage

# 載入環境變數
load_dotenv()

# 確保 OPENROUTER_API_KEY 已設定
if not os.getenv('OPENROUTER_API_KEY'):
    raise ValueError("OPENROUTER_API_KEY 環境變數未設定。請在 .env 文件中設定或直接設定環境變數。")


def create_fake_sop():
    """創建假的 SOP 文件"""
    sop_content = """
# 錯誤處理標準操作程序 (SOP)

## 概述
本 SOP 定義了處理系統錯誤的標準流程。

## 錯誤類型
1. 網路錯誤：檢查網路連接，重啟服務
2. 資料庫錯誤：檢查資料庫連接，重啟資料庫服務
3. 應用程式錯誤：檢查日誌，重新部署應用程式

## 處理步驟
1. 記錄錯誤詳情
2. 識別錯誤類型
3. 應用相應修復措施
4. 驗證修復結果
5. 更新狀態

## 聯絡資訊
- 開發團隊：dev@company.com
- 運維團隊：ops@company.com
"""
    sop_path = "sop/error_handling_sop.md"
    with open(sop_path, 'w', encoding='utf-8') as f:
        f.write(sop_content)
    print(f"已創建假 SOP 文件：{sop_path}")


def create_fake_logs():
    """創建假的 log 文件"""
    # 正常 log
    normal_logs = [
        "2024-01-01 10:00:00 INFO Application started successfully",
        "2024-01-01 10:01:00 INFO Database connection established",
        "2024-01-01 10:02:00 INFO User login: user123",
        "2024-01-01 10:03:00 INFO API request processed: /api/users",
        "2024-01-01 10:04:00 INFO Cache updated",
    ]

    # 異常 log
    anomaly_log = "2024-01-01 10:05:00 ERROR Database connection failed: timeout after 30 seconds"

    log_path = "logs/application.log"
    with open(log_path, 'w', encoding='utf-8') as f:
        for log in normal_logs:
            f.write(log + '\n')
    print(f"已創建假 log 文件：{log_path}")

    # 模擬異常：稍後添加異常 log
    time.sleep(2)  # 等待監控啟動
    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(anomaly_log + '\n')
    print(f"已添加異常 log：{anomaly_log}")


def run_demo():
    """運行演示"""
    print("=== AutoTest AIOps Agent 演示開始 ===")

    # 1. 創建假數據
    print("\n1. 創建假數據...")
    create_fake_sop()
    create_fake_logs()

    # 2. 初始化 RAG 系統
    print("\n2. 初始化 RAG 系統...")
    rag_system = RAGSystem()
    try:
        rag_system.build_index()
        print("RAG 索引建立成功")
    except Exception as e:
        print(f"RAG 索引建立失敗: {e}")
        return

    # 3. 初始化監控模組
    print("\n3. 初始化監控模組...")
    monitor = LogMonitor()

    # 4. 啟動監控在背景執行緒
    print("\n4. 啟動監控...")
    monitor_thread = threading.Thread(target=monitor.start_monitoring, daemon=True)
    monitor_thread.start()

    # 等待監控啟動
    time.sleep(1)

    # 5. 模擬異常檢測（通過寫入異常 log）
    print("\n5. 模擬異常檢測...")
    # 異常已經在 create_fake_logs 中添加

    # 等待異常被檢測
    time.sleep(3)

    # 6. 運行 Agent 處理異常
    print("\n6. 運行 Agent 處理異常...")
    query = "檢測到異常，請查詢相關 SOP 並提供處理建議"
    messages = [HumanMessage(content=query)]

    try:
        result = ai_agent.invoke({"messages": messages})
        print("Agent 回應:")
        print(result["messages"][-1].content)
    except Exception as e:
        print(f"Agent 執行失敗: {e}")

    # 7. 檢查異常
    print("\n7. 檢查檢測到的異常...")
    if monitor.anomalies:
        print("檢測到的異常:")
        for anomaly in monitor.anomalies:
            print(f"- {anomaly}")
    else:
        print("未檢測到異常")

    # 8. 測試 RAG 查詢
    print("\n8. 測試 RAG 查詢...")
    sop_query = "資料庫連接失敗的處理步驟"
    try:
        response = rag_system.query(sop_query)
        print(f"SOP 查詢結果 ({sop_query}):")
        print(response)
    except Exception as e:
        print(f"RAG 查詢失敗: {e}")

    print("\n=== 演示完成 ===")


if __name__ == "__main__":
    run_demo()