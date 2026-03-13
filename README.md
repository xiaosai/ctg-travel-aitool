# CTG Travel Booking Skill

中旅旅行开放平台一站式预订助手，整合机票、酒店、火车票、门票四大资源，支持查询、预订、退款全流程。

## 功能特性

- 多资源聚合：覆盖机票、酒店、火车票、门票主流场景
- 标准化 API：基于 OpenClaw 规范封装，接口一致易用
- 智能引导：自动识别用户意图，逐步收集预订信息

## 快速开始

1. 复制配置文件模板
   ```bash
   cp config/ctgConfig.example.json config/ctgConfig.json
   ```

2. 填写 API 凭证
   ```json
   {
     "apiKey": "your-api-key",
     "callUrl": "https://pro-api.ourtour.com/openapi/tools/call"
   }
   ```

## 目录结构

```
ctg-travel-aitool/
├── SKILL.md              # Skill 定义文件
├── config/               # 配置目录
├── api/                  # 接口文档
├── guide/                # 操作指南
└── scripts/              # 调用脚本
```

## License

MIT No Attribution

Copyright (c) 2026 CTG Travel

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

---

> This repository is a mirror of the internal project ctg-travel-aitool and published with permission.
