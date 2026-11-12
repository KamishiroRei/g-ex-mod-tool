# 现役脚本合同

这是对应工具源码版本的维护入口。字段完整结构以 `toolRoot/schema/inspector.schema.json` 及游戏实际消费者为准。

## 展示配置

`UI/Hangar/inspector.json` 的 Schema 是 `g-ex.mod.inspector.v1`。

- `parts[partDefinitionId].entries[]`：`id` 为稳定条目身份，`title`/`description` 为可选展示覆盖，`resources[]` 绑定真实 CostTag，`drives[]` 绑定真实公开驱动 DefinitionId。
- `drives[driveDefinitionId]`：驱动 `title`/`description` 与 `attributes` 的展示覆盖。
- 属性行：`title` 显示名，`source` 实际投影属性名，`value` 可选手填显示值，`unit` 单位，`group` 为 `attack` 或 `regular`，`hidden` 隐藏该属性。
- `attributes` 缺省跟随真实自动属性，`[]` 明确不显示属性。保存时不把两者合并；数值 `0` 与布尔值 `false` 也不是字段缺省。
- 显式条目后，未被其消费的真实资源/公开驱动仍由现役消费者自动追加。修改自动条目后生成显式覆盖；只浏览不应改变保存状态。自定义顺序需要保存所涉及的条目身份。

## 真实属性与层级

`ExtentData/Parts` 根对象以 `id` 识别；名称/说明在 `part.partInfo`，驱动在 `part.drive`。按真实资源请求、共享/本地资源域和驱动引用追溯归属。隐藏射击阶段可以提供真实属性来源，不成为公开下级行。

自动攻击显示使用有用途的基础威力、DP伤害、射程、爆炸范围、射速等。常用显示映射：基础威力/单枚基础威力→威力，DP伤害→冲击力，最大飞行距离→射程，爆炸半径→范围。不能仅凭驱动名拼接某武器的数值；来源不明确时保留自动/缺省状态。

源码工程中，当前相交责任层：

- `Source/ExceedCavalier/Private/Widget/Menu/FrontendHangarProjection.cpp`：原生实际配置及规则的显示投影。
- `UI/Hangar/assembly-abilities.lua`：条目/资源/驱动归属与显式配置消费。
- `UI/Hangar/assembly.lua`：现役详情与交互。
- `Source/ExceedCavalier/Private/Widget/Menu/LiveUI/FLiveUIScript.cpp`：通用 Lua/JSON 模块加载。
- `Source/ExceedCavalier/ExceedCavalier.Build.cs`：游戏发布收集。

发布游戏可能不携带 C++ 源码；普通展示修改只需正式 JSON/Lua，不因此要求安装 UE 或取得开发环境。接口扩展回到对应版本源码处理，不在发布端猜测新字段。

## 工具作者源

`gex_mod_tool/model.py` 负责文件、配置与保存；`catalog.py` 负责真实目录、自动条目及属性适配；`qt_app.py`/相关 Qt 模块负责同一选择下的层级、预览和当前对象编辑；`editor.qss` 为外置样式。若当前源码文件拆分变化，沿实际导入更新本入口，不另存一份过期实现。

同一工具从源码构建使用 `build_windows.py` 和 `requirements-build.txt`，直接运行使用同版本随包 EXE。发布收集包含运行库、完整工具作者源、Schema/示例、本技能与使用说明，不包含构建环境、凭据、宿主私有 SKILL 或临时日志。

当前 Windows Qt 构建使用系统 ICU C 接口。`windows_runtime.py` 与构建运行时钩子在 Qt 导入前选择系统库；构建脚本的 DLL 搜索路径仅含对应 Qt/Python 和 Windows 目录。不要从宿主 PATH 中的其他应用复制同名 `icuuc.dll`，其版本化接口可能与 Qt 所需系统接口不同。更新运行库时整体替换工具私有 `_internal`，避免旧 DLL 在覆盖升级后继续遮蔽系统或新库；源码、配置和未保存工作不属于此私有运行库。
