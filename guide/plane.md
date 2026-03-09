# 机票订购操作指南

**触发条件**：见 [SKILL.md](../SKILL.md) 中「一、需求识别与分流」的机票触发示例。本指南在识别到用户要**预定或查询机票/航班**时按需加载。

---

## 必填字段收集原则（通用）

**不写死必填项**。在需要向后台发起请求时：
1. 查阅 [api/plane.json](../api/plane.json) 中对应 method 的 `parameters.required` 及 `properties`
2. 若用户未给出某必填字段，用自然语言提示用户填写（勿说「请提供某某参数」）
3. 每次只问一项缺项，待用户回复后再继续
4. 所有必填字段收集完整后再发起请求

**面向用户的话术**：对用户说的内容禁止出现「调用某某接口」「请求 API」「getPassengerList」等任何技术用语，一律使用「正在为您查询…」「请选择乘客」等业务话术。

---

## 退票场景智能识别

**用户表达意图识别**：

| 用户输入 | refundType | 说明 |
|---------|-----------|------|
| 「退票」「我要退票」「取消这张机票」 | 1（全额退票） | 未指定乘客，默认全退 |
| 「全退」「全部退票」「三个人都要退」 | 1（全额退票） | 明确全额退票 |
| 「张三退票」「退张三的票」 | 2（部分退票） | 指定了单个乘客 |
| 「张三和李四退票」「退张三和李四」 | 2（部分退票） | 指定了部分乘客 |
| 「只退王五」「王五一个人退票」 | 2（部分退票） | 指定了单个乘客 |

**处理流程**：
1. 识别用户意图 → 判断是否为退票场景
2. 获取订单信息（orderHistory 或 orderDetail）
3. 根据用户输入判断 refundType：
    - 全退：所有乘客纳入 refundItemList
    - 部分退：仅用户指定的乘客纳入 refundItemList
4. 收集退票原因（必填）
5. 计算或确认退款金额（必填）
6. 向用户确认后提交

---

## 核心步骤与数据流（Agent 内部参考，勿对用户说）

以下为内部执行顺序与数据依赖，**向用户展示时只用业务话术**（如「正在查航班」「正在占位」），不得出现接口名、API、method 等。

```
1. 获取城市列表 → 得到出发/到达城市的 cityId、flightCode
2. 查询航班列表 → 使用 depCityId、arrCityId、fromCity、toCity
3. 查询航班舱位详情 → 使用航班列表返回的 goFlight.flights.extData 作为 goExtData
4. 查询乘客列表 → 若为空则先新增乘客再继续
5. 创建机票订单 → items.resourceItemId 取自舱位详情的 goFlightCabin.cabinList.resourceItemId
6. 轮询订单状态 → 占位完成后引导用户支付
```

---

## 退票接口调用链路

```
1. orderHistory（获取订单历史）→ 获取用户的机票订单列表
2. orderDetail（获取订单详情）→ 根据订单号获取详细信息，包括乘客列表和票号
3. orderDeduct（核损）→ 核算退票手续费和退款金额（退票前必调）
4. flight.refund（申请退票）→ 用户确认核损信息后提交退票申请

关键参数说明：
- refundType：根据用户输入判断
  * 用户未明确指定乘客 → refundType=1（全额退票）
  * 用户明确指定部分乘客（如「张三退票」）→ refundType=2（部分退票）
- deductItemList：核损项目列表（必填），每项包含：
  * orderItemNo：订单项编号（从订单详情获取，取值 `data.flightProductInfos.items[].orderItemNo`）
  * passengerIdList：需要退票的乘客ID列表
    * 全额退票：包含订单中所有乘客ID
    * 部分退票：只包含用户指定的乘客ID
- resourceType：资源类型，默认传 0（机票）
- applyType：退款类型，默认传 1（自愿退票）
- reason：退票原因（如"自愿退票"）
- amount：退款金额（必填）- 从核损结果获取的 totalRefundAmount
- originAmount：原支付金额（必填）- 从订单详情获取
- reasonType：原因类型（必填），默认传 0
- memberId：会员ID（必填）- 从认证上下文获取
- refundItemList：退票乘客明细（必填），每项包含：
  * orderItemNo：订单项编号（从订单详情获取，与核损接口使用相同值）
  * orderPassengerIds：乘客ID数组（如 [264]，注意是数组格式）
  * refundQuantity：退票数量（如 1）
  * refundAmount：退票手续费（必填，从核损结果获取）
    * 注意：这是手续费金额，不是退款金额！退款金额是 amount
```

