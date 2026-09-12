# Release Notes v3.7.65 - 16688 单品链接自动反查店铺与收录同步修复

**Release Date:** 2026-09-12  
**Version:** 3.7.65  

---

## 变更概要 (Overview)

本版本修复了 16688 发卡平台店铺申请收录时，用户/管理员提交商品单品链接（`/goods/G...`）导致连接器校验报错、无法完成全量目录同步入库的问题：
1. 16688 连接器支持自动根据单品链接反查所属店铺编号并抓取全店商品；
2. 探测器与平台识别服务同步支持 16688 单品链接规范化解析与识别；
3. 补全相应单元测试。

---

## 主要更新点 (Key Updates)

1. **16688 连接器单品链接自动反查店铺 (`pipeline/connectors/platform_16688.py`)**
   - 扩展 `_validate_store_url` 支持识别 `/goods/([A-Za-z0-9._~-]+)` 格式链接；
   - 在 `load_records` 中，当输入来源为商品单品链接时，自动调用 16688 开放接口 `POST /shopApi/goods/detail` 取得该商品归属的 `shop_no`，无缝拉取该店铺的所有在售商品。

2. **探测器与平台识别适配 (`detector/probe.py`, `detector/qualify.py`, `apps/api/app/services/source_platform.py`)**
   - 在平台探测与安全质检中支持直接识别 16688 商品单品链接，并在探测结果中自动规范化为该店铺的主页地址（`/shop/S...`）；
   - 在 API 提交预处理中增加单品链接识别，确保后续流转无缝对接。

3. **单元测试与回归防护**
   - 在 `pipeline/tests/test_connectors.py` 中新增通过单品链接反查店铺并抓取全店记录的单元测试；
   - 在 `detector/tests/test_probe.py` 中新增单品链接探测与店铺主页规范化测试。
