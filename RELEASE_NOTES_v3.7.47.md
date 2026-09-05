# Release Notes v3.7.47

## 变更摘要

- 修复 Crawler 来源发现批量提交临时失败时清空候选批次的问题；失败批次会在本轮结束前保留并重试，避免候选静默丢失。
- 版本文件、API、Web package 与锁文件统一升级到 `3.7.47`。

## 验证

- Crawler：79 passed
