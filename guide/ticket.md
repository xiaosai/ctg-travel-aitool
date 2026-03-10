# 门票订购操作指南

**触发条件**：见 [SKILL.md](../SKILL.md) 中「一、需求识别与分流」的门票触发示例。本指南在识别到用户要**购买或查询门票/景区门票**时按需加载。

---

## 必填字段收集原则（通用）

**不写死必填项**。在需要向后台发起请求时：
1. 查阅 [api/ticket.json](../api/ticket.json) 中对应 method 的 `parameters.required` 及 `properties`
2. 若用户未给出某必填字段，用自然语言提示用户填写（勿说「请提供某某参数」）
3. 每次只问一项缺项，待用户回复后再继续
4. 所有必填字段收集完整后再发起请求

**面向用户的话术**：对用户说的内容禁止出现「调用某某接口」「请求 API」「poi-list」等任何技术用语，一律使用「正在为您查询景点…」「请选择游客」等业务话术。

---

## 核心步骤与数据流（Agent 内部参考，勿对用户说）

以下为内部执行顺序与数据依赖，**向用户展示时只用业务话术**（如「正在查景点」「正在下单」），不得出现接口名、API、method 等。

```
1. 获取城市列表(resourceType=3) → 得到 destinationCityId、destinationCityName
2. 查询景点列表 → 使用 destinationCityId、destinationCityName、keyword，分页 current=1、size=15
3. 获取景点详情 → 使用 sourcePoiId 作为 poiId，可选 ticketDate(yyyy-MM-dd)
4. 用户选择门票后 → 调用门票规则接口(poiRule)，入参为 ticketList 中的 resourceId
5. 查询乘客列表(orderType=3) → 若无乘客则先新增乘客再选择
6. 根据门票 visitorInfoType/visitorInfoGroupSize 确定所需游客数量并选择游客
7. 创建门票订单 → resourceItemId 取自景点详情 ticketList 中选中项的 resourceItemId
8. 查询订单详情、订单状态 → orderDetail、getOrderStatus
```

---

## 门票接口调用链路

```
1. cityList（resourceType=3）→ 获取城市列表，得到 cityId、cityName，供景点列表使用
2. poi-list（景点列表）→ 入参：destinationCityId、destinationCityName（来自城市列表）、keyword（用户输入的景点关键字）、current=1、size=15；用户说「换一批景点」时 current++
3. poiDetail（景点详情）→ 入参：poiId（景点列表返回的 sourcePoiId）、ticketDate（可选，格式 yyyy-MM-dd，不传默认当日）
   - 返参 businessStatus：0=营业中，1=已关门，2=筹建中，3=暂停营业
   - 返参 ticketList：该景点门票列表，sellPrice 为展示给用户的门票销售价，resourceItemId 为资源项 id（下单时使用），resourceId 用于规则接口
4. poiRule（门票规则）→ 入参：resourceId（ticketList 中选中门票的 resourceId）
5. getPassengerList（orderType=3）→ 查询门票用乘客列表；无乘客或用户要新增时调用 savePassenger（姓名、手机号、身份证号）
6. createTicketOrder（创建门票订单）→ 入参：resourceItemId（景点详情 ticketList 中选中项的 resourceItemId），以及 quantity、price、totalPrice、travelDate、travellerInfoList 等
7. orderDetail、getOrderStatus → 查询订单详情与状态
```

**游客数量规则**（ticketList 中）：
- `visitorInfoType`：游玩人信息类型  
  - 1 = 不需要游玩人信息  
  - 2 = 只需要一位游玩人信息  
  - 3 = 需要每一位游玩人信息  
  - 4 = 每 visitorInfoGroupSize 个人需要一位游玩人信息  
  - 5 = 每一张票需要 visitorInfoGroupSize 位游玩人信息  
- `visitorInfoGroupSize`：游玩人信息数量。选择乘客时需满足上述规则要求的数量。

---

## 完整交互流程

### 第一阶段：获取城市信息并收集景点查询条件

**内部**：先调用城市列表（resourceType=3），得到各城市的 cityId、cityName。用户查询景点时**城市信息为必填**，用于景点列表的 destinationCityId、destinationCityName。

**对用户的说法**（自然询问）：

```
好的，我来帮您查景点门票！
🏙️ 您想查哪个城市的景点？（例如：北京、上海、杭州）
🔍 想查什么景点？（可以说景点名称或关键字，如「故宫」「长城」）
```

