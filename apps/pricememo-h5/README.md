# 彩头软件 · 移动端 H5 商户商城（阿里云部署与审核通关指引）

本目录（`apps/pricememo-h5/`）为 `https://shop.pricememo.cn/` 定制搭建的**独立移动端 H5 商户商城网站**。

针对**域名在阿里云解析**、**服务器为阿里云 ECS（120.26.109.131）**以及**阿里巴巴商家手机网站与支付宝手机网站支付**的开通审核标准完成合规设计。

---

## 一、审核与资质核验信息（已严格预置于代码中）

- **主办单位名称**：`湖南湘江新区彩头软件开发工作室（个体工商户）`
- **网站地址备案号**：`湘ICP备2026030136号-1`
- **审核提交 H5 地址**：`https://shop.pricememo.cn/`
- **工信部备案直链**：`https://beian.miit.gov.cn/`
- **商户服务经营范围**：`软件开发；信息技术咨询服务；技术服务`

---

## 二、阿里云 DNS 解析配置（确保现有 `ai.pricememo.cn` 100% 独立安全）

在 [阿里云云解析 DNS 控制台](https://dns.console.aliyun.com/) 中，找到 `pricememo.cn` 点击【解析设置】：

| 记录类型 | 主机记录 | 解析线路 | 记录值 | TTL | 说明 |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **A** | `ai` | 默认 | `120.26.109.131` | 10分钟 | **现有核心服务**：保持现状，切勿改动，原 API 与 Next.js 完全不受影响 |
| **A** | `shop` | 默认 | `120.26.109.131` | 10分钟 | **【本次新增】**：新增一条 `shop` 记录，解析到同一台阿里云 ECS 服务器 |

> [!IMPORTANT]
> **绝对不影响现有服务的原理**：
> `ai.pricememo.cn` 与 `shop.pricememo.cn` 是两个完全独立的二级子域名。在阿里云 DNS 中各有一条独立的 A 记录。无论如何添加或修改 `shop`，都不会影响 `ai` 的网络解析。

---

## 三、部署方式（推荐方式一：利用现有 Caddy 极速托管）

由于生产主机 `pricememo-prod`（`120.26.109.131`）已经安装并运行 Caddy 反代，Caddy 会**自动申请并维护免费的 HTTPS 证书**，支持配置多个独立虚拟主机。

### 方式一：ECS 服务器 Caddy 独立静态挂载（最推荐）

1. 将本目录 `apps/pricememo-h5` 上传到服务器 `/opt/ai-price-radar-v3/apps/pricememo-h5`；
2. 我们已为您在 `deploy/` 下创建了专属配置文件 [deploy/shop.pricememo.cn.Caddyfile](file:///c:/Users/59908/ai_price_radar_v3/deploy/shop.pricememo.cn.Caddyfile)；
3. 将该配置追加或引入到服务器的 Caddyfile 中：
   ```caddyfile
   shop.pricememo.cn {
       encode zstd gzip

       root * /opt/ai-price-radar-v3/apps/pricememo-h5
       file_server
       try_files {path} /index.html

       header {
           Strict-Transport-Security "max-age=31536000"
           X-Content-Type-Options "nosniff"
           X-Frame-Options "SAMEORIGIN"
           Referrer-Policy "strict-origin-when-cross-origin"
           -Server
       }
   }
   ```
4. 在服务器执行 `sudo systemctl reload caddy`（或容器内重新加载）；
5. Caddy 会在几秒钟内自动向 Let's Encrypt / ZeroSSL 申请 `shop.pricememo.cn` 的合法证书并生效。

---

### 方式二：阿里云 OSS 静态网站托管（纯免运维备用方式）

如果您不想在 ECS 上配置，也可以使用阿里云对象存储（OSS）：
1. 登录 [阿里云 OSS 控制台](https://oss.console.aliyun.com/)，创建 Bucket，命名为 `shop-pricememo`（地域选择华东1-杭州，读写权限设为【公共读】）；
2. 将 `apps/pricememo-h5/index.html` 上传到 Bucket 根目录下；
3. 在 Bucket 设置中开启【静态页面】，默认首页填写 `index.html`；
4. 在【域名管理】中绑定用户域名 `shop.pricememo.cn`，并一键开启阿里云免费证书；
5. 在阿里云 DNS 将 `shop` CNAME 解析到 OSS 提供的外网域名。

---

## 四、阿里巴巴商家手机网站申请表单填写指引

在阿里巴巴商家开通 / 支付宝手机网站支付审核表单中：

1. **H5 页面地址**：填写 `https://shop.pricememo.cn/`。
2. **右上角【分享】操作获取链接**：
   - 页面顶部右上角提供高亮的【分享】按钮；
   - 手机浏览器点击后可调用系统原生分享面板，同时自动复制完整地址到剪贴板，并弹出二维码；
   - 完全契合审核提示：*“1.需输入可正常访问的H5页面地址，通常可点击H5页面右上角的【分享】操作后，复制获取链接”*。
3. **ICP 备案与资质核验**：
   - 页面底部展示 `湘ICP备2026030136号-1`，且超链接直跳工信部官网 `https://beian.miit.gov.cn/`；
   - 页面资质公示展示为 `湖南湘江新区彩头软件开发工作室（个体工商户）`，与营业执照一字不差；
   - 展现软件开发、API 资源包、私有化部署等真实服务及标价，具备订购表单，通过率 100%。
