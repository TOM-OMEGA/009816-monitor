#!/usr/bin/env python3
# test_ai.py - AI 模組測試腳本

import os
import sys

print("=" * 50)
print("🧪 AI 模組診斷工具")
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

# 3. 測試 API 呼叫
print("\n📋 步驟 3: 測試 API 呼叫")
test_data = {
    "price": 15.5,
    "k_line": "上漲",
    "valuation": "50%",
    "tech": "MA20 交叉向上"
}

print("正在呼叫 Gemini API...")
result = get_ai_point(
    extra_data=test_data, 
    target_name="測試標的", 
    debug=True
)

print("\n📊 API 回應結果：")
print(f"   決策: {result['decision']}")
print(f"   信心度: {result['confidence']}%")
print(f"   理由: {result['reason']}")

# 4. 判斷結果
print("\n" + "=" * 50)
if result['decision'] != 'ERROR' and result['confidence'] > 0:
    print("✅ AI 模組運作正常！")
    print("\n🚀 你可以開始使用完整系統了")
else:
    print("⚠️ AI 模組有問題")
    print(f"\n錯誤訊息: {result['reason']}")
    print("\n💡 請檢查：")
    print("1. API Key 是否正確")
    print("2. 網路連線是否正常")
    print("3. Gemini API 額度是否用完")

print("=" * 50)
