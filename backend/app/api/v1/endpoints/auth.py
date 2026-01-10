from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.services.auth_service import auth_service

router = APIRouter()

class LoginRequest(BaseModel):
    password: str

class AdminToggleRequest(BaseModel):
    admin_password: str
    enabled: bool

@router.post("/login")
async def login(request: Request, body: LoginRequest):
    """
    用户登录
    """
    if not auth_service.is_system_enabled():
        # 如果系统未开启验证，直接返回成功
        return {
            "success": True, 
            "message": "System auth disabled",
            "token": "auth_disabled",
            "expires_at": 9999999999
        }

    client_ip = request.client.host
    result = auth_service.verify_password(body.password, client_ip)
    
    if not result["success"]:
        # 403 Forbidden for auth failures
        status_code = 403
        if result.get("locked"):
            status_code = 423 # Locked
        
        raise HTTPException(
            status_code=status_code,
            detail={
                "message": result["message"],
                "locked": result.get("locked", False),
                "remaining_attempts": result.get("remaining_attempts", 0)
            }
        )
        
    return result

@router.get("/status")
async def get_auth_status(request: Request):
    """
    获取当前认证系统状态及用户是否锁定
    """
    client_ip = request.client.host
    is_locked = auth_service.is_ip_locked(client_ip)
    remaining = auth_service.get_remaining_attempts(client_ip)
    
    return {
        "enabled": auth_service.is_system_enabled(),
        "is_locked": is_locked,
        "remaining_attempts": remaining
    }

@router.post("/admin/toggle")
async def toggle_auth_system(body: AdminToggleRequest):
    """
    管理员开启/关闭认证系统
    """
    success = auth_service.toggle_system(body.admin_password, body.enabled)
    if not success:
        raise HTTPException(status_code=403, detail="Invalid admin password")
    
    return {
        "success": True,
        "enabled": body.enabled,
        "message": f"System authentication {'enabled' if body.enabled else 'disabled'}"
    }

@router.post("/reset-lock")
async def reset_lock(request: Request):
    """
    [紧急] 强制重置所有锁定状态
    """
    # 重新加载文件中的状态（此时文件中已经是空的了）
    auth_service._load_state()
    return {"message": "Auth state reloaded from file. Lock should be cleared."}
