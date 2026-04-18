# 📊 多券商美股持仓追踪 Dashboard

一个基于 Streamlit 的轻量仪表盘，整合 IBKR（盈透证券）和 Charles Schwab（嘉信）的持仓数据，自动获取实时行情，展示总市值、盈亏、资产配置。

无需付费订阅，无需复杂配置，导出 CSV 一键导入，即刻拥有漂亮的整合仪表盘。

![Dashboard Preview](https://img.shields.io/badge/Python-3.9+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-red.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

## ✨ 功能特性

- 📊 **完整总览** - 显示总市值、总成本、总盈亏、今日涨跌
- 🏦 **多券商支持** - 同时支持 IBKR（盈透）、Schwab（嘉信）和 Firstrade（第一证券），按券商分组展示
- 🔄 **实时行情** - 一键从 Yahoo Finance 刷新最新价格
- 📈 **丰富图表** - 持仓占比饼图、资产树图、盈亏柱状图
- 📋 **可交互表格** - 支持筛选、排序，绿色盈利红色亏损一目了然
- 🌓 **主题切换** - 支持深色/浅色主题一键切换
- 🎯 **期权识别** - 自动识别期权策略组合（价差、跨式等）
- 💵 **现金支持** - 导入时自动提取现金余额，完整展示净资产
- 📁 **本地存储** - 数据保存在本地 JSON 文件，隐私安全

## 🚀 快速开始

### 1. 克隆项目安装依赖

```bash
git clone https://github.com/你的用户名/local_account.git
cd local_account
pip install -r requirements.txt
```

依赖只有几个核心包：`streamlit` `pandas` `yfinance` `plotly` `openpyxl`

### 2. 启动 Dashboard

```bash
streamlit run app.py
```

浏览器会自动打开 `http://localhost:8501`，即可看到 Dashboard。

## 📥 数据导入 - 详细导出指南

### 🔶 IBKR (盈透证券) 导出数据

IBKR 支持三种导出方式，推荐优先使用 **方式一 Flex Query**，最灵活最准确。

---

#### 方式一：Flex Query（⭐ 最推荐）

Flex Query 可以自定义导出字段，格式标准，最适合长期使用。

##### 第一步：创建 Flex Query

1. 登录 [IBKR Client Portal](https://www.interactivebrokers.com/portal)
2. 点击顶部菜单 **Performance & Reports** → **Flex Queries**
3. 点击 **Custom Flex Queries** → **+** 新建查询

**基本设置：**

| 设置项 | 推荐值 |
|--------|--------|
| Query Name | `Portfolio Export`（随便取名） |
| Format | **CSV** |
| Period | **Latest**（最新） |
| Date | 留空 |

##### 第二步：选择字段

在 **Sections** 区域，**只需要勾选两个**：
- ✅ **Open Positions**（当前持仓）- 必须勾选
- ✅ **Cash Report**（现金报告）- 必须勾选   

展开 **Open Positions**，勾选以下字段：

| 字段名 | 是否勾选 | 说明 |
|--------|---------|------|
| **Symbol** | ✅ **必须** | 股票代码 |
| **Quantity** / **Position** | ✅ **必须** | 持仓数量 |
| **CostBasisPrice** | ✅ **必须** | 买入均价（用于计算盈亏） |
| **Description** | ✅ 推荐 | 股票名称 |
| **MarkPrice** | ✅ 推荐 | 当前标记价格 |
| **MarketValue** | ✅ 推荐 | 当前市值 |
| **FifoPnlUnrealized** | ✅ 推荐 | 未实现盈亏 |
| **Currency** | ✅ 推荐 | 交易货币 |
| **Multiplier** | ⬜ 可选 | 期权用 |
| **Strike** | ⬜ 可选 | 期权行权价 |
| **Expiry** | ⬜ 可选 | 期权到期日 |
| **Put/Call** | ⬜ 可选 | 期权看涨/看跌 |

展开 **Cash Report**，勾选以下字段：
基础货币总结
| 字段名 | 是否勾选 | 说明 |
|--------|---------|------|
| **EndingCash** | ✅ **必须** | 结束现金余额 |


> 💡 **最简配置**：只需要 `Symbol` + `Quantity` + `CostBasisPrice` 三个字段，Dashboard 就能工作，其他字段会通过 Yahoo Finance 自动获取。

##### 第三步：（推荐）添加现金数据到 CSV 开头

你可以在导出的 CSV 文件**最前面手动添加两行**现金数据，这样导入时会自动提取：

```csv
"EndingCash","EndingCashSecurities","EndingCashCommodities"
"11924.43","11924.43","0"
ClientAccountID,AccountAlias,Model,... （这里是 Flex Query 的表头和数据，保持不变）
```

这样导入后，现金余额会自动添加到 IBKR 的现金账户中。

##### 第四步：运行下载

1. 保存 Flex Query
2. 回到列表 → 点击 **Run**
3. 选择格式 **CSV** → 下载保存到本地

---

#### 方式二：活动报表 (Activity Statement) 导出

这是 IBKR 内置的标准报表功能，适合偶尔查看：

1. 登录 Client Portal
2. 点击 **Performance & Reports** → **Statements**
3. 选择 **Activity** 类型
4. 日期选最近一天
5. 格式选 **CSV**
6. 点击下载

> ℹ️ Dashboard 会自动从多段格式的 CSV 中提取 `Open Positions` 部分，并尝试从 `Cash Report` 提取现金余额。

---

#### 方式三：TWS 桌面端导出

如果你使用 TWS (Trader Workstation) 客户端：

1. 打开 TWS
2. 点击 **Account** → 打开 Account Window
3. 点击 **File** → **Export Portfolio**
4. 保存为 CSV 即可

> ℹ️ 建议导出前在 Account Window 右键表头 → Configure Columns，确保包含 `Symbol`、`Position`、`Average Cost`、`Mark Price`。

---

#### IBKR 三种方式对比

| 特性 | Flex Query | Activity Statement | TWS Export |
|------|-----------|-------------------|------------|
| 推荐度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| 自定义字段 | ✅ 支持 | ❌ 固定 | ✅ 有限 |
| 格式简洁 | ✅ 是 | ❌ 多段 | ✅ 是 |
| 数据精度 | 最高 | 高 | 一般 |
| 操作步骤 | 配置一次永久使用 | 每次重新生成 | 打开TWS导出 |

---

### 🔵 Charles Schwab (嘉信) 导出数据

嘉信导出非常简单，几步搞定：

1. 登录 [schwab.com](https://www.schwab.com)
2. 点击顶部 **Accounts** → **Positions**
3. 确认选中正确账户
4. 点击 **Export** → 选择 **CSV** 格式
5. 保存文件

**Schwab CSV 格式示例：**

```csv
Symbol,Description,Quantity,Price,Market Value,Cost Basis,Gain/Loss,Gain/Loss %
AAPL,APPLE INC,100,"$178.72","$17872.00","$15000.00","$2872.00",19.15%
MSFT,MICROSOFT CORP,50,"$420.55","$21027.50","$18000.00","$3027.50",16.82%
```

> ⚠️ **特殊格式说明**：Schwab 导出的数值会带有 `="$178.72"` 这种格式，Dashboard 内置了清洗逻辑，会自动处理，你无需手动修改。

**现金提取说明**：嘉信现在支持 `Individual Positions` 导出格式，会有一行 `Cash & Cash Investments`，Dashboard 会自动识别并提取现金余额。

---

### 🟢 Firstrade (第一证券) 导出数据

Firstrade 导出非常直接，支持 Excel 格式：

1. 登录 [firstrade.com](https://www.firstrade.com)
2. 点击 **账户 (Accounts)** → **持仓 (Positions)**
3. 点击页面右上角的 **导出 (Export)** 按钮
4. 系统会下载一个 `.xlsx` 格式的文件

**支持的字段说明：**
Dashboard 会自动识别以下列名：
- `Symbol` (股票代码)
- `Quantity` (持仓数量)
- `Unit Cost` / `Adj. Unit Cost` (买入均价)
- `Last Price` / `Price` (当前价格)
- `Market Value` (当前市值)

> 💡 **提示**：Firstrade 导出的是 Excel 文件，导入时请确保上传原始的 `.xlsx` 文件，无需手动转为 CSV。

---

### 📤 导入到 Dashboard

无论哪种导出方式，导入步骤都一样：

1. 在 Dashboard 左侧边栏找到 **📥 导入持仓**
2. 点击 **Browse files** 上传你的 CSV 文件
3. 券商选择保持 **🔍 自动检测**（也可以手动选择）
4. 查看解析预览，确认正确
5. 勾选 **"替换 XX 的所有旧持仓"**（推荐，保持数据干净）
6. 点击 **📥 确认导入**

🎉 完成！数据已经导入，Dashboard 会自动刷新显示最新持仓。

## 🖼️ 界面预览

### 总览区域
显示总市值、总盈亏，按券商分组展示：

```
📈 总市值: $125,430.50
📉 总盈亏: +$12,340.25 (+10.85%)
🔺 今日涨跌: +$1,230.50 (+0.98%)
```

### 图表区域
- 🍩 持仓占比饼图 - 看清每个持仓占比
- 🗺️ 资产树图 - 按券商层级展示，颜色表示盈亏
- 📊 盈亏对比柱状图 - 直观对比各持仓盈亏
- 🏦 券商占比环形图 - 查看各券商资金分布

### 持仓表格
完整表格展示，支持：
- 按券商筛选
- 按任意列排序（代码、市值、盈亏等）
- 绿色盈利红色亏损，一目了然

## 💡 推荐工作流

```
1. 在 IBKR Client Portal 运行 Flex Query，下载 CSV
   （如果需要手动添加现金，在开头加两行）
2. 在 Schwab 网站导出 Positions CSV
3. 打开 Dashboard，分别上传两个 CSV
   （记得勾选"替换 XX 的所有旧持仓"）
4. 如果价格不是最新，点击"🔄 刷新实时行情"
5. 查看整合后的分析结果
```

> 💡 如果持仓变动不频繁，不需要每天导入。只需要在买卖操作后重新导出导入即可。日常查看点击刷新行情就能看到最新价格。

## ⚙️ 常见问题

**Q: 数据存在哪里？安全吗？**
> A: 所有持仓数据保存在项目目录下 `data/portfolio.json` 文件，完全在你的本地电脑，不会上传到任何服务器，隐私安全。

**Q: 行情数据从哪里来？延时吗？**
> A: 行情来自 Yahoo Finance，免费使用。美股盘后/节假日显示的是最后交易日收盘价，满足个人投资者需求。

**Q: 为什么有些持仓价格显示 0？**
> A: 如果 CSV 中没有提供价格，Dashboard 会在刷新行情时自动从 Yahoo Finance 获取。如果 Yahoo Finance 识别不了这个代码（比如某些小众OTC股票），就会显示 0。请确认你的代码是 Yahoo Finance 认可的标准代码。

**Q: 支持港股/A股吗？**
> A: 目前主要为美股设计。如果需要港股，代码要加后缀 `.HK`（如 `0700.HK`），Yahoo Finance 能识别就能出价格。

**Q: 可以手动添加持仓吗？**
> A: 可以！左侧边栏有 ✏️ 手动添加功能，输入代码、数量、成本即可添加。适合添加其他券商的少量持仓。

**Q: 如何删除错误导入的数据？**
> A: 左侧边栏底部 🗂️ 管理持仓，可以删除整个券商的所有持仓，也可以删除单个持仓。

## 📁 项目结构

```
local_account/
├── app.py                 # 主入口
├── requirements.txt       # 依赖
├── components/            # UI 组件
│   ├── overview.py       # 总览
│   ├── charts.py         # 图表
│   ├── positions_table.py # 持仓表格
│   └── import_panel.py   # 导入面板
├── importers/             # 导入器
│   ├── base.py           # 基类
│   ├── ibkr.py           # IBKR 导入
│   └── schwab.py         # Schwab 导入
├── services/              # 业务逻辑
│   ├── portfolio.py      # 投资组合管理
│   ├── market_data.py    # 行情获取
│   └── spread_detector.py # 期权策略检测
├── utils/                 # 工具函数
├── data/                  # 数据存储
│   └── portfolio.json    # 持仓数据
└── README.md             # 你正在看的这个文件
```

## 🤝 贡献

欢迎提 Issue 和 Pull Request！

## 📄 许可证

MIT License - 个人和商业用途免费使用。

## 🌟 鸣谢

- [Streamlit](https://streamlit.io/) - 优秀的数据应用框架
- [yfinance](https://github.com/ranaroussi/yfinance) - Yahoo Finance 行情 API
- [Plotly](https://plotly.com/) - 交互式图表

---

如果你觉得这个项目有用，欢迎点个 Star ⭐！

### 创建快捷方式：创建 .command 快捷脚本（最简单、关窗即停）
这是最直接的办法。双击运行，会弹出一个终端窗口显示运行状态；当你 关闭终端窗口 时，Streamlit 服务也会随之停止。

操作步骤：

1. 在桌面新建一个文本文件，重命名为 启动大师馆.command 。
2. 将以下内容粘贴进去：
```
#!/bin/bash
# 进入项目目录
cd "/Users/stock_portfolio"

# 运行 Streamlit (建议使用绝对路径防止环境问题)
# 如果你有虚拟环境，可以在这里先 source venv/bin/activate
streamlit run app.py
```
3. 关键一步 ：你需要给这个文件“执行权限”。打开终端，输入以下命令并回车：
   ```
   chmod +x ~/Desktop/启动大师馆.command
   ```
4. 效果 ：以后双击桌面这个文件，它就会自动打开终端并启动浏览器。想关掉时，直接 Command+Q 退出终端或点红叉关闭窗口即可。