先确定城市，再从城市列表中匹配 cityId、cityName；再结合用户输入的 keyword 查询景点列表。

### 🔧 Python 调用命令 - 城市列表

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method cityList --arg "{\"domesticType\": 1, \"resourceType\": 3}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method cityList --arg-file temp/citylist_ticket_params.json
```

**参数说明**：
- `resourceType`: 3 表示门票资源，用于获取门票相关城市列表

---

### 第二阶段：展示景点列表

查询景点列表。必填：destinationCityName（与 destinationCityId 均来自城市列表）；keyword 为用户输入的景点关键字。分页：current=1，size=15。用户说「换一批景点」时 current 加 1 再请求。

### 🔧 Python 调用命令 - 景点列表

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method poi-list --arg "{\"destinationCityId\": 1, \"destinationCityName\": \"北京\", \"keyword\": \"故宫\", \"current\": 1, \"size\": 15}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method poi-list --arg-file temp/poilist_params.json
```

**关键参数说明**：
- `destinationCityId`、`destinationCityName`: 来自城市列表接口的 cityId、cityName
- `keyword`: 用户输入的景点关键字
- `current`: 页码，首次为 1，「换一批」时递增
- `size`: 每页条数，建议 15

**展示格式示例**（将后台结果润色后展示，一行一行展示，勿用表格）：

```
🎫 为您找到以下景点

【北京 · 故宫相关】

  ① 故宫博物院  人气景点 · 北京东城
  ② 故宫角楼  拍照打卡 · 北京东城
  …

回复序号或景点名称选择，说「换一批」可查看更多
```

---

### 第三阶段：展示景点详情与门票列表

用户选定景点后，调用景点详情。入参：poiId 为景点列表返回的 **sourcePoiId**；ticketDate 为查询日期，格式 yyyy-MM-dd，用户明确说「查某天」时传入，不传默认当日。

**返参注意**：
- `businessStatus`：0=营业中，1=已关门，2=筹建中，3=暂停营业，可据此提示用户营业状态
- `ticketList`：门票列表，每项含 sellPrice（销售价）、resourceItemId（下单用）、resourceId（规则接口用）、visitorInfoType、visitorInfoGroupSize（用于后续确定需选几位游客）

### 🔧 Python 调用命令 - 景点详情

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method poiDetail --arg "{\"poiId\": 123456}"
```

**命令格式（带日期）**：
```bash
python scripts/apiexe.py call --method poiDetail --arg "{\"poiId\": 123456, \"ticketDate\": \"2026-03-15\"}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method poiDetail --arg-file temp/poidetail_params.json
```

**关键参数说明**：
- `poiId`: 景点列表返回的 sourcePoiId
- `ticketDate`: 可选，格式 yyyy-MM-dd，不传默认当天

**展示格式示例**（一行一行展示，勿用表格）：

```
📍 故宫博物院

营业状态：✅ 营业中
（若 businessStatus≠0，可提示：已关门/筹建中/暂停营业）

🎫 可选门票

  ① 成人票  ¥60/张
  ② 学生票  ¥30/张
  ③ 联票(含珍宝馆)  ¥80/张

请选择要购买的门票（回复序号或名称）
```

---

### 第四阶段：查询门票规则（用户选择门票后）

当用户在景点详情的 ticketList 中选定一张门票后，调用门票规则接口，便于用户了解退改、入园等规则。入参：resourceId 为该门票在 ticketList 中的 resourceId。

### 🔧 Python 调用命令 - 门票规则

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method poiRule --arg "{\"resourceId\": \"xxx\"}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method poiRule --arg-file temp/poirule_params.json
```

**参数说明**：
- `resourceId`: 来自景点详情 ticketList 中选中项的 resourceId

**展示**：将规则内容用自然语言归纳后展示给用户（退改规则、入园方式、使用时间等），勿直接贴原始接口文案。

---

### 第五阶段：选择游客（乘客）

先查询乘客列表（门票场景传 orderType=3）。若列表为空或用户需要新增游客，则收集姓名、手机号、身份证号后调用 savePassenger，保存后再拉取乘客列表供选择。

**选择数量规则**（根据景点详情 ticketList 中选中门票的 visitorInfoType、visitorInfoGroupSize）：
- visitorInfoType=1：不需要游玩人，可不选游客（若接口仍要求传则按接口文档处理）
- visitorInfoType=2：选 1 位游客
- visitorInfoType=3：每位游玩人都需要，选的数量等于游玩人数
- visitorInfoType=4：每 visitorInfoGroupSize 个人需要 1 位游客，按人数计算所需游客数
- visitorInfoType=5：每张票需要 visitorInfoGroupSize 位游客，按票数×visitorInfoGroupSize 计算

