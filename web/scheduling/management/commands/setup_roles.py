from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "创建足协系统用户组并配置权限"

    def get_permissions(self, permission_codes):
        permissions = Permission.objects.filter(
            content_type__app_label="scheduling",
            codename__in=permission_codes,
        )

        found_codes = set(
            permissions.values_list("codename", flat=True)
        )
        missing_codes = set(permission_codes) - found_codes

        if missing_codes:
            missing_text = ", ".join(sorted(missing_codes))
            raise CommandError(
                f"以下权限不存在：{missing_text}"
            )

        return permissions

    def handle(self, *args, **options):
        referee_permissions = {
            "view_competition",
            "view_team",
            "view_venue",
            "view_match",
            "view_assignment",
        }

        recorder_permissions = referee_permissions | {
            "add_competition",
            "change_competition",
            "add_team",
            "change_team",
            "add_venue",
            "change_venue",
            "add_match",
            "change_match",
        }

        scheduler_permissions = recorder_permissions | {
            "view_refereeprofile",
            "add_assignment",
            "change_assignment",
            "delete_assignment",
            "publish_assignments",
        }

        roles = {
            "裁判员": referee_permissions,
            "场次录入员": recorder_permissions,
            "排班管理员": scheduler_permissions,
        }

        for group_name, permission_codes in roles.items():
            group, created = Group.objects.get_or_create(
                name=group_name
            )
            group.permissions.set(
                self.get_permissions(permission_codes)
            )

            action = "创建" if created else "更新"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action}用户组：{group_name}，"
                    f"权限数量：{len(permission_codes)}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS("所有用户组配置完成。")
        )
