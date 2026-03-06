# 机票订购操作指南

**触发条件**：见 [SKILL.md](../SKILL.md) 中「一、需求识别与分流」的机票触发示例。本指南在识别到用户要**预定或查询机票/航班**时按需加载。

---

## 必填字段收集原则（通用）

**不写死必填项**。识别到需要调用某个接口时：
1. 查阅 [api/plane.json](../api/plane.json) 中该 method 的 `parameters.required` 及 `properties`
2. 若用户未给出某必填字段，则提示用户必须填写
3. 每次只问一项缺项，待用户回复后再继续
4. 所有必填字段收集完整后再调用接口

---

## 核心下单接口链路

```
1. cityList（获取城市列表）→ 获取出发/到达城市的 cityId、flightCode
2. flightListV2（查询航班列表）→ 使用 depCityId、arrCityId、fromCity、toCity
3. cabinList（查询航班详情舱位列表）→ 使用 goFlight.flights.extData 作为 goExtData
4. getPassengerList（查询乘客）→ 若为空则调用 savePassenger 新增乘客
5. flight.createOrder（创建机票订单）→ items.resourceItemId 取自 cabinList 的 goFlightCabin.cabinList.resourceItemId
6. getOrderStatus（轮询订单状态）→ 占位完成后引导支付
```

---

## 完整交互流程

### 第一阶段：获取城市信息并收集基本信息

**先调用 `cityList`** 获取城市列表，用于后续航班查询。根据用户输入的出发地、目的地，从城市列表中匹配获取：
- `cityId`：用于航班列表的 depCityId、arrCityId
- `flightCode`：用于航班列表的 fromCity、toCity

**cityList 调用参数（机票场景）**：以 [api/plane.json](../api/plane.json) 为准，当前入参为：
- `domesticType`：国内/国际类型，默认国内。`1`=国内，`2`=国际；机票预订时通常传 `1`
- `resourceType`：资源类型。`0`=飞机，`1`=酒店，`2`=火车，`3`=门票；机票场景传 `0`

调用示例（获取国内飞机城市列表）：`scripts/apiexe.py call --method cityList --arg '{"domesticType":1,"resourceType":0}'`

**自然询问**，而非机械填表：

```
好的，我来帮您预订机票！
✈️ 从哪个城市出发？
🎯 要去哪里？
📅 哪天出发？（可以说"明天"、"本周六"、"3月10日"等）
```

**智能识别日期**：

| 用户输入 | 转换结果 |
|---------|---------|
| 今天/今日 | 当前日期 |
| 明天/明日 | 当前日期+1 |
| 后天、大后天 | 对应计算 |
| 下周一~下周日、这周一~这周日 | 计算对应日期 |
| 3月10日/3月10号/3-10 | 解析为 YYYYMMDD（如 20260310） |
| 5天后 | 当前日期+N |

**城市匹配**：用户说出城市名后，从 cityList 返回中查找对应城市的 cityId 和 flightCode，用于后续 flightListV2 调用。

---

### 第二阶段：展示航班选项

调用 `flightListV2`，必填字段按接口文档，缺则提示。

**参数映射**（来自 cityList）：
- `depCityId`、`arrCityId`：城市列表接口返回的 cityId
- `fromCity`、`toCity`：城市列表接口返回的 flightCode
- `fromDate`：出发日期，**格式 YYYYMMDD**（如 20260306，无横杠）
- `retDate`：回程日期（往返时必填），**格式 YYYYMMDD**
- `fromTimeRanges`、`toTimeRanges`：可选，时间段筛选；内部 `startTime`、`endTime` **格式 HH:mm**
- `cabinGrade`：舱位等级（0-不限，1-经济舱，2-商务舱/头等舱）
- `adultNum`、`childNum`：成人/儿童数量
- `tripType`：行程类型（1-单程，2-往返，3-多程）
- `fromCityType`、`toCityType`：1-机场，2-城市

**展示格式示例**（接口返回后润色展示，一行一行展示，勿用表格）：

```
✈️ 为您找到以下航班

📅 2026年3月10日 北京 → 上海

【推荐】CA1234 首都机场 08:00 → 虹桥机场 10:15  2h15m  ⭐ 直飞
   💺 经济舱 ¥680  公务舱 ¥1980

MU5678 首都机场 10:30 → 浦东机场 12:45  2h15m
   💺 经济舱 ¥720  公务舱 ¥2100

HU9012 首都机场 14:00 → 虹桥机场 16:20  2h20m  ⚡ 价格优
   💺 经济舱 ¥550  公务舱 ¥1650

回复航班号（如 CA1234）或时间偏好即可选择
```

