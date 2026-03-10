# 缓存策略实现

## 概述

为减少重复请求、节省 token，以下接口支持本地缓存。

## 缓存接口列表

| 接口 | 缓存文件 | 过期时间 | 说明 |
|------|----------|----------|------|
| `cityList` | `cache/cityList_{resourceType}.json` | 1 小时 | 城市列表（按 resourceType 分别缓存） |

## 缓存机制

1. 调用接口前，检查缓存文件是否存在且未过期
2. 若缓存有效，直接读取缓存数据，**不发起网络请求**
3. 若缓存无效或不存在，调用接口获取数据，并写入缓存文件
4. 缓存文件存放于 `cache/` 目录（需确保目录存在）

## Python 实现代码

```python
import json
import os
import time

CACHE_DIR = "cache"
CACHE_EXPIRE_SECONDS = 3600  # 1小时

def get_cached_city_list(resource_type: int):
    """获取缓存的城市列表"""
    cache_file = f"{CACHE_DIR}/cityList_{resource_type}.json"

    # 检查缓存是否存在且未过期
    if os.path.exists(cache_file):
        file_mtime = os.path.getmtime(cache_file)
        if time.time() - file_mtime < CACHE_EXPIRE_SECONDS:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)

    # 缓存无效，需要重新请求
    return None

def save_city_list_cache(resource_type: int, data):
    """保存城市列表到缓存"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    cache_file = f"{CACHE_DIR}/cityList_{resource_type}.json"
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

## 使用示例

```python
# 查询机票城市列表 (resourceType=0)
cached = get_cached_city_list(0)
if cached:
    city_list = cached
else:
    # 调用接口获取数据
    result = call_api("cityList", {"resourceType": 0})
    city_list = result["data"]
    save_city_list_cache(0, city_list)

# 查询酒店城市列表 (resourceType=1)
cached = get_cached_city_list(1)
if cached:
    city_list = cached
else:
    result = call_api("cityList", {"resourceType": 1})
    city_list = result["data"]
    save_city_list_cache(1, city_list)
```

## 扩展说明

后续如有其他接口需要缓存，可参照此模式扩展：
- 在上表中添加接口信息
- 实现 `get_cached_{method}` 和 `save_{method}_cache` 函数
- 根据 API 响应大小和更新频率调整过期时间
