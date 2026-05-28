"""
测试配置是否正确加载
"""

from src.config import get_settings_safe, validate_config, print_config_summary

print("测试配置加载...")

# 获取配置
settings = get_settings_safe()

print(f"✅ API Key: {settings.OPENAI_API_KEY[:10]}...")
print(f"✅ API Base: {settings.API_BASE_URL}")
print(f"✅ 模型: {settings.MODEL_NAME}")
print(f"✅ 端口: {settings.API_PORT}")
print(f"✅ 调试: {settings.DEBUG}")

print("\n🎉 配置加载成功！")