import secrets

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class TimeStampedModel(models.Model):
    """为主要数据自动记录创建和更新时间。"""

    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    updated_at = models.DateTimeField("更新时间", auto_now=True)

    class Meta:
        abstract = True


class RefereeProfile(TimeStampedModel):
    """裁判资料。非裁判管理员可以只有账号，没有裁判资料。"""

    class Level(models.TextChoices):
        NATIONAL = "national", "国家级"
        LEVEL_1 = "level_1", "一级"
        LEVEL_2 = "level_2", "二级"
        LEVEL_3 = "level_3", "三级"
        TRAINEE = "trainee", "见习"
        OTHER = "other", "其他"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referee_profile",
        verbose_name="用户账号",
    )
    name = models.CharField("姓名", max_length=50)
    phone = models.CharField("联系电话", max_length=30, blank=True)
    level = models.CharField(
        "裁判等级",
        max_length=20,
        choices=Level.choices,
        default=Level.OTHER,
    )
    is_active = models.BooleanField("是否可参与排班", default=True)
    notes = models.TextField("备注", blank=True)

    class Meta:
        verbose_name = "裁判资料"
        verbose_name_plural = "裁判资料"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Competition(TimeStampedModel):
    """赛事，例如校级联赛、院系杯。"""

    name = models.CharField("赛事名称", max_length=100)
    season = models.CharField(
        "赛季",
        max_length=30,
        help_text="例如：2026赛季或2026春季",
    )
    is_active = models.BooleanField("是否进行中", default=True)

    class Meta:
        verbose_name = "赛事"
        verbose_name_plural = "赛事"
        ordering = ["-season", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "season"],
                name="unique_competition_season",
            )
        ]

    def __str__(self):
        return f"{self.name}（{self.season}）"


class Team(TimeStampedModel):
    """参赛球队。"""

    name = models.CharField("球队名称", max_length=100, unique=True)
    short_name = models.CharField("球队简称", max_length=30, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "球队"
        verbose_name_plural = "球队"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Venue(TimeStampedModel):
    """比赛场地。"""

    name = models.CharField("场地名称", max_length=100, unique=True)
    address = models.CharField("场地位置", max_length=200, blank=True)
    is_active = models.BooleanField("是否启用", default=True)

    class Meta:
        verbose_name = "比赛场地"
        verbose_name_plural = "比赛场地"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Match(TimeStampedModel):
    """具体比赛场次。"""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "正常进行"
        CANCELLED = "cancelled", "已取消"
        FINISHED = "finished", "已结束"

    class AssignmentStatus(models.TextChoices):
        DRAFT = "draft", "排班草稿"
        PUBLISHED = "published", "已经发布"

    competition = models.ForeignKey(
        Competition,
        on_delete=models.PROTECT,
        related_name="matches",
        verbose_name="所属赛事",
    )
    match_number = models.CharField(
        "场次编号",
        max_length=30,
        blank=True,
    )
    round_name = models.CharField(
        "轮次",
        max_length=50,
        blank=True,
        help_text="例如：小组赛第1轮、半决赛",
    )
    kickoff_at = models.DateTimeField(
        "开球时间",
        db_index=True,
    )
    home_team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="home_matches",
        verbose_name="主队",
    )
    away_team = models.ForeignKey(
        Team,
        on_delete=models.PROTECT,
        related_name="away_matches",
        verbose_name="客队",
    )
    venue = models.ForeignKey(
        Venue,
        on_delete=models.PROTECT,
        related_name="matches",
        verbose_name="比赛场地",
    )
    match_level = models.CharField(
        "赛事级别",
        max_length=50,
        blank=True,
    )
    status = models.CharField(
        "比赛状态",
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
    )
    assignment_status = models.CharField(
        "裁判安排发布状态",
        max_length=20,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.DRAFT,
        db_index=True,
    )
    published_at = models.DateTimeField(
        "安排发布时间",
        null=True,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_matches",
        verbose_name="录入人员",
        null=True,
        blank=True,
    )
    notes = models.TextField("比赛备注", blank=True)

    class Meta:
        verbose_name = "比赛"
        verbose_name_plural = "比赛"
        ordering = ["kickoff_at", "id"]
        indexes = [
            models.Index(
                fields=["assignment_status", "kickoff_at"],
                name="match_publish_time_idx",
            )
        ]
        permissions = [
            ("publish_assignments", "可以发布裁判安排"),
        ]

    def clean(self):
        super().clean()

        if (
            self.home_team_id
            and self.away_team_id
            and self.home_team_id == self.away_team_id
        ):
            raise ValidationError("主队和客队不能是同一支球队。")

    def __str__(self):
        # 后台下拉框等处显示：先赛事、轮次和对阵，再开球时间与场次编号。
        parts = [str(self.competition)]
        if self.round_name:
            parts.append(self.round_name)
        parts.append(f"{self.home_team} vs {self.away_team}")
        if self.kickoff_at:
            parts.append(
                timezone.localtime(self.kickoff_at).strftime("%m月%d日 %H:%M")
            )
        if self.match_number:
            parts.append(f"场次 {self.match_number}")
        return " · ".join(parts)


