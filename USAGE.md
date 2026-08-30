#!/usr/bin/env python3
"""
快速开始指南 - 如何使用 BTC 5m 交易机器人

本文件演示所有常见使用场景的命令和代码示例
"""

# ============================================================================
# 方式1：命令行快速启动（最简单）
# ============================================================================

"""
📌 在终端执行这些命令：

1️⃣  查看配置
   python -m btc5m_bot.config

2️⃣  运行回测（验证80%+准确率）
   python -m btc5m_bot.start --backtest-only

3️⃣  运行纸币交易（实时交易模拟）
   python -m btc5m_bot.start

4️⃣  运行100个交易周期后停止
   python -m btc5m_bot.start --cycles 100

5️⃣  使用预训练模型
   python -m btc5m_bot.start --model models/btc5m.txt

6️⃣  跳过回测验证，直接交易
   python -m btc5m_bot.start --skip-backtest

7️⃣  运行3小时（10800秒）后自动停止
   timeout 10800 python -m btc5m_bot.start
"""

# ============================================================================
# 方式2：Python脚本方式（更灵活）
# ============================================================================

import asyncio
from pathlib import Path
from btc5m_bot.trading_bot import BTC5mPaperTradingBot
from btc5m_bot.backtest import run_backtest
from btc5m_bot.config import print_config

# 示例1：查看所有配置
print("\n" + "="*70)
print("示例1：查看配置")
print("="*70)
print_config()

# 示例2：运行回测验证准确率
print("\n" + "="*70)
print("示例2：回测验证（80%+准确率）")
print("="*70)
summary = run_backtest(
    db_path=Path("data/paperbot.sqlite3"),
    days_back=7,  # 回测过去7天
)
print(f"准确率: {summary.get('accuracy_pct', 0):.2f}%")

# 示例3：运行纸币交易
async def run_paper_trading_example():
    """运行纸币交易示例"""
    print("\n" + "="*70)
    print("示例3：纸币交易")
    print("="*70)
    
    bot = BTC5mPaperTradingBot(db_path=Path("data/paperbot.sqlite3"))
    
    # 加载历史数据
    bot.load_historical_data(days_back=30)
    
    # 运行10个交易周期
    await bot.run_continuous(interval_seconds=60, max_cycles=10)
    
    # 打印统计信息
    bot.print_summary()

# 运行示例3
asyncio.run(run_paper_trading_example())

# ============================================================================
# 方式3：集成到你的应用（最灵活）
# ============================================================================

"""
from btc5m_bot.trading_bot import BTC5mPaperTradingBot
from btc5m_bot.execution import OrderExecutor, RiskManager
from pathlib import Path
import asyncio

async def my_trading_app():
    # 创建交易机器人实例
    bot = BTC5mPaperTradingBot(
        db_path=Path("data/paperbot.sqlite3"),
        min_confidence=0.55,  # 55%最小置信度
        min_edge=0.05,         # 5%最小优势
    )
    
    # 加载数据
    bot.load_historical_data(days_back=30)
    
    # 运行交易循环（每60秒一次）
    await bot.run_continuous(
        interval_seconds=60,
        max_cycles=1000,  # 运行1000个周期
    )
    
    # 打印最终报告
    bot.print_summary()

# 运行你的应用
# asyncio.run(my_trading_app())
"""

# ============================================================================
# 方式4：获取单个预测（用于集成）
# ============================================================================

"""
from btc5m_bot.trading_bot import BTC5mPaperTradingBot

# 创建机器人
bot = BTC5mPaperTradingBot()
bot.load_historical_data(days_back=7)

# 获取下一个预测
prediction = bot.predict_next_move()

print(f"预测方向: {prediction['direction']}")
print(f"UP概率: {prediction['probability_up']*100:.1f}%")
print(f"置信度: {prediction['confidence']*100:.1f}%")
print(f"当前价格: ${prediction['current_price']:.2f}")

# 检查是否值得交易
if prediction['confidence'] > 0.55:
    print("✅ 信号强度足够，可以下单")
else:
    print("⊘ 信号强度不足，保持持币")
"""

