---
name: notebooklm
description: 与 Google NotebookLM 交互。支持上传文档、生成摘要、创建播客音频、管理笔记本、与笔记本对话。当用户提到 NotebookLM、生成播客、文档摘要、笔记本管理时使用此 Skill。 (user)
allowed-tools: Read, Bash, Write, Glob
---

# NotebookLM Skill - Claude Code 操作协议

## 🎯 智能流程判断（首先阅读）

### 何时需要 `list`？
```
❌ 用户已经明确说了笔记本名称 → 不需要 list，直接操作
❌ 当前会话已经执行过 list → 不需要重复
✅ 用户说"笔记本"但没指定名称 → 需要 list
✅ 第一次操作，不确定有哪些笔记本 → 需要 list
```

### 快速路径（优先使用）
```
用户: "问问 xgent-LLM 笔记本关于 xxx"
→ 直接执行: nlm --headless smart-chat --notebook "03.xgent-LLM" --question "xxx"
  （不需要先 list）

用户: "查一下笔记本里有什么"
→ 需要先 list，因为不知道用户指哪个笔记本

用户: "用 NotebookLM 获取指导"
→ 根据上下文判断笔记本，如果不确定则 list
```

### 常用笔记本速查
| 关键词 | 笔记本名称 |
|--------|-----------|
| xgent、LLM、Agent | 03.xgent-LLM |
| 自由能、MACE、LAMMPS | 00.two-step free energy... |
| 月球、Fe | 01.月球土壤中 Fe的歧化反应 |
| 地幔、各向异性 | 02.下地幔各向异性NC论文回稿 |

---

## ⚠️ 强制规则 (MANDATORY)

### 规则 1: 使用 nlm 命令
```
🚫 禁止: 手动描述操作步骤让用户执行
🚫 禁止: 假装已完成操作但未调用命令
✅ 必须: 使用 nlm 命令行工具
✅ 必须: 检查命令输出确认操作结果
✅ 必须: 使用 --headless 参数进行无头操作
```

### 规则 2: CLI 命令格式
```bash
# Mac 系统 - 使用 CDP 模式（多窗口安全）
~/.claude/skills/notebooklm/nlm-cdp.sh --headless <命令> [参数]

# Linux 系统 - 需要先激活 conda 环境
source ~/.selfconda && nlm --headless <命令> [参数]
```

**为什么用 nlm-cdp.sh？**
- 自动连接到已运行的 Chrome（通过 CDP）
- 多个 Claude Code 窗口可以同时调用，不会冲突
- 如果 Chrome 没运行，会自动启动

### 规则 3: 数据同步
```
✅ 所有数据通过 Google 账号云同步
✅ 用户在浏览器刷新页面后可以看到 nlm 的操作记录
✅ Chat、Sources、Notes 都会同步
```

### 规则 4: 对话历史理解（重要！）
```
📌 NotebookLM 对话历史 = 服务器端保存，永久存在
📌 NotebookLM AI 记忆 = 每次对话无状态，不会"记住"之前的对话

✅ 对话记录保存在 NotebookLM 服务器（可用 chat-history 命令查看）
✅ 不同 Claude Code 窗口、不同设备，只要同一 Google 账号都能看到相同记录
❌ NotebookLM AI 不会主动"回忆"之前的对话内容
❌ 问它"我们之前聊了什么"会得到"我无法访问历史记录"的回答

查看对话历史的正确方式:
  nlm --headless chat-history --notebook "笔记本名"
```

### 规则 5: 多窗口并发
```
✅ 多个 Claude Code 窗口可以使用 nlm（自动排队）
✅ 第二个调用会等待第一个完成后再执行
⚠️ 排队等待时会显示: "⏳ 另一个 nlm 实例正在运行，等待中..."
```

### 规则 6: 禁止危险操作（重要！）
```
🚫 绝对禁止: pkill -f "Google Chrome"
🚫 绝对禁止: killall Chrome
🚫 绝对禁止: 任何杀死 Chrome 进程的命令

原因: Mac 上使用 CDP 模式，Chrome 需要保持运行
      杀死 Chrome 会导致所有 nlm 操作失败，甚至导致 Claude Code 崩溃

如果 nlm 连接失败，正确做法:
  1. 清理残留文件: rm -f ~/.claude/skills/notebooklm/chrome_profile/Singleton*
  2. 重新运行 nlm 命令，它会自动重启 CDP Chrome
```

---

