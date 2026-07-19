from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
from functools import lru_cache

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from services.opencode_gateway import get_opencode_gateway


# === 模型配置管理 ===
CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "model_config.json"
_default_cfg = get_opencode_gateway()
OPENCODE_DEFAULT_MODEL = _default_cfg.get_default_model()
OPENCODE_DEFAULT_PROVIDER = _default_cfg.get_default_provider()


@lru_cache(maxsize=1)
def _load_model_cache() -> Dict[str, str]:
    """加载模型配置缓存"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def load_model_config() -> Dict[str, str]:
    """获取当前模型配置"""
    return _load_model_cache()


def reset_model_config_cache():
    """清除模型配置缓存"""
    _load_model_cache.cache_clear()


router = APIRouter(prefix="/api/screen")


class ModelItem(BaseModel):
    id: str
    name: str


class ProviderItem(BaseModel):
    id: str
    name: str
    models: List[ModelItem]


class CurrentModel(BaseModel):
    model: str
    provider: str


class GetModelResponse(BaseModel):
    success: bool
    current: CurrentModel
    providers: List[ProviderItem]


class SetModelRequest(BaseModel):
    model: str
    provider: str


@router.get("/model", response_model=GetModelResponse, tags=["model_config"])
async def get_model_config():
    # 获取可用模型信息，按 provider 分组
    gw = get_opencode_gateway()
    models_result = await gw.get_available_models()
    if models_result.get("ok"):
        providers = models_result["data"].get("providers", [])
    else:
        providers = []
    
    # Gateway 已按 provider 分组返回，转换为 ProviderItem / ModelItem
    providers_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(providers, list):
        for pv in providers:
            if not isinstance(pv, dict):
                continue
            provider_id: str = pv.get("id") or ""
            provider_name: str = pv.get("name") or provider_id
            model_list = pv.get("models") or []
            if not provider_id:
                continue
            providers_map[provider_id] = {
                "id": provider_id,
                "name": provider_name,
                "models": [
                    ModelItem(id=m["id"], name=m.get("name") or m["id"])
                    for m in model_list if isinstance(m, dict) and m.get("id")
                ]
            }

    current_cfg = load_model_config()
    current_model = current_cfg.get("default_model") if isinstance(current_cfg, dict) else OPENCODE_DEFAULT_MODEL
    current_provider = current_cfg.get("default_provider") if isinstance(current_cfg, dict) else OPENCODE_DEFAULT_PROVIDER

    # 构造返回结构
    current_out = {"model": current_model, "provider": current_provider}
    providers_final = list(providers_map.values())

    return {"success": True, "current": current_out, "providers": providers_final}


@router.post("/model", response_model=GetModelResponse, tags=["model_config"])
async def set_model_config(req: SetModelRequest):
    # 校验传入的模型与提供商是否存在于当前可用模型中
    gw = get_opencode_gateway()
    models_result = await gw.get_available_models()
    if models_result.get("ok"):
        providers = models_result["data"].get("providers", [])
    else:
        providers = []
    valid = False
    if isinstance(providers, list):
        for prov in providers:
            for mdl in prov.get("models", []):
                if prov.get("id") == req.provider and mdl.get("id") == req.model:
                    valid = True
                    break

    if not valid:
        raise HTTPException(status_code=400, detail="Invalid model or provider")

    # 保存到配置文件中
    config_path: Path = Path(__file__).resolve().parents[1] / "config" / "model_config.json"
    data = {"default_model": req.model, "default_provider": req.provider}
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with config_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save model config: {str(e)}")

    # 清除缓存，让后续 GET 读取最新配置
    reset_model_config_cache()

    # 返回更新后的当前配置
    current_out = {"model": req.model, "provider": req.provider}
    # 转换为 ProviderItem / ModelItem（与 GET 端点相同的逻辑）
    providers_map: Dict[str, Dict[str, Any]] = {}
    if isinstance(providers, list):
        for pv in providers:
            if not isinstance(pv, dict):
                continue
            provider_id: str = pv.get("id") or ""
            provider_name: str = pv.get("name") or provider_id
            model_list = pv.get("models") or []
            if not provider_id:
                continue
            providers_map[provider_id] = {
                "id": provider_id,
                "name": provider_name,
                "models": [
                    ModelItem(id=m["id"], name=m.get("name") or m["id"])
                    for m in model_list if isinstance(m, dict) and m.get("id")
                ]
            }

    return {"success": True, "current": current_out, "providers": list(providers_map.values())}
