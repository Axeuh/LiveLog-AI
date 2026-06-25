# API Behavior Baseline

该目录记录了 `axeuh-health-monitor` 后端所有 API 端点的响应快照，
用于行为验证和回归测试。

## 目录结构

```
behavior/
├── README.md            # 本文档
├── verify.py            # 验证脚本（录制/回放）
└── snapshots/           # 响应快照（每个端点一个 JSON 文件）
    ├── health.get.json
    ├── login.post.json
    ├── ...
```

## 使用方法

### 录制新快照

首次使用或后端 API 变更后，需要重新录制快照：

```bash
python behavior/verify.py --record
```

这会：
1. 自动在端口 8769 启动后端服务器（HTTP 模式）
2. 依次调用所有 API 端点
3. 将响应保存到 `snapshots/` 目录

### 验证

```bash
python behavior/verify.py
```

这会：
1. 自动在端口 8769 启动后端服务器
2. 依次调用所有 API 端点
3. 将响应与已保存的快照对比
4. 报告 PASS/FAIL

退出码：0=全部通过，1=存在失败

## 快照格式

```json
{
  "meta": {
    "recorded_at": "ISO_TIMESTAMP",
    "method": "GET",
    "path": "/health",
    "note": "Endpoint description"
  },
  "request": {
    "method": "GET",
    "path": "/health",
    "headers": {}
  },
  "response": {
    "status_code": 200,
    "headers": {"content-type": "application/json"},
    "body": {"status": "healthy"}
  }
}
```

## 注意事项

- 验证脚本使用 HTTP 端口 8769，避免与生产端口 (8767/8768) 冲突
- 本地访问不需要 Token 认证（由 AuthMiddleware 自动处理）
- 登录成功的 Token 保存在临时变量中，用于认证相关端点
- 如果端口 8769 被占用，脚本会自动尝试终止占用进程