### 🔧 Python 调用命令 - 乘客列表

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method getPassengerList --arg "{\"orderType\": 3}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method getPassengerList --arg-file temp/passengerlist_ticket_params.json
```

**参数说明**：
- `orderType`: 3 表示门票订单类型

### 🔧 Python 调用命令 - 新增乘客

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method savePassenger --arg "{\"passengerName\": \"张三\", \"identityNo\": \"420102199007015297\", \"phoneNumber\": \"13800138000\"}"
```

**保存乘客必填项**（以 [api/ticket.json](../api/ticket.json) 为准）：旅客姓名(passengerName)、证件号(identityNo)、手机号(phoneNumber)。

**对用户的引导**：只问三项——「请问游客姓名？」「请输入身份证号」「请输入手机号」。收集完整后执行保存，保存成功后再次获取乘客列表供选择。

**展示格式示例**（一行一行展示，勿用表格）：

```
👥 请选择游客（本单需 X 位）

  ① 张三  138****8000
  ② 李四  139****9000

回复序号或姓名；若需新增游客请说「新增游客」
```

---

### 第六阶段：创建门票订单

创建门票订单。resourceItemId 为景点详情 ticketList 中**用户所选门票**的 resourceItemId；其他必填项见 [api/ticket.json](../api/ticket.json)（如 phoneNumber、orderSource、quantity、price、totalPrice、travelDate、travellerInfoList、name、mobile 等）。

**travellerInfoList**：根据第五阶段选中的游客，按接口要求构造（passengerId、name、idNumber、idType、phoneNumber 等）。

### 🔧 Python 调用命令 - 创建门票订单

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method createTicketOrder --arg "{\"resourceItemId\": \"xxx\", \"quantity\": 1, \"price\": 60, \"totalPrice\": 60, \"travelDate\": \"2026-03-15\", \"phoneNumber\": \"13800138000\", \"name\": \"张三\", \"mobile\": \"13800138000\", \"orderSource\": 0, \"travellerInfoList\": [{\"passengerId\": 1, \"name\": \"张三\", \"idNumber\": \"420102199007015297\", \"idType\": \"ID\", \"phoneNumber\": \"13800138000\"}]}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method createTicketOrder --arg-file temp/createticketorder_params.json
```

**关键参数说明**：
- `resourceItemId`: 景点详情 ticketList 中选中门票的 resourceItemId
- `quantity`: 购买数量
- `price`: 单价（如 ticketList 中的 sellPrice）
- `totalPrice`: 总价
- `travelDate`: 游玩日期，格式 yyyy-MM-dd
- `travellerInfoList`: 出游人信息列表，与所选游客数量、visitorInfoType 规则一致

**下单成功反馈示例**（一行一行展示，勿用表格）：

```
🎉 门票订单提交成功

📋 订单信息
景点：故宫博物院
门票：成人票 × 1
游玩日期：2026年3月15日
游客：张三
💰 合计：¥60

请按页面提示完成支付。
```

---

### 第七阶段：查询订单详情与订单状态

当用户要查看某笔门票订单时，先确认订单号（可从订单历史或用户输入获取），再调用 orderDetail 获取详情；需要查状态时调用 getOrderStatus。若用户说「我的门票订单」「查看订单列表」，先通过订单历史（如项目内通用的 orderHistory）获取列表供用户选择，再根据选择查询详情或状态。

### 🔧 Python 调用命令 - 订单详情

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method orderDetail --arg "{\"orderBaseId\": \"TRO202603151234567890\"}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method orderDetail --arg-file temp/orderdetail_params.json
```

### 🔧 Python 调用命令 - 订单状态

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method getOrderStatus --arg "{\"orderBaseId\": \"TRO202603151234567890\"}"
```

**参数说明**：
- `orderBaseId`: 订单号（创建门票订单后返回，或从订单历史获取）

**展示格式示例 - 订单详情**（一行一行展示，勿用表格）：

```
📋 门票订单详情

订单号：TRO202603151234567890
状态：✅ 已支付 / ⏰ 待支付 / 已使用 / 已退款

景点：故宫博物院
门票：成人票 × 1
游玩日期：2026年3月15日
游客：张三 138****8000

