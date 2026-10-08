def client_ip(request):
    """返回访问者 IP，仅用于登录失败记录。

    Vercel 会覆盖 X-Forwarded-For，第一项即真实客户端地址；
    其他环境退回到 REMOTE_ADDR。
    """
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")