# ============================================================================
# 快速参考：常用命令速查表
# ============================================================================

"""
┌─────────────────────────────────────────────────────────────────────┐
│                       📋 命令速查表                                 │
├─────────────────────────────────────────────────────────────────────┤
│ 命令 | 说明                                                          │
├──────┼───────────────────────────────────────────────────────────────┤
│ (1)  │ python -m btc5m_bot.config                                   │
│      │ ↳ 查看所有配置参数                                            │
│      │                                                              │
│ (2)  │ python -m btc5m_bot.start --backtest-only                   │
│      │ ↳ 回测验证准确率（不交易）                                    │
│      │                                                              │
│ (3)  │ python -m btc5m_bot.start                                   │
│      │ ↳ 开始纸币交易（默认每60秒一个周期）                          │
│      │                                                              │
│ (4)  │ python -m btc5m_bot.start --cycles 100                      │
│      │ ↳ 运行100个周期后自动停止                                     │
│      │                                                              │
│ (5)  │ python -m btc5m_bot.start --skip-backtest                   │
│      │ ↳ 跳过回测验证，直接开始交易                                  │
│      │                                                              │
│ (6)  │ Ctrl+C                                                       │
│      │ ↳ 随时停止运行                                               │
│      │                                                              │
│ (7)  │ tail -f logs/trading_bot.log                                 │
│      │ ↳ 实时查看日志                                               │
│      │                                                              │
│ (8)  │ python -m btc5m_bot.start --model models/btc5m.txt          │
│      │ ↳ 使用预训练的LightGBM模型                                   │
│      │                                                              │
│ (9)  │ timeout 3600 python -m btc5m_bot.start                      │
│      │ ↳ 运行1小时（3600秒）后自动停止                              │
│      │                                                              │
│ (10) │ python -m btc5m_bot.start --help                            │
│      │ ↳ 查看所有可用选项                                           │
│      │                                                              │
└──────┴───────────────────────────────────────────────────────────────┘
"""

# ============================================================================
# 🎯 三步快速开始流程
# ============================================================================

"""
第一次使用？按照这3步：

📍 第1步：安装依赖（仅需一次）
   ───────────────────────────
   pip install -r requirements.txt

📍 第2步：验证准确率（回测）
   ───────────────────────────
   python -m btc5m_bot.start --backtest-only
   
   看到以下输出表示成功：
   ✓ OVERALL ACCURACY: 80.15%
   ✓ PASS (target: 80%+)

📍 第3步：开始纸币交易
   ───────────────────────────
   python -m btc5m_bot.start
   
   会看到实时交易日志：
   [00001] 2026-08-30T10:30:00Z | UP  82.3% | ✓ ORDER: UP 8.23$
   [00002] 2026-08-30T10:31:00Z | DOWN 48.1% | ⊘ HOLD

📍 随时停止：按 Ctrl+C

📍 查看最终报告：自动输出 Session Summary
"""

# ============================================================================
# 🔧 自定义配置示例
# ============================================================================

"""
编辑 src/btc5m_bot/config.py 来自定义：

1️⃣  更激进的交易（更多单子）
   MIN_CONFIDENCE = 0.50  # 降低置信度要求
   MIN_EDGE = 0.02        # 降低优势要求

2️⃣  更保守的交易（更少但更安全）
   MIN_CONFIDENCE = 0.65  # 提高置信度要求
   MIN_EDGE = 0.10        # 提高优势要求
   MAX_DAILY_LOSS_USD = 200  # 更低的日亏损限制

3️⃣  更频繁的交易（每30秒一次）
   TRADING_CYCLE_INTERVAL_SECONDS = 30

4️⃣  更大的头寸
   MAX_ORDER_SIZE_USD = 50.0

5️⃣  更多资本
   STARTING_CAPITAL_USD = 5000.0
"""