---

## 完整交互流程

### 第一阶段：获取城市信息并收集基本信息

**内部**：先获取城市列表，用于后续航班查询。根据用户输入的出发地、目的地，从城市列表中匹配：
- `cityId`：用于航班列表的 depCityId、arrCityId
- `flightCode`：用于航班列表的 fromCity、toCity

**请求参数（机票场景）**：以 [api/plane.json](../api/plane.json) 为准，国内机票入参示例：`domesticType=1`、`resourceType=0`。具体见 api 文档。

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method cityList --arg "{\"domesticType\": 1, \"resourceType\": 0}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method cityList --arg-file temp/citylist_params.json
```

**参数说明**：
- `domesticType`: 国内/国际类型，默认国内 1（国内）2（国际）
- `resourceType`: 资源类型，默认 0（飞机=0, 酒店=1, 火车=2, 门票=3）

**注意事项**：
- cmd 执行前需先切换到项目目录
- JSON 参数中的双引号在 cmd 中需要转义为 `\"`
- PowerShell 使用 `--arg-file` 可以避免参数转义问题

**对用户的说法**（自然询问，不要机械填表）：

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

**城市匹配**：用户说出城市名后，从城市列表返回结果中查找对应城市的 cityId 和 flightCode，用于下一步查询航班。

---

### 第二阶段：展示航班选项

查询航班列表，必填字段按 [api/plane.json](../api/plane.json)，缺则向用户自然追问（勿说「缺少 fromDate 参数」等）。

**参数映射**（来自城市列表结果）：
- `depCityId`、`arrCityId`：城市列表返回的 cityId
- `fromCity`、`toCity`：城市列表返回的 flightCode
- `fromDate`：出发日期，**格式 YYYYMMDD**（如 20260306，无横杠）
- `retDate`：回程日期（往返时必填），**格式 YYYYMMDD**
- `fromTimeRanges`、`toTimeRanges`：可选，时间段筛选；内部 `startTime`、`endTime` **格式 HH:mm**
- `cabinGrade`：舱位等级（0-不限，1-经济舱，2-商务舱/头等舱）
- `adultNum`、`childNum`：成人/儿童数量
- `tripType`：行程类型（1-单程，2-往返，3-多程）
- `fromCityType`、`toCityType`：1-机场，2-城市

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method flightListV2 --arg "{\"cabinGrade\": 0, \"adultNum\": 1, \"childNum\": 0, \"fromCity\": \"WUH\", \"fromCityType\": 2, \"fromDate\": \"20260311\", \"toCity\": \"SHA\", \"toCityType\": 2, \"tripType\": 1}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method flightListV2 --arg-file temp/flightlist_params.json
```

**关键参数说明**：
- `fromCity`、`toCity`: 出发地/目的地城市代码（如 WUH 武汉、SHA 上海）
- `fromDate`: 出发日期，格式 YYYYMMDD（如 20260311）
- `tripType`: 行程类型（1-单程，2-往返，3-多程）
- `adultNum`、`childNum`: 成人/儿童数量

**注意事项**：
- `fromDate` 格式必须为 YYYYMMDD，无横杠
- `fromCityType`、`toCityType`: 1-机场，2-城市（建议用2-城市）

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

用户选定航班后，查询该航班的舱位与价格。

**入参**（以 [api/plane.json](../api/plane.json) 为准）：
- `goExtData`：**必填**，取自航班列表返回的 `goFlight.flights[].extData`（用户选中的那条航班对应的 extData）
- `backExtData`：返程扩展数据，**单程传空字符串 `""`**，往返时传返程航班的 extData
- `adultNum`：成人数量（如 1）
- `childNum`：儿童数量（如 0）
- `cabinGrade`：舱位等级（**默认传 0**；0-不限，1-经济舱/超级经济舱，2-商务舱/头等舱）

从返回中获取 `goFlightCabin.cabinList.resourceItemId`、各舱位价格、余票，供下单使用。

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method cabinList --arg "{\"goExtData\": \"73026665108161745-1\", \"backExtData\": \"\", \"adultNum\": 1, \"childNum\": 0, \"cabinGrade\": 0}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method cabinList --arg-file temp/cabinlist_params.json
```

