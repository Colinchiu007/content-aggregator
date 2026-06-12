# 修复 server.py 的认证模块导入（强制使用本地 auth_router）
$filePath = "C:\Users\邱领\.qclaw\workspace\content-aggregator\web\server.py"

# 读取文件（UTF-8）
$content = Get-Content -Path $filePath -Encoding UTF8 -Raw

# 旧文本（共享认证模块）
$oldText = '# 共享认证模块
try:
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "team"))
    from shared.auth.auth_routes import router as auth_router
    from shared.auth.jwt_handler import get_user_from_token
    AUTH_ENABLED = True
    logger.info("已加载共享认证模块")
except ImportError:
    # Fallback：加载本地认证模块
    try:
        from web.auth_router import router as auth_router
        from web.auth_router import get_current_user as get_user_from_token
        AUTH_ENABLED = True
        logger.info("已加载本地认证模块（web/auth_router.py）")
    except ImportError:
        AUTH_ENABLED = False
        logger.warning("认证模块未找到，使用无认证模式")'

# 新文本（强制本地认证）
$newText = '# 共享认证模块（已禁用，强制使用本地认证）
# try:
#     sys.path.insert(0, str(Path(__file__).parent.parent.parent / "team"))
#     from shared.auth.auth_routes import router as auth_router
#     from shared.auth.jwt_handler import get_user_from_token
#     AUTH_ENABLED = True
#     logger.info("已加载共享认证模块")
# except ImportError:
#     # Fallback：加载本地认证模块
#     try:
#         from web.auth_router import router as auth_router
#         from web.auth_router import get_current_user as get_user_from_token
#         AUTH_ENABLED = True
#         logger.info("已加载本地认证模块（web/auth_router.py）")
#     except ImportError:
#         AUTH_ENABLED = False
#         logger.warning("认证模块未找到，使用无认证模式")

# 强制使用本地认证模块
from web.auth_router import router as auth_router
from web.auth_router import get_current_user as get_user_from_token
AUTH_ENABLED = True
logger.info("已强制启用本地认证模块（/api/auth 路由）")'

if ($content.Contains($oldText)) {
    $content = $content.Replace($oldText, $newText)
    Set-Content -Path $filePath -Value $content -Encoding UTF8
    Write-Output "已修复 server.py，强制使用本地认证模块"
    Write-Output "共享认证模块已禁用（注释掉）"
} else {
    Write-Output "未找到预期文本，手动检查 server.py 第43-58行"
}

# 验证语法
$checkResult = python -m py_compile $filePath 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Output "语法检查通过"
} else {
    Write-Output "语法错误：$checkResult"
}