## 🖥️ NotebookLM 三面板结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          NotebookLM 界面                                 │
├─────────────────┬──────────────────────────────┬────────────────────────┤
│   SOURCE 面板   │         对话面板              │      STUDIO 面板       │
│    (左侧)       │          (中间)               │        (右侧)          │
├─────────────────┼──────────────────────────────┼────────────────────────┤
│ • 来源类型选择  │ • 与已导入源对话              │ • 保存笔记              │
│   - Web         │ • 聊天输入框                  │ • 生成音频/播客         │
│   - Google Drive│ • 查看聊天历史                │ • 查看/编辑笔记         │
│   - YouTube     │ • 每条回复可:                 │ • 导出内容              │
│   - Link        │   - 保存为笔记                │                        │
│                 │   - 复制                      │                        │
│ • 研究模式选择  │   - 点赞/点踩                 │                        │
│   - Fast Research│                              │                        │
│   - Deep Research│                              │                        │
│                 │                               │                        │
│ • 搜索新来源    │                               │                        │
│ • 查看搜索结果  │                               │                        │
│ • 导入/移除结果 │                               │                        │
│ • 已导入源列表  │                               │                        │
└─────────────────┴──────────────────────────────┴────────────────────────┘
```

---

## 📋 可用命令完整列表

### 基础管理命令
| 命令 | 用途 | 必需参数 | 可选参数 |
|------|------|----------|----------|
| `list` | 列出所有笔记本 | 无 | |
| `create` | 创建新笔记本 | `--name` | |
| `delete` | 删除笔记本 | `--notebook` | |
| `login` | 仅登录账号 | 无 | |

### SOURCE 面板命令
| 命令 | 用途 | 必需参数 | 可选参数 |
|------|------|----------|----------|
| `sources` | 列出已导入的源 | `--notebook` | |
| `upload` | 上传本地文档 | `--file` | `--notebook` |
| `delete-source` | 删除已导入的源 | `--notebook`, `--source` | |
| `search-sources` | **搜索新来源（完整流程）** | `--notebook`, `--query` | `--mode`, `--source-type` |
| `view-results` | 点击查看按钮 | `--notebook` | |
| `import-result` | 导入搜索结果 | `--notebook`, `--title` | |
| `remove-result` | 移除搜索结果 | `--notebook`, `--title` | |
| `clear-search` | **清除所有临时搜索结果** | `--notebook` | |
| `detect-search-state` | **检测搜索状态** | `--notebook` | |
| `inspect-source` | 检查源详情 | `--notebook`, `--source` | |
| `import-source` | 导入临时源（旧命令） | `--notebook`, `--source` | |
| `detect-mode` | 检测UI模式 | `--notebook` | |

### 对话面板命令
| 命令 | 用途 | 必需参数 | 可选参数 |
|------|------|----------|----------|
| `chat` | 与笔记本对话 | `--notebook`, `--question` | |
| `smart-chat` | **智能聊天（推荐）** | `--notebook`, `--question` | `--save-note`, `--max-wait` |
| `chat-history` | **查看对话历史记录** | `--notebook` | |

### STUDIO 面板命令
| 命令 | 用途 | 必需参数 | 可选参数 |
|------|------|----------|----------|
| `save-note` | 保存内容到笔记 | `--notebook`, `--content` | `--title` |
| `audio` | 生成播客音频 | `--notebook` | `--output` |

### 全局参数
- `--headless`: 无头模式（不显示浏览器窗口）
- `--browser {chrome,safari,webkit,firefox}`: 选择浏览器引擎

### smart-chat 专用参数
- `--max-wait <秒>`: 最大等待时间，默认 480 秒（8分钟）
- `--save-note`: 自动将回答保存为笔记

---

## ⏱️ 超时配置（重要！）

### 超时层级总览

```
┌─────────────────────────────────────────────────────────────────┐
│                     超时层级（从外到内）                          │
├─────────────────────────────────────────────────────────────────┤
│  Claude Code Bash timeout     默认 120秒    ⚠️ 需要手动增加！    │
│  ├── nlm --max-wait           默认 480秒    脚本等待回复时间      │
│  │   ├── 阶段1: 等待生成开始   最多 60秒                         │
│  │   ├── 阶段2: 文本稳定检测   最多 max_wait 秒                  │
│  │   └── 阶段3: 额外确认       5秒                               │
│  └── Playwright 操作超时      120秒        单个页面操作          │
└─────────────────────────────────────────────────────────────────┘
```

### ⚠️ Claude Code 调用必须设置 timeout！

**问题**: Claude Code Bash 工具默认 timeout 只有 **120秒 (2分钟)**，而 nlm 内部等待时间是 **480秒 (8分钟)**。如果不设置，Bash 会提前终止导致回复被截断！

**解决方案**: 调用 nlm 时必须设置 Bash timeout 参数：

```
推荐 timeout 值:
- 简单问题: 300000  (5分钟)
- 普通问题: 600000  (10分钟) ← 推荐默认值
- 复杂问题: 900000  (15分钟)
```

### 回复完整性保证机制

`smart-chat` 使用**文本稳定性检测**确保获取完整回复：

| 阶段 | 时间 | 检测方式 |
|------|------|----------|
| 1. 等待生成开始 | 最多60秒 | 检测"停止生成"按钮出现 |
| 2. 等待生成完成 | 最多 max_wait 秒 | **连续5秒文本不变 = 完成** |
| 3. 额外确认 | 5秒 | 再次检查文本是否还在变化 |

### 参数配置表

| 层级 | 参数 | 默认值 | 建议值 | 说明 |
|------|------|--------|--------|------|
| Claude Code | Bash timeout | 120秒 | **600秒** | 必须手动设置！ |
| nlm 脚本 | `--max-wait` | 480秒 | 480-600秒 | 等待回复生成 |
| Playwright | 操作超时 | 120秒 | - | 单个页面操作 |

### 使用示例

```bash
# Mac 系统
~/.claude/skills/notebooklm/nlm-cdp.sh --headless smart-chat \
    --notebook "笔记本名" \
    --question "请详细解释..." \
    --max-wait 600

