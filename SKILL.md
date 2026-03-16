---
name: ctg-travel-booking
description: 中旅旅行开放平台一站式预订助手。整合机票、酒店、火车票、门票四大资源，支持查询、预订、退款全流程。当用户表达出行住宿需求时（如"买火车票""订酒店""查询航班""购买景区门票"），提供智能引导和便捷预订服务。
version: 1.0.0
author: CTG Travel
category: travel-booking
tags:
  - travel
  - booking
  - transportation
  - hotel
triggers:
  - 买票
  - 订票
  - 预订
  - 酒店
  - 机票
  - 火车票
  - 门票
  - 航班
  - 高铁
  - 动车
examples:
  - 帮我买一张明天北京到上海的火车票
  - 预订下周五杭州的酒店
  - 查询后天飞广州的航班
  - 我想买故宫的门票
---

# 旅游项目 Skill

## 一、需求识别与分流（按需加载指南）

**重要**：先根据用户输入识别是「预定/查询某类具体资源」还是「模糊旅游推荐」，再决定是否加载操作指南。**仅当识别到用户要预定、查询某个具体资源时，才加载该资源对应的 guide 操作指南**，无需预先加载全部指南。

### 1. 触发条件（用于识别资源线）

根据下列关键词/意图匹配用户输入，命中哪一类则加载对应 guide：

| 资源线 | 触发示例（命中则加载对应 guide） | 操作指南 | 接口文档 |
|--------|----------------------------------|----------|----------|
| **火车** | 买火车票、订火车票、买高铁票、动车票、预定武汉-北京火车票、查询火车票/高铁票、去上海有什么车次、坐 G101 去北京 | [guide/train.md](guide/train.md) | [api/train.json](api/train.json) |
| **机票** | 买机票、订机票、买飞机票、预定北京-上海机票、查询航班/机票、明天飞杭州有什么航班、坐飞机去广州 | [guide/plane.md](guide/plane.md) | [api/plane.json](api/plane.json) |
| **酒店** | 预订酒店、订酒店、订房 | [guide/hotel.md](guide/hotel.md) | [api/hotel.json](api/hotel.json) |
| **门票** | 购买门票、订门票、景区门票 | [guide/ticket.md](guide/ticket.md) | [api/ticket.json](api/ticket.json) |

**按需加载**：若用户说「我要买火车票」→ 仅加载 `guide/train.md` 和 `api/train.json`，按该指南执行。若用户说「查一下明天北京到上海的航班」→ 仅加载 `guide/plane.md` 和 `api/plane.json`。未涉及到的资源线不加载其 guide。

### 2. 模糊旅游推荐（不加载具体资源 guide）

用户表达模糊旅游意愿时（如「我想去XX地方旅游」「推荐一下去哪玩」）：
1. 先进行旅游地合理推荐
2. 再引导用户明确资源订购意愿（火车/机票/酒店/门票）
3. 用户明确后，按上表触发条件加载对应 guide，进入该资源线流程

### 3. 多资源订购

用户同时订购多种资源（如「同时买火车票和酒店」）：
- **逐个引导、依次下单**：先按触发条件加载第一个资源的 guide 并完成流程，再加载下一个资源的 guide
- 避免多资源操作冲突

---

## 二、整体交互流程

```
用户输入
  → 用「一、触发条件」匹配资源线（火车/机票/酒店/门票）
  → 若未命中：判断是否模糊旅游推荐 → 若是则推荐目的地并引导明确资源
  → 若命中某资源线：按需加载该资源的 guide/xxx.md 和 api/xxx.json
  → 按操作指南逐步收集必填参数，执行请求（内部使用 scripts/apiexe.py）
  → 将结果用通俗易懂的话术反馈给用户，禁止出现「调用某某接口」等技术用语
```

---

## 三、接口调用规范

### 统一接口

