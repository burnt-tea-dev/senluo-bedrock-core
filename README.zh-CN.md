# Senluo Bedrock Core — 森罗基岩版共享核心

**简体中文** · [繁體中文](README.zh-TW.md) · [English](README.md)

森罗基岩版 addon 家族的**非官方共享 SDK 与本地整合工具**。

Core 是**构建阶段 SDK**：其代码会复制到各个使用它的包里；它不会额外增加行为包、全局 tick 循环或新的存档数据所有者。

```text
Core SDK ──→ 烟火（事件路由和公开食物元数据）
        └──→ Cookery 原始宿主（通过烟火已审查的适配器）
本地安装器＋自行获取的 Cookery 原包 ──→ 本地适配包
```

## 当前组装与依赖

当前安装使用 **Tavern 0.6.194、Grilling 2.8.206、世界名酒（World Liquor）0.1.180**。工具包 **0.15.0** 保留当前 G206 和 Immersive Eating 适配器：本地 Cookery **1.6.20008**、Immersive Eating **1.1.20002**；保留欢迎聊天消息与原生配方顺序，同时避免重复完整排序配方。

请从[当前家族安装流程](docs/FAMILY-ASSEMBLY.md#current-g206-installation)开始。保留行为包／模块 UUID、物品 ID 和存档数据归属；升级前备份**已停止运行**的世界，并先在副本中测试。

## 技术文档

- [SDK 合约和来源责任](docs/SDK.md)
- [Cookery 本地安装](docs/COOKERY.md)
- [本地家族组装工具](docs/FAMILY-ASSEMBLY.md)
- [自有移植适配器](docs/PORT-ADAPTERS.md)
- [验证范围与限制](docs/VALIDATION.md)

公开与服务器整合使用相同的烟火标准玩家组合器及 Core 指南工具。公开对照范围包含三个自有移植及必要的接线代码；无关第三方 addon 须单独下载。原生或存档证据**不代表通过了画面客户端验收**。正式发布资源从 [Releases](https://github.com/burnt-tea-dev/senluo-bedrock-core/releases) 获取。

本仓库不分发作者原始资源包、完整作者模块、玩家世界、私有整合历史、服务器配置或凭据。请从[作者项目](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial)自行获取 Cookery。本非官方项目与 Mojang 和原作者无从属关系。

## 许可证及历史兼容

SDK 与新编写的工具采用 [BSD-3-Clause](LICENSE)。独立的烟火 addon 提供的玩法辅助代码保留该项目的声明；本地适配的作者内容继续遵守原有许可证与署名。

较早版本的 descriptor 及其验证记录作为历史保留。复现旧版 Cookery 解码输出需使用当时的工具包源码；0.12 helper 会主动拒绝那些不可更改的历史 helper pin。

可选 TACZ 路线目前可本地构建 **1.0.20005**，具备资源堆栈 PBR 功能，并保留 24 个枪械玩家属性以及烟火的 4 个属性。使用 [TACZ20005 配方](adapters/owned-t194-g206-w180-tacz-pbr.json)，但须分别完成全家族、已有存档、回滚和客户端验证。工具包 0.12 的发布版和 TACZ20004 配方均属于历史产物。

Cookery 配方注册目前**每 tick 最多处理 4 条传入消息**，目标执行时间 **1 毫秒**。保留原始注册验证、FIFO 替换顺序、全部配方和欢迎消息；导出的同步注册函数保持不变。请使用[当前 Cookery descriptor](adapters/cookery-1.6.4-grilling-2.8.206-recipe-ingress.json)和[可选 TACZ 家族 descriptor](adapters/owned-t194-g206-w180-recipe-ingress-tacz.json)。安装器检查与原生／客户端验收是不同的事项。

源码和家族构建器默认使用当前 G206／Cookery20008 组装；历史 G201／G203 和旧 Cookery 配方须通过显式 `--descriptor` 参数选用。
