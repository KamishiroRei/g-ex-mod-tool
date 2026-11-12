# v0.1.0 Windows 首发版

G-EX Mod Tool 直接对接游戏正式数据和内部作者链，项目制作与外部 MOD 作者使用同一个开源工具、功能、源码、SKILL 和构建产物。游戏工程的 `modtool` 是唯一正式维护位置；ZIP 包含同版本完整工具源码和运行库。

Windows x64 自包含目录包含 **G-EX Mod Tool.exe** 和私有运行库 `_internal`。完整解压后即可运行，无需安装 Python、Qt 或虚幻引擎。

- 左侧选择部件、条目和驱动，中间预览条目，右侧编辑当前对象。
- 导入未配置的默认条目，编辑资源、驱动及属性展示，并保存配置。
- 手动填写的数值只影响显示，不改变伤害等游戏数值。
- 正式 JSON 和部件定义按文件事件刷新，保留未保存修改，并就近提示字段冲突。外置样式可热修改。
- 附带 AI 作者入口、相关 SKILL、正式 Schema 和必要作者源，可供 AI 直接维护相关 Lua 和 JSON。

随游戏提供的路径为 `ExceedCavalier/modtool`。

工具源码采用 MIT 许可，详见 `LICENSE`；运行库许可见 `third-party-notices`。