**关键参数说明**：
- `goExtData`: 航班列表返回的 `goFlight.flights[].extData`（航班列表中的短码）
- `backExtData`: 返程扩展数据，单程传空字符串 `""`
- `cabinGrade`: 舱位等级，0-不限，1-经济舱/超级经济舱，2-商务舱/头等舱

**注意事项**：
- `goExtData` 取自航班列表，是短码格式（如 "73026665108161745-1"）
- 下单时用的是舱位详情中的 `goFlightCabin.cabinList[].extData`（整段 JSON 字符串），注意区分

**展示格式示例**（将后台结果润色后这样展示给用户，一行一行展示，勿用表格）：

```
💺 CA1234 可选舱位

  ① 经济舱  ¥680  剩余 9 张  适合大多数出行
  ② 超级经济舱  ¥880  剩余 5 张  更宽敞舒适
  ③ 公务舱  ¥1980  剩余 3 张  顶级体验

请选择舱位类型（如：经济舱、公务舱）
```

---

### 第四阶段：选择乘客

获取乘客列表，必填项按 [api/plane.json](../api/plane.json)，缺则向用户自然追问。机票场景需传 `orderType`（机票订单类型）。

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method getPassengerList --arg "{\"orderType\": 0}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method getPassengerList --arg-file temp/passengerlist_params.json
```

**参数说明**：
- `orderType`: 订单类型，默认 0（机票）

**展示格式示例**（将后台结果润色后这样展示给用户，一行一行展示，勿用表格）：

```
👥 请选择乘客（可多选）

【最近使用】
  ① 张三  138****1234
  ② 李四  139****5678

【全部联系人】
  ③ 王五  150****5000

回复序号或姓名，如「1」「张三」或「1,2」「张三、李四」
```

**乘客列表为空时**：用自然话术提示用户添加乘客（如「还没有常用乘客，请先填写一位出行人信息」），收集姓名、身份证号、手机号三项后发起保存乘客请求。

### 🔧 Python 调用命令 - 新增乘客

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method savePassenger --arg "{\"passengerName\": \"张三\", \"identityType\": \"ID\", \"identityNo\": \"420102199007015297\", \"phoneNumber\": \"15629199695\"}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method savePassenger --arg-file temp/savepassenger_params.json
```

**保存乘客必填项**（以 [api/plane.json](../api/plane.json) 为准）：旅客姓名、证件/身份证号、手机号码。其他字段可选不传。

**对用户的引导**：只问三项——「请问乘客姓名？」「请输入身份证号」「请输入手机号」。收集完整后执行保存。

- 保存成功后，再次获取乘客列表，继续让用户选择乘客。

---

### 第五阶段：下单占位

创建机票订单。入参以 [api/plane.json](../api/plane.json) 为准，**按文档结构传参**：

**顶层必传**：memberId、userName（可空）、phoneNumber、email（可空）、orderSource（如 0）、orderType（如 0）、subOrderType（`FLIGHT_SINGLE`）、tripType（1 单程）、fromDate（YYYY-MM-DD）、returnDate（单程传空）、totalAmount、payAmount（= 票面+机建+燃油，如 970）、items、contact、departureCityId、destinationCityId。

**contact**：对象，字段可传空字符串：address、email、name、phone、postcode；phone 建议填下单人手机号。

**items[]** 每条需包含：
- resourceItemId、sessionId、goExtData、adultNum、childNum、adultSalePrice、adultAirportFee、adultOilFee、childSalePrice、childAirportFee、childOilFee、cabinGrade（1 经济舱 2 商务/头等）；
- **goExtData**：取**舱位详情** `goFlightCabin.cabinList[].extData` 的**整段 JSON 字符串**（不是航班列表的 extData 短码）；
- **sessionId**：取**舱位详情** `data.sessionId` ，`sessionId` 必须放在 `items` 数组内的每个 `item` 对象中，而不是请求体的根级别；
- **passengers[]**：从 getPassengerList 选中项构造，含 passengerId、name、idNumber、idType、phoneNumber、customerType（0 成人）、birthday；gender、nationality、pinyinname 可传空字符串；
- departCityName、departCityCode（如 BJS）、arriveCityName、arriveCityCode（如 SHA）、quantity（1）、rangeType（1 去程）；
- **contact**：本段联系人，字段可空，phone 建议与顶层一致；
- departureDate、departureTime（如 07:25）、flightNumber（如 HU7601）、departureCityName、arrivalCityName。

