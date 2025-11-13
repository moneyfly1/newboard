from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.common import ResponseBase
from app.services.node_service import NodeService
from app.utils.security import get_current_user
from app.api.api_v1.endpoints.common import handle_api_error

router = APIRouter()

def _extract_public_node_data(node: dict) -> dict:
    return {
        "id": node.get("id", 0),
        "name": node.get("name", ""),
        "region": node.get("region", ""),
        "type": node.get("type", ""),
        "status": node.get("status", "offline"),
        "load": node.get("load", 0.0),
        "speed": node.get("speed", 0.0),
        "uptime": node.get("uptime", 0),
        "latency": node.get("latency", 0),
        "description": node.get("description", ""),
        "is_recommended": node.get("is_recommended", False),
        "is_active": node.get("is_active", True)
    }

@router.get("/", response_model=ResponseBase)
@handle_api_error("获取节点列表")
def get_nodes(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    node_service = NodeService(db)
    try:
        nodes_data = node_service.get_nodes_from_clash_config()
        public_nodes = [_extract_public_node_data(node) for node in nodes_data]
        return ResponseBase(data={"nodes": public_nodes}, message="获取节点列表成功")
    finally:
        node_service.close()

@router.get("/{node_id}", response_model=ResponseBase)
def get_node(
    node_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    node_service = NodeService(db)
    try:
        nodes_data = node_service.get_nodes_from_clash_config()
        node = next((n for n in nodes_data if n.get("id") == node_id), None)
        if not node:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="节点不存在")
        return ResponseBase(data={"node": _extract_public_node_data(node)})
    finally:
        node_service.close()

@router.post("/import-from-clash", response_model=ResponseBase)
def import_nodes_from_clash(
    clash_config: str,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> Any:
    # 已废弃：节点现在从文件读取，不支持导入到数据库
    # 请使用配置更新功能来更新节点文件
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="节点管理已改为从文件读取，请通过配置更新功能更新节点文件"
    )

@router.get("/stats/overview", response_model=ResponseBase)
def get_nodes_stats(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Any:
    node_service = NodeService(db)
    try:
        stats = node_service.get_nodes_stats()
        return ResponseBase(data={
            "total_nodes": stats.get("total", 0),
            "online_nodes": stats.get("online", 0),
            "regions": stats.get("regions", []),
            "types": stats.get("types", []),
            "avg_latency": stats.get("avg_latency", 0),
            "avg_load": stats.get("avg_load", 0)
        })
    finally:
        node_service.close() 