**智能筛选和推荐**：
- 优先展示直飞航班
- 按时间或价格排序
- 标注热门航班、价格、舱位类型

**用户选择方式**：
- 说航班号：「CA1234」
- 说序号：「第1个」
- 说时间偏好：「早点的」「下午的」

---

### 第三阶段：确认舱位选择

用户选定航班后，调用 `cabinList` 获取舱位详情。

**cabinList 入参**（以 [api/plane.json](../api/plane.json) 为准）：
- `goExtData`：**必填**，取自航班列表接口返回的 `goFlight.flights[].extData`（用户选中的那条航班对应的 extData）
- `backExtData`：返程扩展数据，**单程传空字符串 `""`**，往返时传返程航班的 extData
- `adultNum`：成人数量（如 1）
- `childNum`：儿童数量（如 0）
- `cabinGrade`：舱位等级（**默认传 0**；0-不限，1-经济舱/超级经济舱，2-商务舱/头等舱）

调用示例（单程、1 成人、0 儿童、不限舱位）：  
`scripts/apiexe.py call --method cabinList --arg '{"goExtData":"<goFlight.flights[].extData>","backExtData":"","adultNum":1,"childNum":0,"cabinGrade":0}'`

从返回中获取 `goFlightCabin.cabinList.resourceItemId`、各舱位价格、余票，供下单使用。

**展示格式示例**（接口返回后润色展示，一行一行展示，勿用表格）：

```
💺 CA1234 可选舱位

  ① 经济舱  ¥680  剩余 9 张  适合大多数出行
  ② 超级经济舱  ¥880  剩余 5 张  更宽敞舒适
  ③ 公务舱  ¥1980  剩余  3 张  顶级体验

请选择舱位类型（如：经济舱、公务舱）
```

---

### 第四阶段：选择乘客

调用 `getPassengerList` 获取乘客列表。必填字段按接口文档，缺则提示。`orderType` 需传入机票订单类型。

**展示格式示例**（接口返回后润色展示，一行一行展示，勿用表格）：

```
👥 请选择乘客（可多选）

【最近使用】
  ① 张三  138****1234
  ② 李四  139****5678

【全部联系人】
  ③ 王五  150****5000

回复序号或姓名，如「1」「张三」或「1,2」「张三、李四」
```

**乘客列表为空时**：提示用户添加乘客信息，调用 `savePassenger` 接口。

**savePassenger 入参**（以 [api/plane.json](../api/plane.json) 为准）：
- **必填**：`passengerName`（旅客姓名）、`identityNo`（证件/身份证号）、`phoneNumber`（手机号码）
- **可选**：其他字段（pinyinName、passengerType、gender、birthday、identityType、nationality、phoneCountryCode、status）可不传

**引导与收集**：只收集三项必填——「请问乘客姓名？」「请输入身份证号」「请输入手机号」。收集完整后调用接口，其他字段不传。

**调用示例**：
`scripts/apiexe.py call --method savePassenger --arg '{"passengerName":"李四","identityNo":"420984198803017743","phoneNumber":"13000000000"}'`

- 添加成功后，再次调用 `getPassengerList` 刷新列表，继续乘客选择流程。

**乘客信息字段**：必填为姓名、身份证号、手机号；其余可选不传。

---

### 第五阶段：下单占位

调用 `flight.createOrder`。入参以 [api/plane.json](../api/plane.json) 为准，**按下列结构传参**：

**顶层必传**：memberId、userName（可空）、phoneNumber、email（可空）、orderSource（如 0）、orderType（如 0）、subOrderType（`FLIGHT_SINGLE`）、tripType（1 单程）、fromDate（YYYY-MM-DD）、returnDate（单程传空）、totalAmount、payAmount（= 票面+机建+燃油，如 970）、items、contact、departureCityId、destinationCityId。

**contact**：对象，字段可传空字符串：address、email、name、phone、postcode；phone 建议填下单人手机号。

**items[]** 每条需包含：
- resourceItemId、sessionId、goExtData、adultNum、childNum、adultSalePrice、adultAirportFee、adultOilFee、childSalePrice、childAirportFee、childOilFee、cabinGrade（1 经济舱 2 商务/头等）；
- **goExtData**：取**舱位详情** `goFlightCabin.cabinList[].extData` 的**整段 JSON 字符串**（不是航班列表的 extData 短码）；
- **passengers[]**：从 getPassengerList 选中项构造，含 passengerId、name、idNumber、idType、phoneNumber、customerType（0 成人）、birthday；gender、nationality、pinyinname 可传空字符串；
- departCityName、departCityCode（如 BJS）、arriveCityName、arriveCityCode（如 SHA）、quantity（1）、rangeType（1 去程）；
- **contact**：本段联系人，字段可空，phone 建议与顶层一致；
- departureDate、departureTime（如 07:25）、flightNumber（如 HU7601）、departureCityName、arrivalCityName。