**departureCityId / destinationCityId**：出发地/目的地城市 id（字符串），如北京=4、上海=785，可从城市列表或业务约定取值。

**重要**：订单创建成功后处于**占位中**，**必须**进入第六阶段轮询订单状态，根据结果再决定提示用户支付或失败重试，切勿未轮询就提示用户支付。

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method flight.createOrder --arg "{\"memberId\": \"15d6676f6be54d5099b106abeeecfcd6\", \"userName\": \"\", \"phoneNumber\": \"15000000000\", \"distributor\": 0, \"orderSource\": 0, \"email\": \"\", \"orderType\": 0, \"subOrderType\": \"FLIGHT_SINGLE\", \"serviceFee\": 0, \"contact\": {\"address\": \"\", \"email\": \"\", \"name\": \"\", \"phone\": \"15000000000\", \"postcode\": \"\"}, \"tripType\": 1, \"fromDate\": \"2026-03-11\", \"returnDate\": \"\", \"totalAmount\": 479, \"payAmount\": 479, \"departureCityId\": \"1669\", \"destinationCityId\": \"785\", \"items\": [{\"resourceItemId\": \"FGde8bd5d6e73e43f7897e302b039c0f36\", \"goExtData\": \"{\\\"flightInfoId\\\":\\\"SXBHVy1Jb3BHdHR2SEJOSUNHWHRMSC10SklvR\\\",\\\"flightParam\\\":\\\"wC08Hw9V+ojuUDcPW1CoS7Y0yNQ/\\\",\\\"priceInfoId\\\":\\\"i9_3_4{G}5{631}8{CN_KM_ZHIVCGW}9{Gv4PJHk3qt||}0{}1{}2{}43{}44{}46{GCEB}47{}48{}49{}40{},prnve-aqp-qbzrfgvp,742.3!742.3\\\"}\", \"adultNum\": 1, \"childNum\": 0, \"sessionId\": \"EPVO73027446302667965\", \"adultSalePrice\": 419, \"adultAirportFee\": 50, \"adultOilFee\": 10, \"childSalePrice\": 0, \"childAirportFee\": 0, \"childOilFee\": 0, \"cabinGrade\": 1, \"passengers\": [{\"passengerId\": 399, \"name\": \"周刘\", \"idNumber\": \"420984199802090112\", \"idType\": \"ID\", \"phoneNumber\": \"15000000000\", \"customerType\": \"0\", \"birthday\": \"1998-02-09\", \"gender\": \"\", \"nationality\": \"\", \"pinyinname\": \"\"}], \"departCityName\": \"武汉\", \"departCityCode\": \"WUH\", \"arriveCityName\": \"上海\", \"arriveCityCode\": \"SHA\", \"quantity\": 1, \"rangeType\": 1, \"contact\": {\"address\": \"\", \"email\": \"\", \"name\": \"\", \"phone\": \"15000000000\", \"postcode\": \"\"}, \"departureDate\": \"2026-03-11\", \"departureTime\": \"08:05\", \"flightNumber\": \"MU2503\", \"departureCityName\": \"武汉\", \"arrivalCityName\": \"上海\"}]}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method flight.createOrder --arg-file temp/createorder_params.json
```

**关键参数说明**：
- `totalAmount`、`payAmount`: 总金额（票面价+机建费+燃油费）
- `sessionId`: 取自舱位详情的 `data.sessionId`
- `goExtData`: 取自舱位详情的 `data.goFlightCabin.cabinList[].extData`（整段 JSON 字符串，需转义双引号）
- `resourceItemId`: 取自舱位详情的`data.goFlightCabin.cabinList[].resourceItemId`
- `child*Price`: 儿童票面价、机建费、燃油费取自舱位详情的`data.goFlightCabin.cabinList[].child*`

**注意事项**：
- `goExtData` 中的双引号在 cmd 中必须转义为 `\"`
- 建议使用 `--arg-file` 参数文件方式，避免 cmd 转义问题
- `sessionId` 必须放在 `items` 数组内的每个 `item` 对象中
- 订单创建成功后会返回 `orderBaseId`，用于后续轮询订单状态

