# 火车票订购操作指南

**触发条件**：见 [SKILL.md](../SKILL.md) 中「一、需求识别与分流」的火车触发示例。本指南在识别到用户要**预定或查询火车票**时按需加载。

---

## 必填字段收集原则（通用）

**不写死必填项**。识别到需要调用某个接口时：

1. 查阅 [api/train.json](../api/train.json) 中该 method 的 `parameters.required` 及 `properties`
2. 若用户未给出某必填字段，则提示用户必须填写
3. 每次只问一项缺项，待用户回复后再继续
4. 所有必填字段收集完整后再调用接口

**面向用户的话术**：对用户说的内容禁止出现「调用某某接口」「请求 API」「getPassengerList」等任何技术用语，一律使用「正在为您查询…」「请选择乘客」等业务话术。

---

## 核心步骤与数据流（Agent 内部参考，勿对用户说）

以下为内部执行顺序与数据依赖，**向用户展示时只用业务话术**（如「正在查车次」「正在占位」），不得出现接口名、API、method 等。

```
1. 查询车次列表 → 使用 fromStation、fromCityType、toStation、toCityType、ticketDate
2. 查询车次详情 → 使用车次列表返回的 fromStation、toStation、fromDate、trainNo作为车次详情参数的fromStation、toStation、ticketDate、trainNo
3. 查询乘客列表 → 若为空则先新增乘客再继续
4. 创建火车票订单 → orderItem.resourceItemId 取自车次详情的 resourceItemId
5. 轮询订单状态 → 占位完成后引导用户支付
```

---

## 完整交互流程

### 第一阶段：收集基本信息（调用 train.search 前）

**自然询问**，而非机械填表。查阅 api/train.json 中 `train.search` 的 required 字段，若用户未给出则逐项提示：

```
好的，我来帮您预订火车票！
🚄 从哪个城市出发？
🎯 要去哪里？
📅 哪天出发？（可以说"明天"、"本周日"、"3月8日"等）
```

**智能识别日期**：

| 用户输入                     | 转换结果          |
| ---------------------------- | ----------------- |
| 今天/今日                    | 当前日期          |
| 明天/明日                    | 当前日期+1        |
| 后天、大后天                 | 对应计算          |
| 下周一~下周日、这周一~这周日 | 计算对应日期      |
| 3月8日/3月8号/3-8            | 解析为 YYYY-MM-DD |
| 5天后                        | 当前日期+N        |

**站点类型判断**（用于 fromCityType/toCityType）：

- 包含「站」「南」「北」「东」「西」→ 火车站（type=1）
- 否则 → 城市（type=2）

---

### 第二阶段：展示车次选项

调用 `train.search`，必填字段按接口文档，缺则提示。

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method train.search --arg "{\"fromStation\": \"上海\", \"fromCityType\": 2, \"toStation\": \"北京\", \"toCityType\": 2, \"ticketDate\": \"2026-03-18\"}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method train.search --arg-file temp/trainlist_params.json
```
**展示格式示例**（接口返回后润色展示，一行一行展示，勿用表格）：

```
🚄 为您找到以下车次

📅 2026年3月8日 武汉 → 长沙

【推荐】G101 汉口 08:00 → 长沙南 09:15  1h15m  ⭐ 热门
   💺 二等座 ¥164  一等座 ¥262  商务座 ¥492

G103 汉口 09:15 → 长沙南 10:30  1h15m
   💺 二等座 ¥164  一等座 ¥262

G105 武汉 10:30 → 长沙南 11:45  1h15m  ⚡ 最快
   💺 二等座 ¥199  一等座 ¥319  商务座 ¥576

回复车次号（如 G101）或时间偏好即可选择
```

**智能筛选和推荐**：

- 优先展示高铁/动车
- 按时间排序（早班车优先）
- 标注热门车次、价格、坐席类型

**用户选择方式**：

- 说车次号：「G101」
- 说序号：「第1个」
- 说时间偏好：「早点的」「下午3点多的」

---

### 第三阶段：确认坐席选择

用户选定车次后，调用 `train.detail` 获取坐席详情。必填字段按接口文档，缺则提示。从返回中获取 resourceItemId、各坐席价格、余票。

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method train.detail --arg "{"fromStation": "上海", "toStation": "北京", "ticketDate": "2026-03-18", "trainNo": "G101", "entranceSource": 0}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method train.detail --arg-file temp/traindetail_params.json
```

