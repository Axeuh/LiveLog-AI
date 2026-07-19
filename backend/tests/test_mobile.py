# -*- coding: utf-8 -*-
import json
from config.config import get_config

_TEST_HOST = f"localhost:{get_config().BACKEND_HTTPS_PORT}"

"""
手机端文件浏览 API 测试

覆盖场景：
  - 列出根目录
  - 按日期列出目录
  - 不存在的路径返回 404
  - 目录穿越被拒绝返回 403
  - 读取 JSON 文件内容
  - 读取 JSONL 文件内容
  - 不存在的文件返回 404
  - 公开路径无需认证
"""


class TestListFiles:
    """列出目录内容"""

    def test_list_root(self, client):
        """GET /api/mobile/files?path= 应返回根目录列表"""
        resp = client.get("/api/mobile/files", params={"path": ""}, headers={"host": _TEST_HOST})
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert isinstance(data["entries"], list)
        # 根目录应包含日期目录（如 2026-06-06）
        names = [e["name"] for e in data["entries"]]
        assert "2026-06-06" in names
        # 目录应标记为 dir 类型
        dir_entries = [e for e in data["entries"] if e["name"] == "2026-06-06"]
        assert len(dir_entries) > 0
        assert dir_entries[0]["type"] == "dir"

    def test_list_by_date(self, client):
        """GET /api/mobile/files?path=2026-06-06 应返回该日目录下的文件"""
        resp = client.get("/api/mobile/files", params={"path": "2026-06-06"}, headers={"host": _TEST_HOST})
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        names = [e["name"] for e in data["entries"]]
        assert "health.json" in names or "perception.jsonl" in names or "profile.json" in names
        # 验证所有条目都有必需字段
        for entry in data["entries"]:
            assert "name" in entry
            assert "type" in entry
            assert "mtime" in entry
            assert entry["type"] in ("dir", "json", "jsonl", "txt", "md", "wav", "jpg", "png", "file")

    def test_list_nonexistent(self, client):
        """GET /api/mobile/files?path=2099-99-99 不存在的路径应返回空列表"""
        resp = client.get("/api/mobile/files", params={"path": "2099-99-99"}, headers={"host": _TEST_HOST})
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data.get("entries"), list)

    def test_list_path_traversal(self, client):
        """GET /api/mobile/files?path=../../../etc 目录穿越应返回 403"""
        resp = client.get("/api/mobile/files", params={"path": "../../../etc"},
                          headers={"host": _TEST_HOST})
        assert resp.status_code == 403
        data = resp.json()
        assert "error" in data and data["error"]["code"] == "FORBIDDEN"
        assert "拒绝" in data["error"]["message"] or "禁止" in data["error"]["message"]

    def test_list_file_path_not_directory(self, client):
        """GET /api/mobile/files?path=2026-06-06/health.json 路径是文件不是目录应返回 400"""
        resp = client.get("/api/mobile/files", params={"path": "2026-06-06/health.json"},
                          headers={"host": _TEST_HOST})
        assert resp.status_code == 400
        data = resp.json()
        assert "error" in data and data["error"]["code"] == "INTERNAL_ERROR"


class TestReadFile:
    """读取文件内容"""

    def test_read_json(self, client, auth_headers):
        """GET /api/mobile/files/content?path=2026-06-06/health.json 应返回 {content} 包裹的原始文本"""
        headers = {**auth_headers, "host": _TEST_HOST}
        resp = client.get("/api/mobile/files/content", params={"path": "2026-06-06/health.json"},
                          headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        # 现在返回 {content: raw_text}，不再直接返回解析后的 JSON 对象
        assert "content" in data
        assert isinstance(data["content"], str)
        assert "type" in data
        assert data["type"] == "json"
        parsed = json.loads(data["content"])
        assert "date" in parsed
        assert parsed["date"] == "2026-06-06"
        assert "samples" in parsed
        assert isinstance(parsed["samples"], list)

    def test_read_jsonl(self, client, auth_headers):
        """GET /api/mobile/files/content?path=2026-06-06/perception.jsonl 应返回对象数组"""
        headers = {**auth_headers, "host": _TEST_HOST}
        resp = client.get("/api/mobile/files/content", params={"path": "2026-06-06/perception.jsonl"},
                          headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "objects" in data
        assert "total_lines" in data
        assert "parse_errors" in data
        assert isinstance(data["objects"], list)
        assert data["total_lines"] > 0
        assert data["parse_errors"] == 0

    def test_read_file_not_found(self, client, auth_headers):
        """GET /api/mobile/files/content?path=nonexistent/file.json 不存在的文件应返回 404"""
        headers = {**auth_headers, "host": _TEST_HOST}
        resp = client.get("/api/mobile/files/content", params={"path": "nonexistent/file.json"},
                          headers=headers)
        assert resp.status_code == 404
        data = resp.json()
        assert "error" in data and data["error"]["code"] == "NOT_FOUND"

    def test_read_path_traversal(self, client, auth_headers):
        """GET /api/mobile/files/content?path=../../../etc/passwd 目录穿越应返回 403"""
        headers = {**auth_headers, "host": _TEST_HOST}
        resp = client.get("/api/mobile/files/content", params={"path": "../../../etc/passwd"},
                          headers=headers)
        assert resp.status_code == 403
        data = resp.json()
        assert "error" in data and data["error"]["code"] == "FORBIDDEN"
        assert "拒绝" in data["error"]["message"] or "禁止" in data["error"]["message"]


class TestAuth:
    """认证检查"""

    def test_unauthorized(self, client):
        """/api/mobile/files 是公开路径，无 token 也能访问"""
        # /api/mobile/files 已被列入 PUBLIC_PATHS，无需认证
        resp = client.get("/api/mobile/files")
        assert resp.status_code == 200
