# Senluo Bedrock Core — 森羅基岩版共用核心

[简体中文](README.zh-CN.md) · **繁體中文** · [English](README.md)

森羅基岩版 addon 家族的**非官方共用 SDK 與本地整合工具**。

Core 是**建置階段的 SDK**，程式碼會複製到各個使用它的封包；它不額外增加行為包、全域 tick 迴圈或存檔資料擁有者。

```text
Core SDK ──→ 煙火（事件路由及公開食物中繼資料）
        └──→ Cookery 原始宿主（透過煙火已審查的接入器）
本機安裝器＋自行取得的 Cookery 原包 ──→ 本機適配封包
```

## 現行組裝與相依

目前的家族安裝使用 **Tavern 0.6.194、Grilling 2.8.206、世界名酒（World Liquor）0.1.180**。工具包 **0.15.0** 保留當前 G206 與 Immersive Eating 接入器：本機 Cookery **1.6.20008**、Immersive Eating **1.1.20002**；保留歡迎聊天訊息及原生配方排序，同時避免重複進行完整配方排序。

請由[現行家族安裝流程](docs/FAMILY-ASSEMBLY.md#current-g206-installation)開始。保留各包／模組 UUID、物品 ID 及存檔資料所有權；升級前必須備份**已停止運作**的世界，先在副本上測試。

## 技術文件

- [SDK 合約與來源責任](docs/SDK.md)
- [Cookery 本機安裝](docs/COOKERY.md)
- [本地家族組裝工具](docs/FAMILY-ASSEMBLY.md)
- [自有移植接入器](docs/PORT-ADAPTERS.md)
- [驗證範圍與限制](docs/VALIDATION.md)

公開與伺服器整合使用相同的煙火標準玩家合成器及 Core 指南輔助工具。公開對照範圍涵蓋三個自有移植和必要接線；無關第三方 addon 必須另行下載。原生或存檔證據**不等於已通過畫面客戶端驗收**。正式發布資產請從 [Releases](https://github.com/burnt-tea-dev/senluo-bedrock-core/releases)取得。

此處不分發作者原始封包、完整作者模組、玩家世界、私有整合歷史、伺服器設定或憑證。請由[作者項目](https://www.curseforge.com/minecraft-bedrock/addons/kaleidoscope-cookery-unofficial)自行取得 Cookery。本非官方項目與 Mojang 及原作者無從屬關係。

## 授權與歷史相容

SDK 和新編寫工具採 [BSD-3-Clause](LICENSE)。另一個煙火 addon 提供的玩法輔助程式保留該項目的聲明；本地適配的作者內容仍受其原授權與署名約束。

較早版本的 descriptor 及其驗證紀錄繼續保留作歷史。重現舊 Cookery 解碼輸出必須使用當時的工具包來源；0.12 的輔助工具會刻意拒絕無法更改的舊版 helper pin。

選用的 TACZ 路線目前可本機建置 **1.0.20005**，包含資源堆疊 PBR 功能，並同時保留 24 個槍械玩家屬性及煙火的 4 個屬性。使用 [TACZ20005 配方](adapters/owned-t194-g206-w180-tacz-pbr.json)，但仍須個別完成全家族、既有存檔、回退及客戶端驗收。工具包 0.12 的發布和 TACZ20004 配方仍只屬歷史結果。

Cookery 配方註冊現在**每 tick 最多處理 4 條傳入訊息**，目標執行時間為 **1 毫秒**。保留原始註冊驗證、FIFO 替換順序、全部配方與歡迎訊息；同步匯出的註冊函式不變。請使用[現行 Cookery descriptor](adapters/cookery-1.6.4-grilling-2.8.206-recipe-ingress.json)和[可選 TACZ 家族 descriptor](adapters/owned-t194-g206-w180-recipe-ingress-tacz.json)。安裝器檢查與原生／客戶端驗收必須分開。

來源與家族建置器預設選擇現行 G206／Cookery20008 組裝。歷史 G201／G203 及早期 Cookery 配方只透過明確的 `--descriptor` 參數選用。
