# G-EX Mod Tool

用于配置游戏中部件和驱动的展示内容。

## 启动

Windows x64 用户可解压 `G-EX-Mod-Tool-Windows-x64.zip`，双击 **G-EX Mod Tool.exe**。工具随游戏提供时，也可从 `ExceedCavalier/ModTools` 目录启动。

这是独立程序，无需安装 Python、虚幻引擎或其他运行依赖。工具会优先识别随游戏的数据；如需手动选择，可选择游戏外层目录，或选择包含 `ExtentData/Parts` 的目录。

## 使用

1. 选择部件。可点击 **导入默认条目**，根据部件定义生成尚未配置的资源和公开驱动条目，已有条目不会被覆盖。
2. 编辑展示条目及其关联的资源和驱动，按需调整属性的显示顺序、区块、隐藏状态、标签、单位和显示内容。
3. 点击 **保存**。配置写入实际游戏数据目录下的 `UI/Hangar/inspector.json`。

未设置的属性使用游戏数据中的实际值；属性列表为空时不显示属性。手动填写的数值只改变显示，不改变伤害等游戏数值。

## 维护者

Windows x64 构建依赖见 `requirements-build.txt`。在源码目录运行：

```text
python build_windows.py --game-root "ExceedCavalier 根目录"
```

游戏内的工具路径为 `ExceedCavalier/ModTools/G-EX Mod Tool.exe`。