**展示格式示例**（接口返回后润色展示，一行一行展示，勿用表格）：

```
🪑 G101 可选坐席

  ① 二等座  ¥164  剩余 99 张  适合大多数出行
  ② 一等座  ¥262  剩余 12 张  更宽敞舒适
  ③ 商务座  ¥492  剩余  3 张  顶级体验

请选择坐席类型（如：二等座、一等座）
```

---

### 第四阶段：选择乘车人

调用 `getPassengerList` 获取乘车人列表。必填字段按接口文档，缺则提示。

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method getPassengerList --arg "{"orderType": 2}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method getPassengerList --arg-file temp/passengerlist_params.json
```

**参数说明**：

- `orderType`: 订单类型，默认 2（火车票）

**展示格式示例**（接口返回后润色展示，一行一行展示，勿用表格）：

```
👥 请选择乘车人（可多选）

【最近使用】
  ① 张三  (成人)  138****1234
  ② 李四  (成人)  139****5678

【全部联系人】
  ③ 王五  (儿童)  150****5000

回复序号或姓名，如「1」「张三」或「1,2」「张三、李四」
```

**乘客类型说明**（供展示与校验参考）：

| 类型     | 代码 | 说明           | 是否需购票 |
| -------- | ---- | -------------- | ---------- |
| 成人     | 0    | 18岁以上成人   | ✅ 是      |
| 儿童     | 1    | 1.2m-1.5m 儿童 | ✅ 是      |
| 免费儿童 | 2    | 身高不足1.2m   | ❌ 否      |

**免费儿童处理**：

- 系统自动过滤免费儿童（subPassengerType=2）
- 免费儿童无需购票，直接携带乘车

**添加新乘客**：当用户表示「没有合适的人」「需要添加乘车人」「添加新联系人」等意愿时，调用 `savePassenger` 接口。### 🔧 Python 调用命令 - 新增乘客

### 🔧 Python 调用命令 - 新增乘客

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method savePassenger --arg "{"passengerName": "张三", "identityType": "ID", "identityNo": "420102199007015297", "phoneNumber": "15629199695"}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method savePassenger --arg-file temp/savepassenger_params.json
```

**保存乘客必填项**（以 [api/train.json](../api/train.json) 为准）：旅客姓名、证件/身份证号、手机号码。其他字段可选不传。

**对用户的引导**：只问三项——「请问乘客姓名？」「请输入身份证号」「请输入手机号」。收集完整后执行保存。

- 保存成功后，再次获取乘客列表，继续让用户选择乘客。


---

### 第五阶段：下单占位

调用 `train.createOrder`。必填字段按接口文档，缺则提示。resourceItemId 从 train.detail 返回中获取，passengers 从 train.passengers 中选取用户勾选的人员构造。
**顶层必传**：memberId(可空)、userName（可空）、phoneNumber(可空)、email（可空）、orderSource（如 0）、orderType（如 2）、subOrderType（`DOMESTIC_TRAIN`）、fromDate（YYYY-MM-DD）、departureCityId、destinationCityId。
**orderItem**每条需包含： resourceItemId、hasSeat、fromDate、seatTypeName、adultSalePrice、childSalePrice、passengers；

