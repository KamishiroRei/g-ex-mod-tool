# G-EX Mod Tool

v0.1.1 · Windows x64

G-EX Mod Tool 是直接对接游戏正式数据和内部作者链的开源制作工具，用于配置部件和驱动的展示内容。项目制作与外部 MOD 作者使用同一个工具、功能、源码、SKILL 和构建产物。

游戏工程的 `modtool` 是唯一正式维护位置。下载包携带同版本的完整工具源码和运行库，与工程使用同一套工具。

## 启动

Windows x64 版采用自包含目录。完整解压下载包后，双击 **G-EX Mod Tool.exe**；请保留同目录的 `_internal` 和其他附带文件。运行无需安装 Python、Qt 或虚幻引擎。

随游戏提供时，工具位于 `ExceedCavalier/modtool`。工具会优先识别随游戏的数据；需要时可选择游戏外层目录，或选择包含 `ExtentData/Parts` 的目录。

## 使用

1. 在左侧选择部件、条目或驱动，在中间查看条目预览，在右侧编辑当前对象。
2. 按需导入默认条目，或编辑条目及其关联的资源、驱动和属性；导入不会覆盖已有条目。
3. 保存配置。配置写入实际游戏数据目录下的 `UI/Hangar/inspector.json`。

未设置的属性使用游戏数据中的实际值；属性列表为空时不显示属性。手动填写的数值只改变显示，不改变伤害等游戏数值。

正式 JSON 或部件定义发生变化时，工具会按文件事件刷新，保留未保存的修改；同一字段发生冲突时，会在相应字段附近提示。外置样式 `gex_mod_tool/editor.qss` 可热修改。

## 使用 AI 制作

发布内容包含 `AGENTS.md`、`.agents/skills/g-ex-mod-authoring/SKILL.md`、正式 Schema 和必要作者源。可让 AI 先读取 `modtool/AGENTS.md`，再按任务修改直接相关的 Lua 和 JSON；没有专用工具也可使用这些资料。资料不依赖本机私有路径或特定 AI 服务。

## 从源码构建

Windows x64 构建依赖见 `requirements-build.txt`。在源码目录运行：

```text
python build_windows.py --game-root "ExceedCavalier 根目录"
```

工具与工程相关源码同步维护。Python 源码或 Qt 基础能力发生变化时，需要正常构建；文件刷新和样式热修改不等于整个程序自动热重载。

## 许可

工具源码采用 MIT 许可，详见 [LICENSE](LICENSE)；运行库许可见 [third-party-notices](third-party-notices/)。
