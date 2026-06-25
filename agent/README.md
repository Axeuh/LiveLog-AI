# axeuh-agent - 远程AI助手客户端

安装在被AI管理的Windows电脑上，提供截图、文件操作、命令执行等功能。

## 安装

### 方式1：直接运行（需要Python）

```bash
pip install -r requirements.txt
python agent_server.py
```

### 方式2：打包成exe

```bash
# 先安装 pyinstaller
pip install pyinstaller

# 然后运行打包脚本
build.bat

# 在 dist/ 目录得到 axeuh-agent.exe
```

## 配置

编辑 `config.json`：

```json
{
  "agent_id": "my-pc",
  "agent_name": "我的电脑",
  "server_host": "0.0.0.0",
  "server_port": 18888,
  "agent_token": "设置一个安全的token",
  "server_url": "wss://(占位符)/ws/agent"
}
```

| 字段        | 说明                                  |
| ----------- | ------------------------------------- |
| agent_id    | 唯一标识，用于服务端区分不同客户端    |
| agent_name  | 显示名称                              |
| server_host | 监听地址，0.0.0.0 表示所有网卡        |
| server_port | 本地 HTTP API 端口                    |
| agent_token | 认证 Token，所有请求需要此 Token      |
| server_url  | 服务端 WebSocket 地址，用于注册和心跳 |

## API端点

所有请求需带 `Authorization: Bearer {token}` 头。

| 端点             | 方法 | 功能                              |
| ---------------- | ---- | --------------------------------- |
| `/health`      | GET  | 健康检查                          |
| `/screenshot`  | GET  | 截屏（返回PNG）                   |
| `/files/list`  | GET  | 列出目录（?path=xxx）             |
| `/files/read`  | GET  | 读取文件（?path=xxx）             |
| `/files/write` | POST | 写入文件（body: {path, content}） |
| `/exec`        | POST | 执行命令（body: {command}）       |
| `/system/info` | GET  | 系统信息                          |

## 安全注意

- 默认 token `change-me-to-a-secure-token` 请务必修改
- 敏感路径（`C:\Windows\System32` 等）自动禁止访问
- 危险命令（`format`, `del /f`, `rd /s` 等）自动拦截
- 建议在防火墙中限制 18888 端口的访问来源