- **resourceItemId**：传train.detail返回的resourceItemId；
- **hasSeat**: 默认传false
- **fromDate**: 传train.detail返回的fromDate；
- **passengers**对象: passengerId、 name, idType、 idNo、passengerType(乘客类型 0-成人 1-儿童 2-免费儿童)、seatTypeName(座位类型名称)、parentId(绑定成人ID (仅免费儿童有效))

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method train.createOrder --arg "{\"distributor\":null,\"email\":\"\",\"memberId\":\"83a47edff10246af9f29ff4975e86646\",\"userName\":\"\",\"phoneNumber\":\"18872233316\",\"orderSource\":3,\"orderType\":2,\"subOrderType\":\"DOMESTIC_TRAIN\",\"orderItem\":{\"hasSeat\":false,\"resourceItemId\":\"RW12ff1d2df9da42567f1b939bbfefe481\",\"fromDate\":\"2026-02-12\",\"seatTypeName\":\"无座\",\"adultSalePrice\":298,\"childSalePrice\":149,\"passengers\":[{\"passengerId\":316,\"passengerType\":0,\"seatTypeName\":\"无座\",\"parentId\":null,\"idNumber\":\"420115199001010101\",\"phoneNumber\":\"18872233316\",\"name\":\"张飞\"}]},\"departureCityId\":\"4\",\"destinationCityId\":\"785\",\"serviceFee\":0.00}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method train.createOrder --arg-file temp/createorder_params.json
```

**重要**：创建订单成功后，订单处于**占位中**状态，此时**必须**进入第六阶段轮询订单状态，根据轮询结果再决定后续反馈，切勿直接提示用户支付。

**自动处理**：自动处理 API 参数格式，无需用户额外输入。

---

### 第六阶段：订单状态轮询（必执行）

下单成功后，订单处于占位中，**必须**有限次数轮询 `train.orderStatus`，直到得到明确结果。必填字段 orderBaseId 从 train.createOrder 返回的 data.orderBaseId 获取。

- **轮询间隔**：10 秒
- **最大轮询次数**：6 次（最多等待约 1 分钟）

**状态码与处理**：

| 状态码 | 含义             | Agent 处理                                 |
| ------ | ---------------- | ------------------------------------------ |
| `10`   | 处理中           | 继续轮询，可提示「正在为您占位，请稍候…」 |
| `12`   | 占位成功         | 进入第七阶段，展示成功反馈并提醒支付       |
| `11`   | 占位失败         | 进入第七阶段，展示失败反馈并引导重新预订   |
| 超时   | 轮询 6 次仍为 10 | 告知「占位超时，请稍后查询订单状态」       |

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method getOrderStatus --arg "{"orderBaseId": "SRO202603091138018328863"}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method getOrderStatus --arg-file temp/orderstatus_params.json
```

**参数说明**：

- `orderBaseId`: 订单号（从创建订单返回获取）

---

### 第七阶段：根据轮询结果反馈

根据第六阶段轮询得到的 status 分别处理：

#### 占位成功（status=12）

**成功反馈示例**（一行一行展示，勿用表格）：

```
🎉 占位成功！座位已为您预留

📋 订单信息
订单号：SRO202603031234567890
车次：G101 汉口 08:00 → 长沙南 09:15
日期：2026年3月8日
坐席：一等座
乘车人：张三
💰 费用：¥262 × 1人 = ¥262

⏰ 请在 30 分钟内完成支付
付款方式：12306 APP / 网页 / 窗口
```

#### 占位失败（status=11）

**失败反馈示例**：

```
❌ 占位失败，座位未能预留

可能原因：余票不足、网络波动等。

🔧 建议操作：
   1. 重新预订（可选择其他车次或坐席）
   2. 稍后再试

需要我帮您重新预订吗？
```

#### 占位超时（轮询 6 次仍为 10）

**超时反馈示例**：

```
⏳ 占位超时，系统处理较慢

订单号：SRO202603031234567890

建议您稍后通过「查询订单状态」确认是否占位成功，或选择重新预订。
```

---

### 第八阶段：取消订单（可选）

当用户表达取消火车订单意愿时，调用 `train.cancelOrder`。必填字段按接口文档，缺则提示。

**场景**：用户想预订其他车次，需先取消当前未支付订单。

**流程**：

1. 向用户确认：「检测到您有未支付的订单，是否需要取消后重新预订？」
2. 用户同意后执行取消
3. 取消成功后继续新流程

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method train.cancelOrder --arg "{"orderBaseId": "SRO202603091138018328863", "orderType": 0, "cancelReason": "不需要了", "terminalCode": "APP"}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method train.cancelOrder --arg-file temp/cancelorder_params.json
```

**参数说明**：

- `orderBaseId`: 订单号（必填）
- `orderType`: 订单类型，默认 2（火车票）
- `cancelReason`: 取消原因
- `orderType` : 订单类型 默认火车票 2
- `subOrderType` : 默认国内机票 DOMESTIC_TRAIN
- `terminalCode`: 终端类型，如 "APP"

**确认话术示例**（润色展示，一行一行展示，勿用表格）：

```
⚠️ 检测到您有未支付订单