---

### 第六阶段：订单状态轮询（必执行）

下单成功后订单处于占位中，**必须**在有限次数内轮询订单状态，直到得到明确结果。轮询时使用的订单号从创建订单返回的 `data.orderBaseId` 或 `holdingDetailList[].orderBaseId` 获取。

- **轮询间隔**：10 秒
- **最大轮询次数**：6 次（最多等待约 1 分钟）

**状态码与处理**：

| 状态码 | 含义 | Agent 处理 |
|--------|------|-------------|
| `10` | 处理中 | 继续轮询，可提示「正在为您占位，请稍候…」 |
| `12` | 占位完成 | 进入第七阶段，展示成功反馈并提醒支付 |
| `11` | 占位失败 | 进入第七阶段，展示失败反馈并引导重新预订 |
| 超时 | 轮询 6 次仍为 10 | 告知「占位超时，请稍后查询订单状态」 |

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method getOrderStatus --arg "{\"orderBaseId\": \"SRO202603091138018328863\"}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method getOrderStatus --arg-file temp/orderstatus_params.json
```

**参数说明**：
- `orderBaseId`: 订单号（从创建订单返回获取）

**轮询逻辑**：
```python
# 伪代码示例
max_attempts = 6
interval = 10  # 秒

for i in range(max_attempts):
    status = getOrderStatus(orderBaseId)
    if status == 12:  # 占位完成
        print("占位成功！")
        break
    elif status == 11:  # 占位失败
        print("占位失败")
        break
    elif i == max_attempts - 1:  # 最后一次仍为处理中
        print("占位超时")
        break
    time.sleep(interval)
```

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

当用户表达取消机票订单意愿时，执行取消订单。必填为订单号（orderBaseId），按 [api/plane.json](../api/plane.json) 文档，缺则向用户确认订单号。

**场景**：用户想预订其他航班，需先取消当前未支付订单。

**流程**：
1. 向用户确认：「检测到您有未支付的订单，是否需要取消后重新预订？」
2. 用户同意后执行取消
3. 取消成功后继续新流程

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method flight.cancelOrder --arg "{\"orderBaseId\": \"SRO202603091138018328863\", \"orderType\": 0, \"cancelReason\": \"不需要了\", \"terminalCode\": \"APP\"}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method flight.cancelOrder --arg-file temp/cancelorder_params.json
```

**参数说明**：
- `orderBaseId`: 订单号（必填）
- `orderType`: 订单类型，默认 0（机票）
- `cancelReason`: 取消原因
- `orderType` : 订单类型 默认机票 0
- `subOrderType` : 默认国内机票 DOMESTIC_FLIGHT
- `terminalCode`: 终端类型，如 "APP"

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

### 第九阶段：查询订单历史

当用户表达"查看订单"、"我的订单"、"历史订单"等意图时，调用 `orderHistory`。必填字段 memberId 按接口文档，缺则提示。

**触发场景**：
- 用户说「查看我的机票订单」
- 用户说「最近买过的机票」
- 用户说「订单历史」

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method orderHistory --arg "{\"memberId\": \"15d6676f6be54d5099b106abeeecfcd6\"}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method orderHistory --arg-file temp/orderhistory_params.json
```

**参数说明**：
- `memberId`: 会员ID（从认证上下文中获取，通常无需询问）

**展示格式示例**（一行一行展示，勿用表格）：

```
📋 您的机票订单历史

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

订单1：
  订单号：FRO202603101234567890
  航班：CA1234 北京 → 上海
  日期：2026年3月10日 08:00 → 10:15
  状态：✅ 已完成
  金额：¥680

订单2：
  订单号：FRO202603056789012345
  航班：MU5678 上海 → 北京
  日期：2026年3月5日 14:30 → 16:45
  状态：⏰ 待支付
  金额：¥720
  ⚠️ 请在 30 分钟内完成支付

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

