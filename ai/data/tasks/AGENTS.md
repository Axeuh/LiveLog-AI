# 定时任务 & 自定义脚本配置

此目录存放所有定时任务和自定义脚本的配置文件。

- `*.yaml` — YAML 定时任务（简单固定流程）
- `*.py` — Python 自定义脚本（复杂自动化，FileWatcher 自动加载）
  AI 可直接编辑此目录下的所有文件。

## 文件格式

```yaml
name: 任务名称
enabled: true                           # 是否启用，可选，默认 true
schedule: <schedule格式>                 # 触发计划
prompt: |-                              # 发给 AI 的提示词
  任务执行逻辑...
```

## schedule 格式

### 简写方式（推荐：一行搞定）

| 表达式                                         | 说明                    |
| ---------------------------------------------- | ----------------------- |
| `daily: "08:00"`                             | 每天 08:00              |
| `daily: "04:00"`                             | 每天 04:00              |
| `hourly: 30`                                 | 每小时的 30 分          |
| `weekly: {days: "mon,wed,fri", at: "09:00"}` | 每周一三五 09:00        |
| `monthly: "1,15 14:30"`                      | 每月 1 日和 15 日 14:30 |
| `delay: "5m"`                                | 5 分钟后执行一次        |

### 每月不同日期不同时间

```yaml
schedule:
  monthly:
    1: "14:30"
    15: "10:00"
```

### 字符串简写

```yaml
schedule: "daily 04:00"
schedule: "weekly mon,wed,fri 09:00"
schedule: "monthly 1,15 14:30"
schedule: "hourly"
schedule: "delay 5m"
```

规则：

- 第一个词是模式关键字：`daily` / `hourly` / `weekly` / `monthly` / `delay`
- 星期名用 3 字母小写：`mon,tue,wed,thu,fri,sat,sun`
- 时间格式 `HH:MM`（24 小时制）
- 延迟格式：数字+单位（`s`秒, `m`分, `h`时, `d`天）

## 默认值

| 字段                    | 默认值        | 说明             |
| ----------------------- | ------------- | ---------------- |
| `enabled`             | `true`      | 任务启用状态     |
| `schedule` 未指定时间 | `00:00`     | 凌晨执行         |
| `weekly` 未指定天数   | `mon`       | 周一             |
| `monthly` 未指定日期  | `1`         | 每月 1 号        |
| `user_id`             | `"default"` | 自动填充，不用写 |
| `target`              | `main-task` | 自动填充，不用写 |

## 运行时状态（不需要写，调度器自动管理）

以下字段由调度器自动管理，**不要在任务文件中填写**：

- `next_run` — 下次执行时间
- `last_run` — 上次执行时间
- `run_count` — 已执行次数
- `task_id` — 自动生成
- `created_at` — 自动生成

## 新增任务的步骤

1. 在 `ai/data/tasks/` 下新建 `.yaml` 文件
2. 写 `name`, `schedule`, `prompt` 三个字段
3. 可选：`enabled: false` 暂不启用
4. 保存文件，后端自动热加载，**无需重启**

## 示例

```yaml
# ai/data/tasks/example-task.yaml
name: 示例任务
schedule:
  daily: "08:00"
enabled: true
prompt: |-
  【示例任务】 按以下流程执行：

  1. 运行分析脚本
  2. 生成报告
  3. git add/commit
```

---

## Python 自定义脚本（2026-06-25 新增）

此目录也支持 `.py` 文件——FileWatcher 自动检测、AST 安全审查后启动。

### 脚本文件格式

```python
"""
name: 脚本名称          # 必填
enabled: true            # true=自动启动, false=停止
note: 备注说明           # 可选
prompt: |               # 调用 trigger_task 时的默认提示词
  请分析今天的感知数据。
"""

def run(context):
    """自循环模式：自己控制频率和心跳"""
    while True:
        context.log("检查中...")
        if 条件满足:
            context.trigger_task("任务名")  # 触发 AI 任务
        context.heartbeat()   # 必须每30秒至少调用一次
        time.sleep(60)
```

### Context API

| 方法                                     | 说明                        |
| ---------------------------------------- | --------------------------- |
| `context.log(msg)`                     | 记录结构化日志              |
| `context.trigger_task(target, prompt)` | 触发 AI 任务（prompt 可选） |
| `context.alert(msg)`                   | 报告错误/异常               |
| `context.read_file(path)`              | 读取文件（沙箱路径）        |
| `context.heartbeat()`                  | 保活信号（自循环必调）      |

### 与 YAML 任务的区别

YAML 任务：简单固定流程，静态 prompt，适合系统内部调度。
Python 脚本：完整编程能力，动态条件判断，适合复杂自动化。

### 沙箱限制

- 允许导入：`math, json, re, datetime, time, random, typing, collections`
- 禁止：`os`(部分)、`subprocess`、`socket`、`eval/exec/compile`
- 内存限制 256MB，trigger_task 速率限制 10次/分钟
- 如何有什么新的导入需求应该向用户请求和通知。

### 示例

```python
# ai/data/tasks/hello_production.py
"""
name: 生产测试脚本
enabled: true
note: 完整功能演示
prompt: 这是一个自定义脚本的完整功能演示。
"""

def run(context):
    while True:
        context.log("正在检查...")
        context.trigger_task("检查", "请分析数据")
        context.heartbeat()
        time.sleep(60)
```

## 参考

- `ai/data/tasks/*.yaml` — YAML 定时任务
- `ai/data/tasks/*.py` — Python 自定义脚本
- `ai/data/tasks/logs/{脚本名}/{日期}.log` — 脚本运行日志
- `ai/data/tasks/logs/audit/{日期}.jsonl` — 审计日志
- `demo/` — 独立测试环境（`demo/run.py` 调试脚本）
- 后端解析逻辑见 `backend/services/schedule_parser.py`