订单号：SRO202603031325023495901
车次：G311 汉口 15:14 → 长沙南 16:25

如需预订其他车次，需先取消当前订单。

是否取消该订单？(y/n)
```

**取消成功**：「✅ 已为您提交取消申请，订单取消后将自动释放座位。」

---

### 第九阶段：查询订单历史

当用户表达"查看订单"、"我的订单"、"历史订单"等意图时，调用 `orderHistory`。必填字段 memberId 按接口文档，缺则提示。

**触发场景**：

- 用户说「查看我的火车票订单」
- 用户说「最近买过的火车票」
- 用户说「订单历史」

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method orderHistory --arg "{"memberId": "15d6676f6be54d5099b106abeeecfcd6"}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method orderHistory --arg-file temp/orderhistory_params.json
```

**参数说明**：

- `memberId`: 会员ID（从认证上下文中获取，通常无需询问）

**展示格式示例**（一行一行展示，勿用表格）：

```
📋 您的火车票订单历史

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

订单1：
  订单号：SRO202603091138018328863
  车次：G101 北京 → 上海
  日期：2026年3月10日 08:00 → 10:15
  状态：✅ 已完成
  金额：¥680

订单2：
  订单号：SRO202603091138018328864
  车次：G02 上海 → 北京
  日期：2026年3月5日 14:30 → 16:45
  状态：⏰ 待支付
  金额：¥720
  ⚠️ 请在 30 分钟内完成支付

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

共 2 个订单。如需查看详情，请回复订单号。
```

### 第十阶段：订单详情

当用户提供订单号或从订单列表中选择某个订单查看详情时，调用 `orderDetail`。必填字段 orderBaseId 按接口文档，缺则提示。

**触发场景**：

- 用户说「查看订单详情 FRO202603101234567890」
- 用户从订单历史中选择某个订单
- 用户说「查询这个订单的情况」

### 🔧 Python 调用命令

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method orderDetail --arg "{"orderBaseId": "FRO202603101234567890"}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method orderDetail --arg-file temp/orderdetail_params.json
```

**参数说明**：

- `orderBaseId`: 订单号（如 FRO202603101234567890）

**展示格式示例**（一行一行展示，勿用表格）：

```
📋 订单详情

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

订单号：FRO202603101234567890
订单状态：✅ 已出票
列车信息：
  车次号：CA1234
  日期：2026年3月10日（周一）
  时间：08:00 → 10:15
  坐席：二等座

乘客信息：
  张三（320***********1234）

费用明细：
  票面价：¥600
  ───────────────
  总金额：¥680

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如需退票，请回复「退票」。
```

### 第十一阶段：申请退票

当用户表达"退票"、"我要退票"、"申请退款"等意图时，按顺序调用 `orderHistory`、`orderDetail`、`orderDeduct`（核损）、`train.refund`。必填字段按接口文档，缺则提示。

**触发场景**：

- 用户说「退票」
- 用户说「我要申请退款」
- 用户说「取消这张机票」
- 用户说「张三要退票」或「张三和李四要退票」

**流程**：

**步骤1：确认订单号**

- 如果用户未提供订单号，先调用 `orderHistory` 获取订单列表，让用户选择
- 或者询问用户订单号

**步骤2：获取订单详情**

- 调用 `orderDetail` 获取订单信息，包括：
  - 乘客列表（passengerId、passengerName、ticketNo）
  - 订单项编号（orderItemNo）
  - 车次信息
- 展示订单信息供用户确认

**步骤3：判断退票类型**

- **refundType = 1（全额退票）**：用户未明确指定乘客，或说「全退」、「全部退票」
- **refundType = 2（部分退票）**：用户明确指定了部分乘客，如「张三退票」、「张三和李四退票」

**步骤4：收集退票信息**

- **全退场景**（refundType=1）：
  
  - 无需询问乘客，自动包含所有乘客
  - 退票原因：询问用户「退票原因是什么？」
- **部分退票场景**（refundType=2）：
  
  - 确认要退票的乘客：「请确认要退票的乘客：张三、李四」
  - 退票原因：询问用户「退票原因是什么？」

**步骤5：核损（orderDeduct）**

- 调用 `orderDeduct` 接口计算退票手续费和退款金额

### 🔧 Python 调用命令 - 核损

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method orderDeduct --arg "{"orderBaseId": "SRO202603091138018328863", "resourceType": 2, "refundType": 1, "applyType": 0, "reason": "行程变更", "deductItemList": [{"orderItemNo": "OI202603091441449321207", "passengerIdList": ["399"]}]}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method orderDeduct --arg-file temp/orderdeduct_params.json
```