**departureCityId / destinationCityId**：出发地/目的地城市 id（字符串），如北京=4、上海=785，可从城市列表或业务约定取值。

**重要**：创建订单成功后，订单处于**占位中**状态，此时**必须**进入第六阶段轮询订单状态，根据轮询结果再决定后续反馈，切勿直接提示用户支付。

---

### 第六阶段：订单状态轮询（必执行）

下单成功后，订单处于占位中，**必须**有限次数轮询 `getOrderStatus`，直到得到明确结果。必填字段 orderBaseId 从 flight.createOrder 返回的 data.orderBaseId 获取。

- **轮询间隔**：10 秒
- **最大轮询次数**：6 次（最多等待约 1 分钟）

**状态码与处理**：

| 状态码 | 含义 | Agent 处理 |
|--------|------|-------------|
| `10` | 处理中 | 继续轮询，可提示「正在为您占位，请稍候…」 |
| `12` | 占位完成 | 进入第七阶段，展示成功反馈并提醒支付 |
| `11` | 占位失败 | 进入第七阶段，展示失败反馈并引导重新预订 |
| 超时 | 轮询 6 次仍为 10 | 告知「占位超时，请稍后查询订单状态」 |

---

### 第七阶段：根据轮询结果反馈

根据第六阶段轮询得到的 status 分别处理：

#### 占位成功（status=12）

**成功反馈示例**（一行一行展示，勿用表格）：

```
🎉 占位成功！座位已为您预留

📋 订单信息
订单号：FRO202603101234567890
航班：CA1234 首都机场 08:00 → 虹桥机场 10:15
日期：2026年3月10日
舱位：经济舱
乘客：张三
💰 费用：¥680 × 1人 = ¥680

⏰ 请在 30 分钟内完成支付
付款方式：APP / 网页 / 柜台
```

#### 占位失败（status=11）

**失败反馈示例**：

```
❌ 占位失败，座位未能预留

可能原因：余票不足、网络波动等。

🔧 建议操作：
   1. 重新预订（可选择其他航班或舱位）
   2. 稍后再试

需要我帮您重新预订吗？
```

#### 占位超时（轮询 6 次仍为 10）

**超时反馈示例**：

```
⏳ 占位超时，系统处理较慢

订单号：FRO202603101234567890

建议您稍后通过「查询订单状态」确认是否占位成功，或选择重新预订。
```

---

### 第八阶段：取消订单（可选）

当用户表达取消机票订单意愿时，调用 `flight.cancelOrder`。必填字段 orderBaseId 按接口文档，缺则提示。

**场景**：用户想预订其他航班，需先取消当前未支付订单。

**流程**：
1. 向用户确认：「检测到您有未支付的订单，是否需要取消后重新预订？」
2. 用户同意后执行取消
3. 取消成功后继续新流程

**确认话术示例**（润色展示，一行一行展示，勿用表格）：

```
⚠️ 检测到您有未支付订单

订单号：FRO202603101325023495901
航班：CA1234 首都机场 08:00 → 虹桥机场 10:15

如需预订其他航班，需先取消当前订单。

是否取消该订单？(y/n)
```

**取消成功**：「✅ 已为您提交取消申请，订单取消后将自动释放座位。」

---

## 接口清单与数据流

| 阶段 | 接口 | 关键入参 | 关键出参 |
|------|------|----------|----------|
| 1 | cityList | domesticType、resourceType（机票：domesticType=1, resourceType=0） | cityId、flightCode |
| 2 | flightListV2 | depCityId、arrCityId、fromCity、toCity、fromDate | goFlight.flights.extData |
| 3 | cabinList | goExtData、backExtData、adultNum、childNum、cabinGrade（goExtData=goFlight.flights[].extData，单程 backExtData=""） | goFlightCabin.cabinList.resourceItemId |
| 4 | getPassengerList | orderType | 乘客列表 |
| 4 | savePassenger | passengerName、identityNo、phoneNumber（仅此三项必填） | 新增乘客 |
| 5 | flight.createOrder | items.resourceItemId、passengers、contact 等 | orderBaseId |
| 6 | getOrderStatus | orderBaseId | status |
| 8 | flight.cancelOrder | orderBaseId | 取消结果 |

---

## 异常处理

