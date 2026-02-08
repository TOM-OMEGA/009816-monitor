#!/usr/bin/env python3
# test_ai.py - AI 模組診斷工具（加強版）

import os
import sys

print("=" * 50)
print("🧪 AI 模組診斷工具 v2.0")
print("=" * 50)

# 1. 檢查環境變數
print("\n📋 步驟 1: 檢查環境變數")
gemini_key = os.environ.get("GEMINI_API_KEY")

if gemini_key:
    print(f"✅ GEMINI_API_KEY 已設定")
    print(f"   長度: {len(gemini_key)} 字元")
    print(f"   開頭: {gemini_key[:10]}...")
else:
    print("❌ GEMINI_API_KEY 未設定")
    print("\n💡 解決方法：")
    print("1. 前往 https://aistudio.google.com/app/apikey")
    print("2. 建立 API Key")
    print("3. 在部署平台設定環境變數：")
    print("   GEMINI_API_KEY=你的金鑰")
    sys.exit(1)

# 2. 檢查模組導入
print("\n📋 步驟 2: 檢查模組導入")
try:
    from ai_expert import get_ai_point
    print("✅ ai_expert 模組導入成功")
except ImportError as e:
    print(f"❌ ai_expert 模組導入失敗: {e}")
    sys.exit(1)

# 3. 測試 API 呼叫（簡單測試）
print("\n📋 步驟 3: 測試 API 呼叫（簡單）")
test_data_simple = {
    "price": 15.5,
    "k_line": "上漲",
    "valuation": "50%",
    "tech": "多頭"
}

print("正在呼叫 Gemini API（簡單測試）...")
result1 = get_ai_point(
    extra_data=test_data_simple, 
    target_name="測試標的A", 
    debug=True
)

print("\n📊 簡單測試結果：")
print(f"   決策: {result1['decision']}")
print(f"   信心度: {result1['confidence']}%")
print(f"   理由: {result1['reason']}")

# 4. 測試 API 呼叫（複雜測試）
print("\n📋 步驟 4: 測試 API 呼叫（複雜）")
test_data_complex = {
    "price": 175.3,
    "k_line": "🔴 強勢多頭",
    "valuation": "RSI 68.5",
    "tech": "MA20: 170.2, MA60: 165.8",
    "order_strength": "網格策略",
    "market_context": "補倉點 172.5"
}

print("正在呼叫 Gemini API（複雜測試）...")
result2 = get_ai_point(
    extra_data=test_data_complex, 
    target_name="2317 鴻海", 
    debug=True
)

print("\n📊 複雜測試結果：")
print(f"   決策: {result2['decision']}")
print(f"   信心度: {result2['confidence']}%")
print(f"   理由: {result2['reason']}")

# 5. 判斷結果
print("\n" + "=" * 50)
success_count = 0
if result1['decision'] != 'ERROR' and result1['confidence'] > 0:
    success_count += 1
if result2['decision'] != 'ERROR' and result2['confidence'] > 0:
    success_count += 1

if success_count == 2:
    print("✅ AI 模組運作完全正常！")
    print("\n🚀 你可以開始使用完整系統了")
    print("\n💡 建議：")
    print("   1. 部署到 Render")
    print("   2. 訪問 /run 路徑")
    print("   3. 檢查 Discord 訊息")
elif success_count == 1:
    print("⚠️ AI 模組部分正常")
    print("\n💡 建議：繼續測試，可能是暫時性問題")
else:
    print("❌ AI 模組有問題")
    print(f"\n錯誤訊息:")
    print(f"   測試1: {result1['reason']}")
    print(f"   測試2: {result2['reason']}")
    print("\n💡 請檢查：")
    print("1. API Key 是否正確")
    print("2. 網路連線是否正常")
    print("3. Gemini API 配額是否用完")

print("=" * 50)