共 2 个订单。如需查看详情，请回复订单号。
```

---

### 第十阶段：订单详情

当用户提供订单号或从订单列表中选择某个订单查看详情时，调用 `orderDetail`。必填字段 orderBaseId 按接口文档，缺则提示。

**触发场景**：
- 用户说「查看订单详情 FRO202603101234567890」
- 用户从订单历史中选择某个订单
- 用户说「查询这个订单的情况」

### 🔧 Python 调用命令

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method orderDetail --arg "{\"orderBaseId\": \"FRO202603101234567890\"}"
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

航班信息：
  航班号：CA1234
  日期：2026年3月10日（周一）
  时间：08:00 → 10:15
  航线：北京首都机场 T3 → 上海虹桥机场 T2
  舱位：经济舱

乘客信息：
  张三（320***********1234）

费用明细：
  票面价：¥600
  机建费：¥50
  燃油费：¥30
  ───────────────
  总金额：¥680

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

如需退票，请回复「退票」。
```

---

### 第十一阶段：申请退票

当用户表达"退票"、"我要退票"、"申请退款"等意图时，按顺序调用 `orderHistory`、`orderDetail`、`orderDeduct`（核损）、`flight.refund`。必填字段按接口文档，缺则提示。

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
    - 乘客列表（passengerId、passengerName、ticketId）
    - 订单项编号（orderItemNo）
    - 航班信息
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
python scripts/apiexe.py call --method orderDeduct --arg "{\"orderBaseId\": \"SRO202603091138018328863\", \"resourceType\": 0, \"refundType\": 1, \"applyType\": 0, \"reason\": \"行程变更\", \"deductItemList\": [{\"orderItemNo\": \"OI202603091441449321207\", \"passengerIdList\": [\"399\"]}]}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method orderDeduct --arg-file temp/orderdeduct_params.json
```

**参数说明**：
- `orderBaseId`: 订单号
- `resourceType`: 资源类型，默认 0（机票）
- `refundType`: 1-整单退，2-部分退
- `applyType`: 0-自愿退票，1-非自愿退票，默认 0
- `reason`: 退票原因
- `deductItemList`: 核损项目列表（必填）
    - `orderItemNo`: 订单项编号（从订单详情获取 取值`data.flightProductInfos.items[].orderItemNo`）
    - `passengerIdList`: 需要退票的乘客ID列表
        * 全额退票：包含订单中所有乘客ID
        * 部分退票：只包含用户指定的乘客ID

**核损结果展示**（润色展示，一行一行展示，勿用表格）：

```
📊 核损结果

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

订单号：FRO202603101234567890
航班：CA1234 北京 → 上海
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

**步骤7：提交退票申请（flight.refund）**
- 调用 `flight.refund` 接口提交退票申请

### 🔧 Python 调用命令 - 申请退票

**命令格式（cmd）**：
```bash
python scripts/apiexe.py call --method flight.refund --arg "{\"orderBaseId\": \"SRO202603091138018328863\", \"orderType\": 0, \"applyType\": 1, \"refundType\": 1, \"amount\": 479, \"refundReason\": \"行程变更\", \"refundItemList\": [{\"orderItemNo\": \"OI202603091441449321207\", \"orderPassengerIds\": [\"399\"], \"refundQuantity\" : 1, \"refundAmount\" : 252}]}"
```

**命令格式（PowerShell）**：
```powershell
python scripts/apiexe.py call --method flight.refund --arg-file temp/flightrefund_params.json
```

**参数说明**：
- `orderBaseId`: 订单号（必填）
- `orderType`: 订单类型，默认 0（必填）
- `applyType`: 申请类型，默认 1（必填）
- `refundType`: 1-全额退票，2-部分退票（必填）
- `amount`: 从核损的`flightDeductInfo.totalRefundAmount`获取（退款金额）
- `reason`: 退票原因（必填）
- `reasonType`: 退票原因枚举 默认0即可
- `refundItemList`: 退票明细列表（必填）
    - `orderItemNo`: 订单项编号（从订单详情获取 取值从核损的`ddeductItemList[].orderItemNo`获取）
    - `orderPassengerIds`: 从核损的`deductItemList[].passengerIdList`获取，转为数组，必须是数组，不能是单个数字
        * 全额退票：包含订单中所有乘客ID
        * 部分退票：只包含用户指定的乘客ID
    - `refundQuantity`：需要退票的乘客人数
    - `refundAmount`: 从核损的`flightDeductInfo.totalFeeAmount`获取（手续费）

