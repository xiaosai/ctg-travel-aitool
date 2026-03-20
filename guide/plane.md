# 机票订购操作指南

**触发条件**：购买/查询/预订机票、航班、飞机票

---

## 核心流程

```
1. flightListV2 → 查询航班列表，入参：fromCityName、toCityName、fromDate
2. cabinList → 获取舱位详情，入参：goExtData(航班列表返回的 extData)
3. getPassengerList(orderType=0) → 乘客列表；无乘客则调用 savePassenger 新增
4. flight.createOrder → 创建订单，入参：items(resourceItemId、goExtData、passengers 等)
5. getOrderStatus → 轮询订单状态（占位中 → 成功/失败）
6. orderDetail → 查询订单详情
7. flight.cancelOrder → 取消未支付订单（仅取消未支付订单，已支付需走退票流程）
8. orderHistory → 获取历史订单
```

---

## 参数传递依赖

| 接口 | 入参来源                                                                                                                                                                                        |
|------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| cabinList | `goExtData` ← flightListV2 返回的 `goFlight.flights[].extData`                                                                                                                                 |
| flight.createOrder | `resourceItemId` ← cabinList 返回的 `goFlightCabin.cabinList[].resourceItemId`<br>`goExtData` ← flightListV2 返回的 `goFlight.flights[].extData`<br>`passengerIds` ← getPassengerList 返回的乘客信息id列表<br>`contactPhone` ← 用户提供的联系手机号 |

---

## 关键参数说明

### flightListV2 返参
- `goFlight.flights[]`：航班列表
  - `extData`：扩展数据（舱位查询用）
  - `flightNo`：航班号
  - `depTime`、`arrTime`：起降时间

### cabinList 返参
- `sessionId`：会话ID（下单必用）
- `goFlightCabin.cabinList[]`：舱位列表
  - `resourceItemId`：资源项ID（下单必用）
  - `extData`：扩展数据（下单必用，整段 JSON 字符串）
  - `sellPrice`：售价
  - `airportFee`：机建费
  - `oilFee`：燃油费

### 创建订单注意事项
- `goExtData`：取**舱位详情**的 `goFlightCabin.cabinList[].extData`（整段 JSON 字符串，需转义）
- `sessionId`：必须放在 `items[].sessionId` 中
- 下单后**必须轮询**订单状态，直到占位完成或失败

### 订单状态码
| 状态码  | 含义 | 处理 |
|------|------|------|
| `1`  | 处理中 | 继续轮询，提示「正在为您占位，请稍候…」 |
| `10` | 占位完成 | 展示成功，提醒支付 |
| `9`  | 占位失败 | 展示失败，引导重新预订 |

---

## 调用命令示例

```bash
# 航班列表（必填：fromCityName, toCityName, fromDate）
python scripts/apiexe.py call --method flightListV2 --arg "{\"fromCityName\": \"武汉\", \"fromDate\": \"2026-03-15\", \"toCityName\": \"上海\"}"

# 舱位详情（必填：goExtData, adultNum, childNum, cabinGrade）
python scripts/apiexe.py call --method cabinList --arg "{\"goExtData\": \"73026665108161745-1\"}"

# 乘客列表
python scripts/apiexe.py call --method getPassengerList --arg "{\"orderType\": 0}"

# 新增乘客（必填：passengerName, identityNo, phoneNumber）
python scripts/apiexe.py call --method savePassenger --arg "{\"passengerName\": \"张三\", \"identityType\": \"ID\", \"identityNo\": \"420102199007015297\", \"phoneNumber\": \"13800138000\"}"

# 创建订单（必填：memberId, phoneNumber, orderSource, orderType, subOrderType, tripType, fromDate, totalAmount, payAmount, items, contact, departureCityId, destinationCityId）
python scripts/apiexe.py call --method flight.createOrder --arg "{\"resourceItemId\": \"xxx\", \"goExtData\": \"73026665108161745-1\",  \"passengers\": [11,21], \"contactPhone\":\"13801138001\"}"

# 订单状态轮询（必填：orderBaseId）
python scripts/apiexe.py call --method getOrderStatus --arg "{\"orderBaseId\": \"FRO202603151234567890\"}"

# 订单详情（必填：orderBaseId）
python scripts/apiexe.py call --method orderDetail --arg "{\"orderBaseId\": \"FRO202603151234567890\"}"

# 取消订单（必填：orderBaseId，仅未支付）
python scripts/apiexe.py call --method flight.cancelOrder --arg "{\"orderBaseId\": \"FRO202603151234567890\", \"orderType\": 0}"

# 订单历史（必填：memberId）
python scripts/apiexe.py call --method orderHistory --arg "{\"memberId\": \"xxx\"}"
```

### passengers 结构（flight.createOrder 必填）
```json
[{
  "passengerId": 1,
  "name": "张三",
  "idNumber": "420102...",
  "idType": "ID",
  "phoneNumber": "138...",
  "customerType": "0",
  "birthday": "1990-07-01"
}]
```

---

## 展示格式参考

**航班列表**：一行一行展示，格式「① CA1234 首都机场 08:00 → 虹桥机场 10:15  2h15m  💺 经济舱 ¥680」

**舱位列表**：格式「① 经济舱  ¥680  剩余 9 张」

**订单详情**：订单号、航班、日期、乘客、舱位、状态、金额

**订单创建成功**：展示订单信息后，提示「请前往「中旅旅行」App 完成支付」

---

## 异常处理

- **后台异常**：保留用户已选内容，提示稍后重试
- **航班列表为空**：建议换日期/换航线
- **舱位售罄**：建议选择其他舱位或航班
- **网络超时**：提示稍后重试或前往中旅旅行App

**重要**：异常时不要让用户重复提供信息，已选择的内容必须记住。

---

## 退票流程

- 当用户明确表达退票、我要退票、申请退款、取消这张机票（已支付）意图时，加载 [guide/plane-refund.md](plane-refund.md)
