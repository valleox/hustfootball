from django.apps import AppConfig, apps


class SchedulingConfig(AppConfig):
    name = "scheduling"
    verbose_name = "裁判排班"

    def ready(self):
        # django-axes 的应用名称不支持翻译，在这里改成中文显示在后台。
        if apps.is_installed("axes"):
            apps.get_app_config("axes").verbose_name = "登录安全"

            from axes.admin import AccessAttemptAdmin

            # 该列标题由方法名生成，无法通过翻译文件修改。
            AccessAttemptAdmin.status.short_description = "状态"
