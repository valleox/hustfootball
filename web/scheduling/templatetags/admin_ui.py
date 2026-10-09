from django import template

register = template.Library()

# 后台首页磁贴：图标与一句话说明
MODEL_TILES = {
    "scheduling.match": ("⚽", "录入比赛、批量发布裁判安排"),
    "scheduling.matchassignmentsummary": ("📋", "每场比赛一行，查看四个岗位的反馈"),
    "scheduling.refereeprofile": ("🧑‍⚖️", "裁判的姓名、等级与联系方式"),
    "scheduling.competition": ("🏆", "联赛、杯赛等赛事与赛季"),
    "scheduling.team": ("👕", "参赛的学院与球队"),
    "scheduling.venue": ("🏟️", "比赛场地与位置"),
    "scheduling.invitecode": ("🎟️", "发给裁判的自助注册邀请码"),
    "scheduling.notification": ("🔔", "已发送的站内通知记录"),
    "auth.user": ("👤", "登录账号、密码与所属角色"),
    "auth.group": ("👥", "角色及其权限"),
    "axes.accessattempt": ("🔒", "被锁定或多次失败的账号"),
    "axes.accessfailurelog": ("🧾", "每一次失败登录的明细"),
    "axes.accesslog": ("🗂️", "所有登录与退出记录"),
}

APP_ORDER = ["scheduling", "auth", "axes"]


def _key(app_label, model):
    return f"{app_label}.{model['object_name'].lower()}"


@register.filter
def tile_icon(model, app_label):
    return MODEL_TILES.get(_key(app_label, model), ("📁", ""))[0]


@register.filter
def tile_description(model, app_label):
    return MODEL_TILES.get(_key(app_label, model), ("", ""))[1]


@register.filter
def ordered_apps(app_list):
    """业务功能放在最前面，账号和登录安全放后面。"""
    def rank(app):
        label = app["app_label"]
        return APP_ORDER.index(label) if label in APP_ORDER else len(APP_ORDER)

    return sorted(app_list, key=rank)