# Adam 系统（通过 ~/bin/nlm wrapper）
~/bin/nlm --headless smart-chat \
    --notebook "笔记本名" \
    --question "请详细解释..." \
    --max-wait 600
```

### Claude Code 调用模板

当 Claude Code 调用 nlm 时，应使用以下格式：
```
工具: Bash
timeout: 600000  # 10分钟，必须设置！
command: nlm --headless smart-chat --notebook "xxx" --question "xxx"
```

---

## 🔄 搜索新来源完整工作流程

### ⚠️ 搜索状态机

```
搜索有两种状态:
┌─────────────────────────────────────────────────────────┐
│  READY                                                   │
│  - 搜索框可用                                            │
│  - 可以输入新的搜索查询                                   │
│  - "查看"按钮不可见                                       │
└────────────────────┬────────────────────────────────────┘
                     │ 执行搜索
                     ▼
┌─────────────────────────────────────────────────────────┐
│  PENDING_RESULTS                                         │
│  - 有待处理的搜索结果                                     │
│  - "查看"按钮可见                                         │
│  - "删除"按钮可见（在查看按钮附近）                        │
│  - 搜索框不可用（必须先处理结果）                          │
└────────────────────┬────────────────────────────────────┘
                     │ 点击"删除"并确认
                     │ 或点击"查看" → 导入 → 关闭
                     ▼
┌─────────────────────────────────────────────────────────┐
│  READY (返回初始状态)                                    │
└─────────────────────────────────────────────────────────┘
```

### 检测当前搜索状态
```bash
nlm --headless detect-search-state --notebook "笔记本名"
# 返回: READY / PENDING_RESULTS / UNKNOWN
```

### ⚠️ 重要规则
```
搜索完成后必须导入或清除所有结果，否则无法进行新的搜索！
search-sources 命令会自动清除待处理的结果，但如果手动操作需要注意状态。
```

### 步骤 1: 执行搜索
```bash
nlm --headless search-sources \
    --notebook "笔记本名" \
    --query "搜索词" \
    --mode fast \          # fast(快速) 或 deep(深度研究)
    --source-type web      # web/drive/youtube/link
```

### 步骤 2: 查看搜索结果（搜索完成后自动执行）
```bash
# 如果需要手动查看
nlm --headless view-results \
    --notebook "笔记本名"
```

### 步骤 3: 导入或移除结果
```bash
# 导入想要的结果
nlm --headless import-result \
    --notebook "笔记本名" \
    --title "结果标题（部分匹配）"

# 移除不需要的结果
nlm --headless remove-result \
    --notebook "笔记本名" \
    --title "结果标题"

# 或清除所有临时结果
nlm --headless clear-search \
    --notebook "笔记本名"
```

### 步骤 4: 验证导入成功
```bash
nlm --headless sources \
    --notebook "笔记本名"
