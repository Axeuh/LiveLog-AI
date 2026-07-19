# -*- coding: utf-8 -*-
"""通知推送路由测试 - 历史记录管理"""

import time
import pytest


class TestNotificationHistory:
    """通知历史管理功能测试"""

    def test_send_and_history(self, client, auth_headers):
        """发送通知后可通过历史 API 检索到"""
        # 发送通知
        resp = client.post(
            "/api/notification/send",
            json={"title": "测试标题", "content": "测试内容"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        nid = resp.json()["notification_id"]

        # 查询历史应包含刚发送的通知
        resp = client.get("/api/notification/history", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        ids = [n["id"] for n in data["notifications"]]
        assert nid in ids

        # 验证字段完整性
        match = [n for n in data["notifications"] if n["id"] == nid][0]
        assert match["title"] == "测试标题"
        assert match["content"] == "测试内容"
        assert isinstance(match["created_at"], int)

    def test_delete_notification(self, client, auth_headers):
        """删除后通知不再出现在历史中"""
        # 先发一条
        resp = client.post(
            "/api/notification/send",
            json={"title": "待删除", "content": "这条将被删除"},
            headers=auth_headers,
        )
        nid = resp.json()["notification_id"]

        # 确认存在
        resp = client.get("/api/notification/history", headers=auth_headers)
        ids_before = [n["id"] for n in resp.json()["notifications"]]
        assert nid in ids_before

        # 删除
        resp = client.delete(f"/api/notification/history/{nid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

        # 确认已移除
        resp = client.get("/api/notification/history", headers=auth_headers)
        ids_after = [n["id"] for n in resp.json()["notifications"]]
        assert nid not in ids_after

    def test_delete_nonexistent(self, client, auth_headers):
        """删除不存在的通知返回 404"""
        resp = client.delete("/api/notification/history/999999", headers=auth_headers)
        assert resp.status_code == 404

    def test_history_pagination(self, client, auth_headers):
        """分页参数 limit/offset 生效"""
        # 发多条通知（先清一下之前的，用时间戳区分）
        sent_ids = []
        for i in range(5):
            resp = client.post(
                "/api/notification/send",
                json={"title": f"通知{i}", "content": f"第{i}条"},
                headers=auth_headers,
            )
            sent_ids.append(resp.json()["notification_id"])

        # limit=2 应只返回 2 条（最新在前）
        resp = client.get(
            "/api/notification/history?limit=2&offset=0", headers=auth_headers
        )
        data = resp.json()
        assert len(data["notifications"]) == 2
        assert data["total"] >= 5

        # offset=2 应跳过前 2 条
        resp2 = client.get(
            "/api/notification/history?limit=2&offset=2", headers=auth_headers
        )
        data2 = resp2.json()
        assert len(data2["notifications"]) == 2
        # 偏移后第一条的 id 应和 limit 2 的第三条相同
        assert data2["notifications"][0]["id"] != data["notifications"][0]["id"]

    def test_auto_prune(self, client, auth_headers):
        """超出 MAX_HISTORY_PER_USER 自动裁剪最早的通知"""
        MAX_HISTORY = 100
        # 发 MAX_HISTORY + 5 条
        for i in range(MAX_HISTORY + 5):
            client.post(
                "/api/notification/send",
                json={"title": f"裁剪测试{i}", "content": f"内容{i}"},
                headers=auth_headers,
            )

        resp = client.get("/api/notification/history", headers=auth_headers)
        data = resp.json()
        assert data["total"] == MAX_HISTORY

    def test_user_isolation(self, client, auth_headers):
        """不同用户的通知历史隔离"""
        # 用 Axeuh 身份发一条通知（来自 token 中的 user_id）
        resp = client.post(
            "/api/notification/send",
            json={"title": "Axeuh的通知", "content": "仅供Axeuh查看"},
            headers=auth_headers,
        )
        axeuh_nid = resp.json()["notification_id"]

        # 用显式 user_id="user1" 发一条通知（模拟 AI 指定目标用户）
        resp = client.post(
            "/api/notification/send",
            json={"title": "user1的通知", "content": "仅供user1查看", "user_id": "user1"},
            headers=auth_headers,
        )
        user1_nid = resp.json()["notification_id"]

        # Axeuh 的历史应包含自己的通知，不包含 user1 的
        resp = client.get("/api/notification/history", headers=auth_headers)
        assert resp.status_code == 200
        axeuh_ids = [n["id"] for n in resp.json()["notifications"]]
        assert axeuh_nid in axeuh_ids
        assert user1_nid not in axeuh_ids

    def test_poll_does_not_affect_history(self, client, auth_headers):
        """poll 读取通知不应从历史中移除"""
        # 发一条通知
        resp = client.post(
            "/api/notification/send",
            json={"title": "poll测试", "content": "poll不删除历史"},
            headers=auth_headers,
        )
        nid = resp.json()["notification_id"]

        # poll 取走
        resp = client.get("/api/notification/poll", headers=auth_headers)
        assert resp.status_code == 200

        # 历史中应仍存在
        resp = client.get("/api/notification/history", headers=auth_headers)
        ids = [n["id"] for n in resp.json()["notifications"]]
        assert nid in ids
