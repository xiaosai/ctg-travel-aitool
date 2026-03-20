# 机票退票操作指南

**触发条件**：退票、我要退票、申请退款、把刚刚预定的机票退了、取消这张机票（已支付）、张三退票、张三和李四退票

---

## 退票流程

```
1. orderDeduct → 核损（退票前必调）
2. flight.refund → 提交退票申请
```

---

## 参数传递依赖

| 接口 | 入参来源 |
|------|----------|
| orderDeduct | `orderBaseId` |
| flight.refund | `orderBaseId` ← 同上<br>`orderItemNo` ← orderDeduct 返回的 `deductItemList[].orderItemNo`<br>`orderPassengerIds` ← orderDeduct 返回的 `deductItemList[].passengerIdList`<br>`amount` ← orderDeduct 返回的 `flightDeductInfo.totalRefundAmount`<br>`refundAmount`（手续费）← orderDeduct 返回的 `flightDeductInfo.totalFeeAmount` |

---

## 退票类型识别

| 用户输入 | refundType | 说明 |
|---------|-----------|------|
| 「退票」「我要退票」「取消这张机票」 | 1（全额退票） | 未指定乘客，默认全退 |
| 「全退」「全部退票」「三个人都要退」 | 1（全额退票） | 明确全额退票 |
| 「张三退票」「退张三的票」 | 2（部分退票） | 指定了单个乘客 |
| 「张三和李四退票」「退张三和李四」 | 2（部分退票） | 指定了部分乘客 |

---

## 接口参数

### orderDeduct（核损）
**必填**：
- `orderBaseId`：订单号
- `refundType`：1=整单退，2=部分退

**可选**：
- `passengerIds`：退票乘客ID列表（部分退时必填）

**返参关键字段**：
- `flightDeductInfo.totalRefundAmount`：退款金额
- `flightDeductInfo.totalFeeAmount`：手续费
- `deductItemList[].orderItemNo`：订单项编号
- `deductItemList[].passengerIdList`：乘客ID列表

### flight.refund（申请退票）
**必填**：
- `orderBaseId`：订单号
- `orderType`：传 0（机票）
- `applyType`：默认 1
- `refundType`：1=全额退票，2=部分退票
- `amount`：退款金额，取 `flightDeductInfo.totalRefundAmount`
- `refundReason`：退票原因
- `reasonType`：原因类型，默认 0
- `refundItemList`：退票明细列表

**refundItemList 结构（必填）**：
- `orderItemNo`：取核损接口返回的 orderItemNo
- `orderPassengerIds`：乘客ID数组（如 ["399"]，注意是数组格式）
- `refundQuantity`：退票数量
- `refundAmount`：手续费，取 `flightDeductInfo.totalFeeAmount`

---

## 调用命令

```bash
# 核损（必填：orderBaseId, refundType；部分退时还需 passengerIds）
python scripts/apiexe.py call --method orderDeduct --arg "{\"orderBaseId\": \"FRO202603151234567890\", \"refundType\": 1}"

# 申请退票（必填：orderBaseId, orderType, applyType, refundType, amount, refundItemList）
python scripts/apiexe.py call --method flight.refund --arg "{\"orderBaseId\": \"FRO202603151234567890\", \"orderType\": 0, \"applyType\": 1, \"refundType\": 1, \"amount\": 580, \"reasonType\": 0, \"refundReason\": \"行程变更\", \"refundItemList\": [{\"orderItemNo\": \"OI202603151234567890\", \"orderPassengerIds\": [\"399\"], \"refundQuantity\": 1, \"refundAmount\": 100}]}"
```

---

## 展示格式

**核损结果**：订单号、航班、日期、退票乘客、原支付金额、退款金额、手续费

**退票确认（全额）**：
```
⚠️ 退票确认

订单号：FRO202603101234567890
航班：CA1234 北京 → 上海
日期：2026年3月10日 08:00 → 10:15

乘客：
  张三（票号：7891234567890）
  李四（票号：7891234567891）

退票类型：全额退票（全部乘客）
退票原因：行程变更

核损结果：
  退款金额：¥1160
  手续费：¥200

确认申请全额退票吗？(y/n)
```

**退票成功**：订单号、退款金额、预计到账时间(3-7个工作日)

---

## 异常处理

- **订单不可退**：提示可能原因（未支付/超时限/已使用）
- **核损失败**：提示稍后重试或前往中旅旅行App
- **退票申请失败**：展示后台友好提示，引导重试或前往App
