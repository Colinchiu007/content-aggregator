"""自定义异常类 — 统一错误处理"""


class HotRewriteException(Exception):
    """应用基础异常"""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class NotFoundError(HotRewriteException):
    """资源未找到 (404)"""

    def __init__(self, message: str = "资源未找到"):
        super().__init__(message, status_code=404)


class UnauthorizedError(HotRewriteException):
    """未授权 (401)"""

    def __init__(self, message: str = "未授权，请先登录"):
        super().__init__(message, status_code=401)


class ForbiddenError(HotRewriteException):
    """禁止访问 (403)"""

    def __init__(self, message: str = "无权限访问该资源"):
        super().__init__(message, status_code=403)


class ConflictError(HotRewriteException):
    """资源冲突 (409) — 如用户名/邮箱已存在"""

    def __init__(self, message: str = "资源已存在"):
        super().__init__(message, status_code=409)


class ValidationError(HotRewriteException):
    """请求参数验证失败 (422)"""

    def __init__(self, message: str = "请求参数无效"):
        super().__init__(message, status_code=422)


class ServiceError(HotRewriteException):
    """服务层错误 (502) — 如 LLM API 调用失败"""

    def __init__(self, message: str = "服务暂时不可用"):
        super().__init__(message, status_code=502)


class CollectError(HotRewriteException):
    """内容采集错误 (502)"""

    def __init__(self, message: str = "内容采集失败"):
        super().__init__(message, status_code=502)
