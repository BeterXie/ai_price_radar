# Release Notes - v3.7.80

## 店铺专属卡包、LDXP 真实优惠券池与前台锦鲤彩蛋掉落 (v3.7.80)

### 1. 业务目标与价值闭环
- **商业变现闭环**：通过在雷达站（`ai.pricememo.cn`）引入真实店铺优惠券，连接“比价发现 $\to$ 幸运领券 $\to$ 店铺下单”，大幅提升前台流量转化率与用户黏性；
- **官方直营保障**：优惠券直接适用于“彩头AI”（`https://wzyp.cn/shop/pricememo`）官方小铺，结算时输入 10 位券码立享满减抵扣（首批：满15减5元）。

### 2. 核心架构与功能模块
1. **数据模型与结构迁移 (`scripts/migrate_shop_coupons_v16.py`)**:
   - `shop_coupons`：持久化 LDXP 10 位真实券码、抵扣面额、使用门槛、过期时间与用户绑定关系；
   - `coupon_campaigns`：营销活动口令（如 `RADAR888`、`CAITOUAI`），支持限制单人兑换上限与活动名额。
2. **商户卡券同步 (`scripts/sync_ldxp_coupons.py`)**:
   - 调用 LDXP `/merchantApi/SalesCoupon/list` 与 `/merchantApi/SalesCoupon/codeList`；
   - 自动拉取商户后台生成的批次与 10 位券码，增量入库保持卡券池库存充盈。
3. **用户卡包、动态掉落与兑换 API (`apps/api/app/routers/user.py`)**:
   - `GET /api/v1/user/coupons/drop-status`：查询掉落状态与自适应动态概率（库存紧缺时智能衰减）；
   - `GET /api/v1/user/coupons`：获取用户所有领取的卡券；
   - `POST /api/v1/user/coupons/redeem`：输入口令兑换专属优惠券；
   - `POST /api/v1/user/coupons/claim-drop`：领取前台随机掉落的幸运券，支持每日限额与库存校验。
4. **后台优惠券与营销管理面板 (`apps/web/components/coupons-admin-panel.tsx`)**:
   - 挂载于 `/admin?tab=coupons`；
   - 提供可用库存、已领、已核销等实时监控数据指标；
   - 可配置前台随机掉落开关、基准概率滑块、库存紧张自动降频及单用户单日上限；
   - 一键同步链动小铺(LDXP)券码，支持批量文本粘贴导券与自动排重；
   - 营销口令（如 `RADAR888`）生命周期与配额管理。
5. **前端个人中心卡包 (`apps/web/components/account-client.tsx`)**:
   - 个人中心增加专属卡包板块，卡片式展示满减额度、10 位券码、一键复制按钮与直达店铺下单按钮；
   - 内置活动口令兑换框。
6. **前台锦鲤彩蛋概率浮窗 (`apps/web/components/lucky-coupon-drop.tsx`)**:
   - 全局挂载在 `apps/web/app/layout.tsx`，客户端加载后自动查询后端掉落状态与动态概率，中奖后展示惊喜彩蛋浮窗，支持一键领取并存入卡包。

### 3. 质量保障与门禁
- Python 单元测试：`apps/api/tests/test_user_coupons.py` 8/8 通过，`scripts/tests/test_migrate_shop_coupons_v16.py` 3/3 通过，全量 pytest 371/371 通过；
- 版本与健康检查：`apps/api/tests/test_version.py` 通过；
- 前端测试与构建：`npm run typecheck` 与 63 个前端测试全部通过。