**参数说明**：

- `orderBaseId`: 订单号
- `resourceType`: 资源类型，默认 2（火车票）
- `refundType`: 1-整单退，2-部分退
- `applyType`: 0-自愿退票，1-非自愿退票，默认 0
- `reason`: 退票原因
- `deductItemList`: 核损项目列表（必填）
  - `orderItemNo`: 订单项编号（从订单详情获取 取值`data.trainProductInfos.orderItemNo`）

  - `passengerIdList`: 需要退票的乘客ID列表
    * 全额退票：包含订单中所有乘客ID
    * 部分退票：只包含用户指定的乘客ID

**核损结果展示**（润色展示，一行一行展示，勿用表格）：

```
📊 核损结果

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

订单号：FRO202603101234567890
车次：G101 北京 → 上海
日期：2026年3月10日 08:00 → 10:15

退票乘客：
  张三 退票金额：¥580  手续费：¥100
  李四 退票金额：¥580  手续费：¥100
  王五 退票金额：¥580  手续费：¥100

────────────────────────────────────────
总计：
  原支付金额：¥2040
  退款金额：¥1740
  手续费：¥300

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

确认核损信息无误后，请回复「确认退票」。
```

**步骤6：用户确认核损**

- 用户确认核损信息后，才进入下一步提交退票申请

**步骤7：提交退票申请（train.refund）**

- 调用 `train.refund` 接口提交退票申请

### 🔧 Python 调用命令 - 申请退票

**命令格式（cmd）**：

```bash
python scripts/apiexe.py call --method train.refund --arg "{"orderBaseId": "SRO202603091138018328863", "refundType": 1, "amount": 479, "originAmount": 479, "orderPassengerIds": [316]}"
```

**命令格式（PowerShell）**：

```powershell
python scripts/apiexe.py call --method flight.refund --arg-file temp/trainrefund_params.json
```

**参数说明**：

- `orderBaseId`: 订单号（必填）
- `refundType`: 1-全额退票，2-部分退票（必填）
- `orderItemNo`: 订单项编号（从订单详情获取 取值从核损的`ddeductItemList[].orderItemNo`获取）
- `amount`: 从核损的`trainDeductInfo.totalRefundAmount`获取（退款金额）
- `originAmount`: 原金额
- `orderPassengerIds`: 订单使用人

**确认话术示例 - 全额退票**（润色展示，一行一行展示，勿用表格）：

```
⚠️ 退票确认

订单号：FRO202603101234567890
车次：G01 北京 → 上海
日期：2026年3月10日 08:00 → 10:15

乘客：
  张三（票号：7891234567890）
  李四（票号：7891234567891）
  王五（票号：7891234567892）

核损结果：
  退款金额：¥1740
  手续费：¥300

确认申请全额退票吗？(y/n)
```

**确认话术示例 - 部分退票**（润色展示，一行一行展示，勿用表格）：

```
⚠️ 退票确认

订单号：FRO202603101234567890
车次：G101 北京 → 上海
日期：2026年3月10日 08:00 → 10:15

退票乘客：
  张三（票号：7891234567890）
  李四（票号：7891234567891）

保留乘客：
  王五（票号：7891234567892）

退票类型：部分退票

核损结果：
  退款金额：¥1160
  手续费：¥200

确认申请部分退票吗？(y/n)
```

**退票申请提交成功**：

```
✅ 退票申请已提交

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

订单号：FRO202603101234567890
退款金额：¥1740
预计到账时间：3-7 个工作日

您可以通过「查询订单状态」查看退票进度。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

## 异常处理

### 核心原则

**当 API 调用异常时，不要让用户重复提供信息！**

用户已经选择的内容必须记住：

- ✅ 出发地和目的地
- ✅ 出发日期
- ✅ 选择的车次
- ✅ 选择的坐席
- ✅ 选择的乘车人

### 常见错误处理

**1. 接口返回异常**

```
❌ 获取车次详情时遇到系统异常
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