```

---

## 🔄 操作决策树

```
用户意图是什么？
│
├── 提问/获取信息 → smart-chat 命令 (推荐)
│   └── python ~/.../notebooklm.py smart-chat --notebook "名称" --question "问题"
│       └── 添加 --save-note 可自动保存回答为笔记
│
├── 搜索新来源 → search-sources 命令（完整流程）
│   ├── Web 搜索: --source-type web
│   ├── Google Drive: --source-type drive
│   ├── YouTube: --source-type youtube
│   └── 链接: --source-type link
│       └── 研究模式:
│           ├── 快速: --mode fast (默认，约30秒)
│           └── 深度: --mode deep (约2分钟)
│
├── 导入搜索结果 → import-result 命令
│   └── python ~/.../notebooklm.py import-result --notebook "名称" --title "标题"
│
├── 移除搜索结果 → remove-result 命令
│   └── python ~/.../notebooklm.py remove-result --notebook "名称" --title "标题"
│
├── 查看已有源 → sources 命令
│   └── python ~/.../notebooklm.py sources --notebook "名称"
│
├── 删除已导入的源 → delete-source 命令
│   └── python ~/.../notebooklm.py delete-source --notebook "名称" --source "源名"
│
├── 上传本地文档 → upload 命令
│   └── python ~/.../notebooklm.py upload --file "/path/file" --notebook "名称"
│
├── 保存笔记 → save-note 命令
│   └── python ~/.../notebooklm.py save-note --notebook "名称" --content "内容" --title "标题"
│
├── 生成播客 → audio 命令
│   └── python ~/.../notebooklm.py audio --notebook "名称" --output "/path/output.mp3"
│
└── 管理笔记本 → list/create/delete 命令
```

---

## 📖 常用操作示例

### 1. 智能聊天（推荐，自动处理 UI 模式切换）
```bash
nlm --headless smart-chat \
    --notebook "00.two-step free energy Thermodynamic integration & MACE & Lammps" \
    --question "请详细解释 Two-Step NeTI 方法的 W_irr 和 W_rev 计算"
```

### 2. 智能聊天并保存回答为笔记
```bash
nlm --headless smart-chat \
    --notebook "笔记本名" \
    --question "问题内容" \
    --save-note
```

### 3. 从 Web 搜索新来源（快速模式）
```bash
nlm --headless search-sources \
    --notebook "笔记本名" \
    --query "MACE machine learning potential" \
    --mode fast \
    --source-type web
```

### 4. 从 Google Drive 搜索（深度研究）
```bash
nlm --headless search-sources \
    --notebook "笔记本名" \
    --query "thermodynamic integration" \
    --mode deep \
    --source-type drive
```

### 5. 导入搜索到的结果
```bash
nlm --headless import-result \
    --notebook "笔记本名" \
    --title "Reversible Scaling"  # 部分匹配即可
```

### 6. 清除所有临时搜索结果
```bash
nlm --headless clear-search \
    --notebook "笔记本名"
```

### 7. 列出所有已导入的源
```bash
nlm --headless sources \
    --notebook "00.two-step free energy Thermodynamic integration & MACE & Lammps"
```

### 8. 删除已导入的源
```bash
nlm --headless delete-source \
    --notebook "笔记本名" \
    --source "源名称"
```

### 9. 上传本地文档
```bash
nlm --headless upload \
    --file "/tmp/document.pdf" \
    --notebook "笔记本名"
```

### 10. 保存研究笔记
```bash
nlm --headless save-note \
    --notebook "笔记本名" \
    --title "fscale vs scale 总结" \
    --content "Step 1 和 Step 2 都使用 fscale..."
```

### 11. 生成播客音频
```bash
nlm --headless audio \
    --notebook "笔记本名" \
    --output "/tmp/podcast.mp3"
```

### 12. 列出所有笔记本
```bash
nlm --headless list
```

---

## 🐍 Python API（高级用法）

```python
from notebooklm_cli import NotebookLMAutomation

# 创建实例
nlm = NotebookLMAutomation(headless=False)
nlm.start()

# === SOURCE 面板操作 ===

# 检测搜索状态（READY / PENDING_RESULTS / UNKNOWN）
state = nlm.detect_search_state()

# 选择来源类型
nlm.select_source_type("web")  # web/drive/youtube/link

# 选择研究模式
nlm.select_research_mode("fast")  # fast/deep

# 搜索新来源（完整流程，自动清除待处理结果）
results = nlm.search_sources("笔记本名", "搜索词", mode="fast", source_type="web", auto_clear=True)

