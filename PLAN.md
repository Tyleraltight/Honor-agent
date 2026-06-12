# Hermes Spotlight 继续开发计划

## 项目状态总结

根据 `agents.md` 和代码分析，项目有两个核心问题需要解决：

### 问题 1：区分 Copilot 键和左 Windows 键
**现状**：
- Copilot 键和左 Windows 键的扫描码都是 `SC15B`，虚拟键码都是 `VK5B`
- 当前 AHK 脚本使用 `VK07`，但 agents.md 说这是错误的键码
- 已尝试 7 种方案均失败

**可能的解决方案**：
1. **使用 HID 设备级别的区分** - 研究荣耀 MagicBook 的 Copilot 键是否有特殊的 HID 信号
2. **使用 `RegisterRawInputDevices` + `WM_INPUT`** - 需要正确的 AHK v2 语法
3. **使用外部程序（C#/Rust）编写键盘钩子** - 绕过 AHK 的限制

### 问题 2：搜索框流式输出不工作
**现状**：
- API 调用正常（历史记录有回复内容）
- 前端只显示"你:"，看不到 AI 回复
- Python 端使用 `evaluate_js` 推送 token，但可能从后台线程调用时被丢弃

**可能的解决方案**：
1. **使用 WebSocket 替代 JS 桥通信** - 避免线程问题
2. **使用轮询模式** - 前端定期查询后端获取新 token
3. **检查 pywebview 版本兼容性** - 确认 `evaluate_js` 的线程安全问题

---

## 执行计划

### 阶段 1：修复流式输出问题（优先级高）✅ 已完成

**目标**：让搜索框能正常显示 AI 回复

**最终方案**：
完全重构，使用 pywebview JS 桥 + 队列轮询。核心思路：
- 后端在后台线程执行 API 调用，token 放入线程安全队列
- 前端通过 `pywebview.api.poll()` 每 50ms 轮询获取事件
- 不依赖 `evaluate_js`，不依赖 HTTP 代理，不依赖 CORS

**后端** (`hermes_spotlight.py`)：
- `SpotlightAPI.chat(msg)` — 接收消息，启动后台线程
- `SpotlightAPI.poll()` — 返回队列中的所有事件（JSON 数组）
- 事件格式：`{t:"tok", v:"text"}`, `{t:"tool", v:"name"}`, `{t:"done"}`, `{t:"err", v:"msg"}`
- 递归处理工具调用

**前端** (`hermes_spotlight.html`)：
- 轮询 `pywebview.api.poll()`，解析事件并更新 DOM
- 闪烁光标动画表示正在输出
- 简洁可靠

**测试状态**：待测试

### 阶段 2：解决 Copilot 键区分问题（优先级中）

**目标**：让 Copilot 键打开搜索框，左 Win 键正常打开开始菜单

**步骤**：
1. **研究 HID 设备信息**
   - 使用 `hid` 工具或 `USBDeview` 查看 Copilot 键的 HID 描述符
   - 确认是否有独特的 Vendor ID / Product ID

2. **尝试 `RegisterRawInputDevices` 方案**
   - 使用 AHK v2 的 `DllCall` 调用 Windows API
   - 注册原始输入设备，区分不同的键盘设备

3. **备选方案：使用 C# 编写键盘钩子**
   - 如果 AHK 无法解决，用 C# 编写一个独立的键盘钩子程序
   - 编译为 `.exe`，由 AHK 脚本调用

### 阶段 3：优化和测试

**目标**：确保所有功能稳定运行

**步骤**：
1. **整合测试**
   - 测试 Copilot 键触发搜索框
   - 测试流式输出
   - 测试工具调用

2. **优化用户体验**
   - 添加加载动画
   - 优化错误处理
   - 确保对话历史正常保存

3. **部署和自启动**
   - 更新开机自启动脚本
   - 确保所有依赖项正确配置

---

## 需要的资源

1. **pywebview 文档** - 确认 `evaluate_js` 的线程安全行为
2. **AHK v2 文档** - 研究 `RegisterRawInputDevices` 的正确用法
3. **HID 工具** - 如 `hid`、`USBDeview`，用于分析 Copilot 键的 HID 信号
4. **C# 开发环境** - 如果需要编写外部键盘钩子程序

---

## 预期成果

1. **流式输出正常** - 搜索框能实时显示 AI 回复
2. **Copilot 键正常工作** - 只响应 Copilot 键，不影响左 Win 键
3. **用户体验流畅** - 搜索框稳定、快速、易用
