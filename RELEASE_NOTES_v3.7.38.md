# AI Price Radar v3.7.38 Release Notes

## Overview

v3.7.38 enhances merchant communication during shop onboarding by including the shop's name and original URL (`店铺地址`) in all notification emails sent to the applicant.

## Key Changes

1. **Intake Notification Email Transparency**:
   - Applicant emails for auto-approval and manual approval (`shop_request.approved`) now explicitly list:
     - `店铺名称：{intake.shop_name or '未填写'}`
     - `店铺地址：{intake.source_url}`
   - Official onboarding & publication email (`shop_intake.onboarded`) clearly distinguishes:
     - `店铺地址：{intake.source_url}` (the merchant's external shop URL)
     - `本站收录页面：https://ai.pricememo.cn/shops/{shop_token}` (the catalog page on AI Price Radar)
   - Failure / error / rejection notifications (`shop_request.rejected`, `shop_intake.no_products`, `shop_intake.validation_failed`) also include the shop name and address so applicants immediately know which submission was affected.

2. **Security & Validation**:
   - `source_url` and `shop_name` continue to pass through strict URL normalization and control-character stripping, preventing CRLF and SMTP header injection risks.