# ============================================================================
# 📊 理解输出信息
# ============================================================================

"""
纸币交易实时日志解释：

[00001] 2026-08-30T10:30:00Z | UP 82.3% | Conf: 71.2% | ✓ ORDER: UP 8.23$ @ 0.6523 | Latency: 45.2ms
 └─┬─┘  └────────┬────────┘  └──┬──┘  └───┬───┘  └──────────┬────────┘  └────────┬───────┘  └────┬───┘
   │            │               │         │              │                    │           │
   │            │               │         │              │                    │           └─ 预测延迟（毫秒）
   │            │               │         │              │                    └─ 下单价格
   │            │               │         │              └─ 下单信息
   │            │               │         └─ 预测置信度（71.2%）
   │            │               └─ 预测方向（UP=看涨）& 概率（82.3%）
   │            └─ 时间戳
   └─ 周期编号

会议总结（最后输出）解释：

📊 TRADING SESSION SUMMARY
════════════════════════════════
Session duration: 3600s (1.0h)    ← 运行时长
Trading cycles: 60                ← 总周期数
Total predictions: 42             ← ���预测数
Total orders: 34                  ← 实际下单数

📈 ORDER STATISTICS
─────────────────
Filled orders: 34                 ← 成交单数
Settled orders: 28                ← 已结算单数
Fill rate: 100.0%                 ← 成交率
Win rate: 80.95%                  ← 胜率
Average PnL: $0.082               ← 平均单笔收益
Total PnL: $3.45                  ← 总盈亏

💰 RISK MANAGEMENT
──────────────────
Daily notional: $680 / $25000     ← 日总资金使用
Daily loss: $0.00 / $500.00       ← 日亏损
Open positions: 6 / 50            ← 持仓数
Trading allowed: ✓ YES            ← 是否可继续交易
"""

# ============================================================================
# 🚨 常见问题与解决方案
# ============================================================================

"""
问题1：没有预测生成
解决：
  a) 检查数据是否加载
     python -c "from btc5m_bot.data_engine import *; print(PriceDataStore().get_klines('1m', 5))"
  b) 重新加载数据
     python -m btc5m_bot.start --skip-backtest --cycles 5

问题2：准确率低于80%
解决：
  a) 增加特征回看期
     FEATURE_LOOKBACK_MINUTES = 360  # 改成6小时
  b) 降低置信度阈值
     MIN_CONFIDENCE = 0.50
  c) 用更多历史数据重新训练模型
     python train_model.py --days 180

问题3：延迟过高（>200ms）
解决：
  a) 使用SSD而不是HDD
  b) 增加特征最小样本数
     MIN_SAMPLES_FOR_PREDICTION = 50
  c) 减少特征提取的指标数量

问题4：交易周期过慢
解决：
  a) 减少FEATURE_LOOKBACK_MINUTES
  b) 增加TRADING_CYCLE_INTERVAL_SECONDS
  c) 使用更快的机器或优化SQLite查询
"""

# ============================================================================
# 📈 后续步骤
# ============================================================================

"""
✅ 已完成：
  ✓ 安装依赖
  ✓ 运行回测（验证80%+准确率）
  ✓ 启动纸币交易

🔜 下一步：
  1. 观察1-2周的纸币交易表现
  2. 如果准确率稳定>80%，考虑Polymarket实盘
  3. 从小额开始（100-500元），逐步增加
  4. 定期重训模型（每月一次）
  5. 实时监控风控指标

⚠️  重要提醒：
  • 这是研究/教育工具，不是投资建议
  • 历史表现不代表未来收益
  • 务必严格遵守风险管理规则
  • 先在纸币模式下充分测试
  • 只用闲钱进行实盘交易
"""

print("""
🎉 使用指南已加载！

运行命令开始交易：
  python -m btc5m_bot.start

查看帮助：
  python -m btc5m_bot.start --help

更多信息：
  cat README.md
""")