# 点击查看按钮
nlm.click_view_results()

# 获取带操作信息的搜索结果
results = nlm.get_search_results_with_actions()

# 导入搜索结果
nlm.import_search_result("结果标题")

# 移除搜索结果
nlm.remove_search_result("结果标题")

# 清除所有临时结果
nlm.clear_temp_sources()

# 列出已导入的源
sources = nlm.list_sources("笔记本名")

# 删除已导入的源
nlm.delete_source("笔记本名", "源名称")

# === 对话面板操作 ===

# 智能聊天（自动处理模式切换）
response = nlm.smart_chat("笔记本名", "问题")

# 将回复保存为笔记
nlm.save_response_as_note()

# 检测当前 UI 模式
mode = nlm.detect_mode()  # 'chat' 或 'source_search'

# === STUDIO 面板操作 ===

# 保存笔记
nlm.save_note("笔记本名", "笔记内容", "笔记标题")

# 生成播客
nlm.generate_audio("笔记本名", "/tmp/output.mp3")

# 完成后关闭
nlm.close()
```

---

## 🔍 NotebookLM UI 模式说明

| 模式 | 位置 | 用途 | 识别特征 |
|------|------|------|----------|
| `chat` | 对话面板 | 与已导入源对话 | placeholder 包含 "开始输入" |
| `source_search` | SOURCE面板 | 搜索添加新源 | placeholder 包含 "发现来源" |

**研究模式（搜索时）:**
- `fast` (快速研究): 约30秒，基础搜索
- `deep` (深度研究): 约2分钟，更全面

---

## ✅ 验证清单

执行 NLM 操作后，必须检查:

1. **检查输出**: 脚本是否输出成功信息
2. **检查截图**: 如有 `debug_*.png` 生成，说明可能有问题
3. **验证结果**: 对于重要操作，再次查询确认
   ```bash
   # 搜索并导入后验证
   nlm --headless sources --notebook "笔记本名"
   ```

---

## ❌ 禁止事项

1. **不要猜测笔记本名称** - 使用 `list` 命令获取准确名称
2. **不要跳过验证** - 重要操作后必须验证结果
3. **不要在无头模式下调试** - 问题排查时使用可见模式
4. **不要忽略错误输出** - 仔细检查脚本返回的错误信息
5. **不要假设操作成功** - 没有明确成功信息就视为失败
6. **搜索后不要忘记处理结果** - 必须导入或移除，否则无法新搜索

---

## 📁 安装与文件位置

### 安装方式
```bash
# 从 GitHub 安装
pip install git+https://github.com/Superionichuan/notebooklm-skill.git

# 安装浏览器
playwright install chromium
```

### 文件位置
```
命令位置: nlm (pip 安装后全局可用)
Python 包: notebooklm_cli

~/.claude/skills/notebooklm/
├── SKILL.md                    # 本文档
├── chrome_profile/             # 隔离的 Chrome Profile（已登录）
├── webkit_profile/             # Safari/WebKit Profile
└── firefox_profile/            # Firefox Profile
```

---

## 🔧 故障排除

### 问题: 超时或找不到元素
```bash
# 使用非无头模式调试
nlm --headless smart-chat \
    --notebook "笔记本名" --question "测试"
```

### 问题: Chrome 冲突
```bash
# 使用 Safari/WebKit 引擎（不会和 Chrome 冲突）
nlm --headless smart-chat \
    --notebook "笔记本名" --question "测试" --browser safari
```

### 问题: 需要重新登录
```bash
nlm --headless login
```

### 问题: 搜索结果没有清除，无法新搜索
```bash
nlm --headless clear-search \
    --notebook "笔记本名"
```

---

## 📋 重要笔记本

| 名称 | ID | 内容 |
|------|-----|------|
| 00.two-step free energy Thermodynamic integration & MACE & Lammps | e91d4a25-773a-4e31-b248-09824a7a0e56 | Two-Step NeTI 自由能计算、LAMMPS-MACE 集成、de Koning 论文 |

---

## 🤖 Claude Code 操作规范

当用户请求与 NotebookLM 交互时，Claude Code **必须**:

1. **识别意图** → 使用上方决策树
2. **构建命令** → 使用上方命令模板
3. **执行脚本** → 通过 Bash 工具调用
4. **检查输出** → 验证成功/失败
5. **报告结果** → 告知用户操作结果

**绝对不要**: 描述步骤而不执行、假装完成而没调用脚本、跳过验证步骤。