**确认话术示例 - 全额退票**（润色展示，一行一行展示，勿用表格）：

```
⚠️ 退票确认

订单号：FRO202603101234567890
航班：CA1234 北京 → 上海
日期：2026年3月10日 08:00 → 10:15

乘客：
  张三（票号：7891234567890）
  李四（票号：7891234567891）
  王五（票号：7891234567892）

退票类型：全额退票（全部乘客）
退票原因：行程变更

核损结果：
  退款金额：¥1740
  手续费：¥300

确认申请全额退票吗？(y/n)
```

**确认话术示例 - 部分退票**（润色展示，一行一行展示，勿用表格）：

```
⚠️ 退票确认

订单号：FRO202603101234567890
航班：CA1234 北京 → 上海
日期：2026年3月10日 08:00 → 10:15

退票乘客：
  张三（票号：7891234567890）
  李四（票号：7891234567891）

保留乘客：
  王五（票号：7891234567892）

退票类型：部分退票
退票原因：张三行程变更

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

---

## 步骤与数据对照（Agent 内部参考）

| 阶段 | 步骤说明 | 关键入参 | 关键出参 |
|------|----------|----------|----------|
| 1 | 获取城市列表 | domesticType、resourceType（机票：1, 0） | cityId、flightCode |
| 2 | 查询航班列表 | depCityId、arrCityId、fromCity、toCity、fromDate | goFlight.flights.extData |
| 3 | 查询舱位详情 | goExtData、backExtData、adultNum、childNum、cabinGrade | goFlightCabin.cabinList.resourceItemId |
| 4 | 查询乘客列表 | orderType | 乘客列表 |
| 4 | 保存乘客 | passengerName、identityNo、phoneNumber | 新增乘客 |
| 5 | 创建订单 | items.resourceItemId、passengers、contact 等 | orderBaseId |
| 6 | 查询订单状态 | orderBaseId | status |
| 8 | 取消订单 | orderBaseId | 取消结果 |
| 9 | orderHistory | memberId | 订单历史列表 |
| 10 | orderDetail | orderBaseId | 订单详情 |
| 11 | orderDeduct | orderBaseId、resourceType=1、refundType、deductItemList | 核损结果（含手续费、退款金额等） |
| 12 | flight.refund | orderBaseId、orderType=1、applyType=1、refundType、amount、refundReason、refundItemList | 退票申请结果 |

---

## 异常处理

### 核心原则

**当后台请求异常时，不要让用户重复提供信息！**

用户已经选择的内容必须记住：
- ✅ 出发地和目的地
- ✅ 出发日期
- ✅ 选择的航班
- ✅ 选择的舱位
- ✅ 选择的乘客

### 常见错误处理

**1. 后台返回异常**

向用户展示示例（勿出现「接口」「API」等词）：

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

### 后台返回结果润色（重要）

收到后台返回后，**不要直接原样输出**，应润色成用户可读的文案：

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

【推荐】CA1234 首都机场 08:00 → 虹桥机场 10:15  2h15m  ⭐
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

（内部：若用户说「我要添加新乘客」「没有合适的人」等，则先收集姓名、身份证号、手机号并保存乘客，再展示乘客列表供选择。）

（内部：创建订单后必须轮询订单状态，直到占位完成或失败/超时。）

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

## 执行方式（Agent 内部）

识别用户意图后，查阅 [api/plane.json](../api/plane.json) 选择对应 method，按 `parameters` 构造 params，使用 `scripts/apiexe.py call --method <method> --arg '<params_json>'` 或 `--arg-file` 执行。**以上为内部执行方式，对用户只说业务话术（如「正在为您查询」「正在占位」），不得出现接口名、API、method 等。**

## 多资源场景

若用户同时订购机票和其他资源，先完成机票订购流程，再引导用户处理下一个资源。