💰 金额：¥60
```

---

## 步骤与数据对照（Agent 内部参考）

| 阶段 | 步骤说明 | 关键入参 | 关键出参 |
|------|----------|----------|----------|
| 1 | 获取城市列表 | resourceType=3 | cityId、cityName |
| 2 | 景点列表 | destinationCityId、destinationCityName、keyword、current、size | sourcePoiId 等 |
| 3 | 景点详情 | poiId(sourcePoiId)、ticketDate(可选) | businessStatus、ticketList(sellPrice、resourceItemId、resourceId、visitorInfoType、visitorInfoGroupSize) |
| 4 | 门票规则 | resourceId(ticketList 中) | 规则内容 |
| 5 | 乘客列表 | orderType=3 | 乘客列表 |
| 5 | 保存乘客 | passengerName、identityNo、phoneNumber | 新增乘客 |
| 6 | 创建门票订单 | resourceItemId、quantity、price、totalPrice、travelDate、travellerInfoList 等 | 订单号等 |
| 7 | 订单详情 | orderBaseId | 订单详情 |
| 7 | 订单状态 | orderBaseId | status |

---

## 异常处理

### 核心原则

**当后台请求异常时，不要让用户重复提供信息！**

用户已经选择的内容必须记住：
- ✅ 城市与景点关键字
- ✅ 选中的景点
- ✅ 选中的门票
- ✅ 选中的游客

### 常见错误处理

**1. 后台返回异常**

向用户展示示例（勿出现「接口」「API」等词）：

```
❌ 查询景点时遇到系统异常

我已为您记录的选择：
  🏙️ 城市：北京
  🔍 关键字：故宫

请稍后再试，或换个关键词/城市试一下。
```

**2. 景点列表为空**

```
未找到与「XXX」相关的景点。

可以尝试：
  ① 换个关键词（如景区全称）
  ② 换一批（查看更多）
  ③ 换个城市
```

**3. 网络超时**

```
❌ 网络连接超时，可能是网络不稳定

我已为您记录的选择：[列出已选城市、关键字、景点等]

您可以稍后重试，或直接到景区官网/APP 购票。
```

---

## 用户体验

### 对话风格

✅ **友好自然**：「好的，帮您查一下北京的故宫门票！」  
❌ **机械生硬**：「请提供目的城市ID和关键字。」

### 后台返回结果润色

- **使用符号**：🎫 🏙️ 📍 👥 📋 💰 ✅ ❌ 等增强可读性
- **一行一行展示**：每条信息单独一行，勿用表格、框线
- **适当留白**：信息块之间空行分隔
- **引导语**：在信息块末尾加简短操作提示（如「回复序号选择」「说换一批查看更多」）

### 错误处理

✅ **提供解决方案**：给出可选项，让用户选择  
❌ **只报错**：仅提示「错误：系统异常」

---

## 完整对话示例

```
用户: 我想买故宫门票

助手: 好的，帮您查故宫门票！
🏙️ 您要查的是哪个城市？（故宫在北京，我就按北京来查可以吗？）

用户: 对，北京

助手: 🎫 为您找到以下景点

  ① 故宫博物院  人气景点 · 北京东城
  ② 故宫角楼  拍照打卡

回复序号选择景点

用户: 1

助手: 📍 故宫博物院  营业中

🎫 可选门票
  ① 成人票  ¥60/张
  ② 学生票  ¥30/张

请选择要购买的门票

用户: 成人票

助手: （可选）为您查询该门票的购买与入园规则…（展示 poiRule 归纳内容）
👥 请选择游客（本单需 1 位）
  ① 张三  138****8000
回复序号或姓名；需新增请说「新增游客」

用户: 张三

助手: 请确认游玩日期（如明天、3月15日）

用户: 明天

助手: 🎉 门票订单提交成功
景点：故宫博物院  门票：成人票×1  游玩日期：2026年3月11日  游客：张三  💰 ¥60
请按页面提示完成支付。
```

---

## 执行方式（Agent 内部）

识别用户意图后，查阅 [api/ticket.json](../api/ticket.json) 选择对应 method，按 `parameters` 构造 params，使用 `scripts/apiexe.py call --method <method> --arg '<params_json>'` 或 `--arg-file` 执行。**以上为内部执行方式，对用户只说业务话术（如「正在为您查询景点」「正在下单」），不得出现接口名、API、method 等。**

## 多资源场景

若用户同时订购门票和其他资源（如机票+门票），先完成当前资源订购流程，再引导用户处理下一个资源。
