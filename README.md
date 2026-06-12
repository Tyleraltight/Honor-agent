# Honor Agent

荣耀 MagicBook Pro 16 2026 的本地 AI 搜索框。

## 功能

- 按 **F11** 打开/最小化搜索框
- 支持 AI 对话（Xiaomi mimo-v2.5 模型）
- 支持文件操作、命令执行等工具调用
- 对话历史自动保存

## 使用方法

1. 运行 `hermes_spotlight.bat` 启动搜索框
2. 运行 `copilot-to-hermes.ahk` 启动快捷键支持
3. 按 **F11** 打开搜索框
4. 输入消息并按 **Enter** 发送
5. 点击 **×** 按钮关闭搜索框

## 快捷键

| 快捷键 | 功能 |
|--------|------|
| F11 | 打开/最小化搜索框 |
| Enter | 发送消息 |
| /new | 开启新对话 |

## 配置

API 配置在 `E:\hermes\.env` 文件中。

## 依赖

- Python 3.12+
- pywebview
- requests
- AutoHotkey v2