我已为您记录的选择：
  🚄 车次：G311 汉口 15:14 → 长沙南 16:25
  🪑 坐席：一等座 ¥319
  👥 乘车人：大明、刘斌

🔧 解决方案：
  ① 稍后 1–2 分钟我再重试
  ② 选择其他车次
  ③ 手动通过 12306 预订

您希望我如何处理？
```

**2. 资源不足/售罄**

```
❌ 该坐席已售罄
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

G311 一等座暂时无票，但还有以下选择：
  ✅ 二等座 ¥199  剩余 99 张
  ✅ 商务座 ¥576  剩余  4 张

🔄 其他车次（同一时间段）：G303、G319 有票

您希望：① 选择其他坐席  ② 选择其他车次  ③ 稍后再试
```

**3. 网络超时**

```
❌ 网络连接超时，可能是网络不稳定
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

我已为您记录的选择：[列出所有已选择的信息]

🔧 解决方案：
  ① 立即重试
  ② 稍后 2 分钟再试
  ③ 手动通过 12306 预订

我可以为您生成一份预订清单，方便您手动预订。
```

---

## 用户体验

### 对话风格

✅ **友好自然**：「好的，我来帮您查询武汉到长沙的车次！」
❌ **机械生硬**：「请提供出发城市、到达城市和出发日期。」

### 接口返回结果润色（重要）

收到接口返回后，**不要直接原样输出**，应对结果进行润色展示：

- **使用符号**：🚄 🪑 👥 📋 💰 ⏰ ✅ ❌ ⚠️ 等增强可读性
- **一行一行展示**：每条信息单独一行，**勿用表格、框线**（`│` `├` `┌` `└` 等），避免在不同界面展示错乱
- **适当留白**：信息块之间空行分隔，避免拥挤
- **引导语**：在信息块末尾加简短操作提示

### 信息展示

✅ **结构化清晰**：分块展示车次、坐席、乘车人、费用
❌ **信息堆砌**：整段文字挤在一起

### 错误处理

✅ **提供解决方案**：列出可选方案，让用户选择
❌ **只报错**：仅提示「错误：系统异常」

---

---

## 完整对话示例

```
用户: 我要买张火车票

助手: 好的，我来帮您预订火车票！
🚄 从哪个城市出发？

用户: 武汉

助手: 🎯 要去哪里？

用户: 长沙

助手: 📅 哪天出发？（可以说"明天"、"本周日"、"3月8日"等）

用户: 这周日

助手: 🚄 为您找到以下车次

📅 2026年3月8日 武汉 → 长沙

【推荐】G311 汉口 15:14 → 长沙南 16:25  1h11m ⭐
   💺 二等座 ¥199  一等座 ¥319  商务座 ¥576

用户: G311

助手: 🪑 G311 可选坐席

  ① 二等座 ¥199  剩余99张
  ② 一等座 ¥319  剩余11张
  ③ 商务座 ¥576  剩余4张

用户: 一等座

助手: 👥 请选择乘车人（可多选）

  ① 大明 (成人) 138****1313
  ② 刘斌 (成人) 150****3771

用户: 大明和刘斌

（若用户说「我要添加新乘客」「没有合适的人」等，则调用 save_passenger，引导输入姓名、证件类型、证件号、手机号，添加成功后再展示乘车人列表供选择）

（调用 train.createOrder 后，必须轮询 train.orderStatus，直到 status=12 占位成功）

助手: 🎉 占位成功！座位已为您预留

📋 订单信息
订单号：SRO202603031325023495901
车次：G311 汉口 15:14 → 长沙南 16:25
日期：2026年3月8日  坐席：一等座
乘车人：大明、刘斌
💰 费用：¥319 × 2人 = ¥638

⏰ 请在 30 分钟内完成支付
```

---

## 接口调用方式

Agent 识别用户意图后，查阅 [api/train.json](../api/train.json) 选择 method，按 `parameters` 构造 params，执行 `scripts/apiexe.py call --method <method> --arg '<params_json>'`。每次调用自动携带 auth 签名

## 多资源场景

若用户同时订购火车票和其他资源，先完成火车票订购流程，再引导用户处理下一个资源。