### 核心原则

**当 API 调用异常时，不要让用户重复提供信息！**

用户已经选择的内容必须记住：
- ✅ 出发地和目的地
- ✅ 出发日期
- ✅ 选择的航班
- ✅ 选择的舱位
- ✅ 选择的乘客

### 常见错误处理

**1. 接口返回异常**

```
❌ 获取航班详情时遇到系统异常
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

我已为您记录的选择：
  ✈️ 航班：CA1234 首都机场 08:00 → 虹桥机场 10:15
  💺 舱位：经济舱 ¥680
  👥 乘客：张三、李四

🔧 解决方案：
  ① 稍后 1–2 分钟我再重试
  ② 选择其他航班
  ③ 手动通过航司或 OTA 预订

您希望我如何处理？
```

**2. 舱位售罄**

```
❌ 该舱位已售罄
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CA1234 经济舱暂时无票，但还有以下选择：
  ✅ 超级经济舱 ¥880  剩余 5 张
  ✅ 公务舱 ¥1980  剩余 3 张

🔄 其他航班（同一时间段）：MU5678、HU9012 有票

您希望：① 选择其他舱位  ② 选择其他航班  ③ 稍后再试
```

**3. 网络超时**

```
❌ 网络连接超时，可能是网络不稳定
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

我已为您记录的选择：[列出所有已选择的信息]

🔧 解决方案：
  ① 立即重试
  ② 稍后 2 分钟再试
  ③ 手动通过航司或 OTA 预订

我可以为您生成一份预订清单，方便您手动预订。
```

---

## 用户体验

### 对话风格

✅ **友好自然**：「好的，我来帮您查询北京到上海的航班！」
❌ **机械生硬**：「请提供出发城市、到达城市和出发日期。」

### 接口返回结果润色（重要）

收到接口返回后，**不要直接原样输出**，应对结果进行润色展示：

- **使用符号**：✈️ 💺 👥 📋 💰 ⏰ ✅ ❌ ⚠️ 等增强可读性
- **一行一行展示**：每条信息单独一行，**勿用表格、框线**（`│` `├` `┌` `└` 等），避免在不同界面展示错乱
- **适当留白**：信息块之间空行分隔，避免拥挤
- **引导语**：在信息块末尾加简短操作提示

### 信息展示

✅ **结构化清晰**：分块展示航班、舱位、乘客、费用
❌ **信息堆砌**：整段文字挤在一起

### 错误处理

✅ **提供解决方案**：列出可选方案，让用户选择
❌ **只报错**：仅提示「错误：系统异常」

---

## 完整对话示例

```
用户: 我要买张机票

助手: 好的，我来帮您预订机票！
✈️ 从哪个城市出发？

用户: 北京

助手: 🎯 要去哪里？

用户: 上海

助手: 📅 哪天出发？（可以说"明天"、"本周六"、"3月10日"等）

用户: 这周六

助手: ✈️ 为您找到以下航班

📅 2026年3月8日 北京 → 上海

【推荐】CA1234 首都机场 08:00 → 虹桥机场 10:15  2h15m ⭐
   💺 经济舱 ¥680  公务舱 ¥1980

用户: CA1234

助手: 💺 CA1234 可选舱位

  ① 经济舱 ¥680  剩余9张
  ② 公务舱 ¥1980  剩余3张

用户: 经济舱

助手: 👥 请选择乘客（可多选）

  ① 张三 138****1313
  ② 李四 150****3771

用户: 张三

（若用户说「我要添加新乘客」「没有合适的人」等，则调用 savePassenger，仅收集必填三项：姓名、身份证号、手机号，添加成功后再展示乘客列表供选择）

（调用 flight.createOrder 后，必须轮询 getOrderStatus，直到 status=12 占位完成）

助手: 🎉 占位成功！座位已为您预留

📋 订单信息
订单号：FRO202603081325023495901
航班：CA1234 首都机场 08:00 → 虹桥机场 10:15
日期：2026年3月8日  舱位：经济舱
乘客：张三
💰 费用：¥680 × 1人 = ¥680

⏰ 请在 30 分钟内完成支付
```

---

## 接口调用方式

Agent 识别用户意图后，查阅 [api/plane.json](../api/plane.json) 选择 method，按 `parameters` 构造 params，执行 `scripts/apiexe.py call --method <method> --arg '<params_json>'`。每次调用自动携带 auth 签名。tools/call 入参结构为：`method`（含 category、subCategory、action）、`params`、`auth`。

## 多资源场景

若用户同时订购机票和其他资源，先完成机票订购流程，再引导用户处理下一个资源。
