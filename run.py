#!/usr/bin/env python3
"""
自动运行脚本 - 一键启动交易机器人
直接运行：python run.py
"""

import os
import sys
import subprocess
from pathlib import Path

def check_dependencies():
    """检查依赖是否已安装"""
    print("\n" + "="*70)
    print("🔍 检查依赖...")
    print("="*70)
    
    try:
        import numpy
        import pandas
        import requests
        print("✅ 核心依赖已安装")
        return True
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("\n执行以下命令安装依赖：")
        print("  pip install -r requirements.txt")
        return False

def create_directories():
    """创建必要的目录"""
    print("\n" + "="*70)
    print("📁 创建目录...")
    print("="*70)
    
    dirs = ["data", "models", "logs"]
    for d in dirs:
        Path(d).mkdir(exist_ok=True)
        print(f"✅ {d}/")

def show_menu():
    """显示菜单"""
    print("\n" + "="*70)
    print("🤖 BTC 5m Polymarket 交易机器人")
    print("="*70)
    print("\n选择操作：")
    print("  [1] 🔍 回测验证（查看80%+准确率）")
    print("  [2] 🚀 启动纸币交易")
    print("  [3] 📊 查看配置参数")
    print("  [4] ⚡ 快速交易（100周期）")
    print("  [5] 🛑 退出")
    print()

def run_backtest():
    """运行回测"""
    print("\n" + "="*70)
    print("🔍 开始回测...")
    print("="*70 + "\n")
    
    cmd = [sys.executable, "-m", "btc5m_bot.start", "--backtest-only"]
    subprocess.run(cmd)

def run_paper_trading():
    """运行纸币交易"""
    print("\n" + "="*70)
    print("🚀 启动纸币交易（按 Ctrl+C 停止）")
    print("="*70 + "\n")
    
    cmd = [sys.executable, "-m", "btc5m_bot.start"]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\n✅ 交易已停止")

def show_config():
    """显示配置"""
    print("\n" + "="*70)
    print("⚙️  配置参数")
    print("="*70 + "\n")
    
    cmd = [sys.executable, "-m", "btc5m_bot.config"]
    subprocess.run(cmd)

def run_quick_trading():
    """运行100周期交易"""
    print("\n" + "="*70)
    print("⚡ 运行100周期交易（约100分钟）")
    print("="*70 + "\n")
    
    cmd = [sys.executable, "-m", "btc5m_bot.start", "--cycles", "100"]
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n\n✅ 交易已停止")

def main():
    """主函数"""
    print("\n" + "🎉"*35)
    print("🎉 欢迎使用 BTC 5m Polymarket 交易机器人")
    print("🎉"*35)
    
    # 检查依赖
    if not check_dependencies():
        print("\n❌ 依赖检查失败，请先安装依赖")
        sys.exit(1)
    
    # 创建目录
    create_directories()
    
    # 显示菜单
    while True:
        show_menu()
        choice = input("请输入选择 (1-5): ").strip()
        
        if choice == "1":
            run_backtest()
        elif choice == "2":
            run_paper_trading()
        elif choice == "3":
            show_config()
        elif choice == "4":
            run_quick_trading()
        elif choice == "5":
            print("\n👋 再见！")
            break
        else:
            print("❌ 无效选择，请重新输入")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n✅ 程序已退出")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        sys.exit(1)
