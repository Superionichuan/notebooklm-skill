# NotebookLM 多实例快速指南

## 自动实例分配（推荐）

系统根据笔记本名称自动分配独立实例，无需手动指定 `--instance`：

```bash
# Mac 本地 - 直接使用，自动分配实例
nlm --headless smart-chat --notebook "01.月球土壤中 Fe的歧化反应" --question "你的问题"
# 输出: 🔷 自动实例: nb_01 (笔记本: 01.月球土壤中 Fe的歧化反应...)

# 禁用自动实例
nlm --headless --no-auto-instance smart-chat --notebook "..." --question "问题"
```

## 已配置实例

| 实例 | 绑定笔记本 | 用途 |
|------|-----------|------|
| `nb_01` | 01.月球土壤中 Fe的歧化反应 | 月球研究 |
| `nb_02` | 02.下地幔各向异性NC论文回稿 | NC论文 |
| `nb_03` | 00.two-step free energy... | 自由能计算 |

## 常用命令

### Mac 本地

```bash
# 聊天（自动分配实例）
nlm --headless smart-chat --notebook "01.月球土壤中 Fe的歧化反应" --question "你的问题"

# 查看聊天历史
nlm --headless chat-history --notebook "01.月球土壤中 Fe的歧化反应" --limit 10

# 搜索新来源
nlm --headless search-sources --notebook "01.月球土壤中 Fe的歧化反应" --query "关键词"

# 列出笔记本
nlm --headless list
```

### Adam 集群

⚠️ **首次使用需要手动登录 Google 账号**（见下方说明）

```bash
# 聊天
source ~/.selfconda && nlm --headless smart-chat \
    --notebook "01.月球土壤中 Fe的歧化反应" --question "你的问题"

# 搜索新来源
source ~/.selfconda && nlm --headless search-sources \
    --notebook "01.月球土壤中 Fe的歧化反应" --query "关键词" --mode fast
```

## Adam 首次登录（一次性）

由于 Google 安全机制，在新服务器上首次使用需要手动登录：

```bash
# 步骤 1: 本地终端建立 SSH 隧道
ssh -L 9222:localhost:9222 adaml

# 步骤 2: 在 Adam 上启动 Chrome（另一个终端）
source ~/.selfconda
chromium --headless=new --remote-debugging-port=9222 \
  --user-data-dir=~/.claude/skills/notebooklm/chrome_profile \
  --no-sandbox https://notebooklm.google.com

# 步骤 3: 本地浏览器打开 chrome://inspect
#   - Configure 添加 localhost:9222
#   - 找到 NotebookLM 页面，点击 inspect
#   - 在 DevTools 中完成 Google 登录

# 步骤 4: 登录完成后 Ctrl+C 关闭 Chrome
```

## 并行运行

```bash
# Mac: 同时运行两个笔记本（自动分配不同实例）
nlm --headless smart-chat --notebook "01.月球" --question "问题1" &
nlm --headless smart-chat --notebook "02.NC论文" --question "问题2" &
wait
```

## 常用操作速查

| 操作 | 命令 |
|------|------|
| 列出笔记本 | `nlm --headless list` |
| 聊天 | `nlm --headless smart-chat --notebook "名称" --question "问题"` |
| 聊天历史 | `nlm --headless chat-history --notebook "名称"` |
| 列出源 | `nlm --headless sources --notebook "名称"` |
| 搜索源 | `nlm --headless search-sources --notebook "名称" --query "关键词"` |
| 导入结果 | `nlm --headless import-result --notebook "名称" --title "标题"` |
| 清除搜索 | `nlm --headless clear-search --notebook "名称"` |
| 保存笔记 | `nlm --headless save-note --notebook "名称" --content "内容"` |

## 文件位置

```
~/.claude/skills/notebooklm/
├── SKILL.md              # 完整使用文档
├── QUICK_START.md        # 本文件
├── instances.yaml        # 实例配置
├── chrome_profile/       # 默认 profile（共享）
└── profiles/             # 多实例 profiles（自动创建）
    ├── nb_01/chrome/     # 笔记本 01 的独立 Profile
    ├── nb_02/chrome/     # 笔记本 02 的独立 Profile
    └── nb_03/chrome/     # 笔记本 03 的独立 Profile
```