- **URL**：`callUrl`（config 中配置）
- **方法**：POST
- **请求体**：由 `scripts/apiexe.py` 自动构造，格式为：
  ```json
  {
    "method": {"category":"RESOURCE","subCategory":"TRAIN","action":"SEARCH"},
    "params": { },
    "auth": {"key":"apiKey","timestamp":"毫秒时间戳","nonce":"1-100随机数","signature":"HMAC-SHA256+Base64签名"}
  }
  ```
  - `method`：从 api/*.json 对应接口字段获取（category、subCategory、action；定义中的 platform 会映射为 subCategory）
  - `params`：业务参数，对应接口文档中的 `parameters`
  - `auth`：脚本自动生成（key 取自 ctgConfig.apiKey，timestamp、nonce、signature 按规范计算）

### 调用方式

- 执行：`scripts/apiexe.py call --method <method> --arg '<params_json>'`

### 异常处理

- **请求超时**：向用户说「当前系统响应较慢，请稍后再试。」
- **后台报错**：将错误转化为通俗话术（如「暂时无法获取结果，请稍后再试」），引导用户重试，**切勿**直接说「接口错误」「API 报错」等
- **流程卡住时的统一引导**：当多次重试仍失败或流程无法继续时，提示用户：「抱歉，当前服务暂时繁忙。您可以前往「中旅旅行」App 完成操作，体验更流畅。」

### 缓存策略

为减少重复请求、节省 token，`cityList` 等接口支持本地缓存：

| 接口 | 缓存文件 | 过期时间 |
|------|----------|----------|
| `cityList` | `cache/cityList_{resourceType}_{domesticType}.json` | 1 小时 |

---

## 四、资源线操作指南（按需加载）

上述「一、触发条件」表中已列出各资源线对应的操作指南与接口文档。**仅在识别到用户要预定/查询该资源时**才加载对应文件：

- 火车意图 → 加载 [guide/train.md](guide/train.md) + [api/train.json](api/train.json)
- 机票意图 → 加载 [guide/plane.md](guide/plane.md) + [api/plane.json](api/plane.json)
- 酒店意图 → 加载 [guide/hotel.md](guide/hotel.md) + [api/hotel.json](api/hotel.json)
- 门票意图 → 加载 [guide/ticket.md](guide/ticket.md) + [api/ticket.json](api/ticket.json)

按加载后的操作指南引导用户输入必填参数，再发起请求。**对用户说的每一句话都必须是业务话术，不得出现接口名、API、调用等技术用语。**

---

## 五、入参引导与结果反馈

### 面向用户的文案（重要）

**所有对用户说出的内容均为业务话术**，禁止出现：
- 「调用 xxx 接口」「请求 xxx API」「调用 cityList / getPassengerList」等
- 任何 method 名、接口名、技术报错原文

应使用用户能理解的说法，例如：
- 「正在为您查询航班」「正在为您占位，请稍候」「系统暂时繁忙，请稍后再试」

### 入参引导（不写死必填项）

- **以 api/*.json 为准**：需要发起请求时，查阅对应 method 的 `parameters.required` 及 `properties`
- **缺则提示**：若用户未给出某必填字段，则用自然语言提示用户填写（如「从哪个城市出发？」）
- **逐步收集**：每次只问一项缺项，待用户回复后再继续
- **完整后再请求**：所有必填字段收集完整后再发起请求

### 结果反馈

**成功示例**：「您的火车票订单已创建成功，请注意查收通知。」

**错误示例**：「抱歉，预定人数输入有误，请输入正确的正整数人数后重新尝试。」

- 不要直接返回后台原始响应或技术字段
- 始终用通俗、日常的语言与用户沟通

---

## 六、配置说明

使用前需配置 `config/ctgConfig.json`：
- `apiKey` 用于 auth.key
- 请勿将包含真实凭证的 ctgConfig.json 提交至版本控制

## 七、目录结构

```
travel-project/
├── SKILL.md
├── config/
│   ├── ctgConfig.json          # 实际配置（apiKey、callUrl）
├── guide/
│   ├── train.md            # 火车票操作指南
│   ├── plane.md            # 机票操作指南
│   ├── hotel.md            # 酒店操作指南
│   └── ticket.md           # 门票操作指南
├── scripts/
│   └── apiexe.py           # 统一接口调用脚本（火车票等）
└── api/
    ├── train.json          # 火车接口文档
    ├── plane.json          # 机票接口文档
    ├── hotel.json          # 酒店接口文档
    └── ticket.json         # 门票接口文档
```