class Assignment(TimeStampedModel):
    """一场比赛中的一个裁判岗位。"""

    class Position(models.IntegerChoices):
        REFEREE = 1, "主裁判"
        ASSISTANT_1 = 2, "第一助理裁判"
        ASSISTANT_2 = 3, "第二助理裁判"
        FOURTH_OFFICIAL = 4, "第四官员"

    class ResponseStatus(models.TextChoices):
        PENDING = "pending", "待确认"
        CONFIRMED = "confirmed", "已经确认"
        LEAVE = "leave", "申请请假"

    match = models.ForeignKey(
        Match,
        on_delete=models.CASCADE,
        related_name="assignments",
        verbose_name="比赛",
    )
    referee = models.ForeignKey(
        RefereeProfile,
        on_delete=models.PROTECT,
        related_name="assignments",
        verbose_name="裁判员",
    )
    position = models.PositiveSmallIntegerField(
        "执法岗位",
        choices=Position.choices,
    )
    response_status = models.CharField(
        "确认状态",
        max_length=20,
        choices=ResponseStatus.choices,
        default=ResponseStatus.PENDING,
        db_index=True,
    )
    response_note = models.TextField(
        "确认或请假说明",
        blank=True,
    )
    responded_at = models.DateTimeField(
        "回应时间",
        null=True,
        blank=True,
    )
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_assignments",
        verbose_name="排班人员",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "裁判安排明细"
        verbose_name_plural = "裁判安排明细"
        ordering = ["match__kickoff_at", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["match", "position"],
                name="unique_match_position",
            ),
            models.UniqueConstraint(
                fields=["match", "referee"],
                name="unique_referee_per_match",
            ),
        ]

    def __str__(self):
        return (
            f"{self.match} - "
            f"{self.get_position_display()} - "
            f"{self.referee}"
        )


# 去掉容易混淆的 0/O、1/I/L，方便口头或截图传播。
INVITE_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_invite_code():
    return "".join(
        secrets.choice(INVITE_CODE_ALPHABET) for _ in range(10)
    )


class InviteCode(TimeStampedModel):
    """裁判自助注册使用的邀请码。"""

    code = models.CharField(
        "邀请码",
        max_length=40,
        unique=True,
        default=generate_invite_code,
        help_text="注册时不区分大小写。建议使用自动生成的随机码。",
    )
    note = models.CharField(
        "备注",
        max_length=100,
        blank=True,
        help_text="例如：2026 秋季裁判群",
    )
    is_active = models.BooleanField("是否启用", default=True)
    expires_at = models.DateTimeField(
        "过期时间",
        null=True,
        blank=True,
        help_text="留空表示不过期。",
    )
    max_uses = models.PositiveIntegerField(
        "最多使用次数",
        null=True,
        blank=True,
        help_text="留空表示不限次数。",
    )
    used_count = models.PositiveIntegerField("已使用次数", default=0)

    class Meta:
        verbose_name = "邀请码"
        verbose_name_plural = "邀请码"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def is_usable(self):
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def __str__(self):
        return self.note or self.code


class Notification(models.Model):
    """站内通知；配置了邮件服务时同时发送邮件。"""

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="接收人",
    )
    message = models.TextField("内容")
    link = models.CharField("链接", max_length=200, blank=True)
    created_at = models.DateTimeField("创建时间", auto_now_add=True)
    read_at = models.DateTimeField("阅读时间", null=True, blank=True)

    class Meta:
        verbose_name = "通知"
        verbose_name_plural = "通知"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["recipient", "read_at"],
                name="notification_unread_idx",
            )
        ]

    def __str__(self):
        return self.message[:40]


class MatchAssignmentSummary(Match):
    """后台「裁判安排」列表：每场比赛一行，四个岗位并排显示。"""

    class Meta:
        proxy = True
        verbose_name = "裁判安排"
        verbose_name_plural = "裁判安排"
