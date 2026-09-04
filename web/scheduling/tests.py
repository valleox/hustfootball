from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Competition, Match, Team, Venue


class MatchPagePermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("setup_roles", stdout=StringIO())

        user_model = get_user_model()

        cls.referee = user_model.objects.create_user(
            username="test_referee",
            password="test-password",
        )
        cls.recorder = user_model.objects.create_user(
            username="test_recorder",
            password="test-password",
        )
        cls.scheduler = user_model.objects.create_user(
            username="test_scheduler",
            password="test-password",
        )
        cls.no_role_user = user_model.objects.create_user(
            username="test_no_role",
            password="test-password",
        )

        cls.referee.groups.add(
            Group.objects.get(name="裁判员")
        )
        cls.recorder.groups.add(
            Group.objects.get(name="场次录入员")
        )
        cls.scheduler.groups.add(
            Group.objects.get(name="排班管理员")
        )

        cls.competition = Competition.objects.create(
            name="测试联赛",
            season="2026测试赛季",
        )
        cls.home_team = Team.objects.create(name="测试主队")
        cls.away_team = Team.objects.create(name="测试客队")
        cls.venue = Venue.objects.create(name="测试场地")

        cls.match = Match.objects.create(
            competition=cls.competition,
            match_number="TEST-001",
            round_name="第一轮",
            kickoff_at=timezone.now() + timedelta(days=1),
            home_team=cls.home_team,
            away_team=cls.away_team,
            venue=cls.venue,
            match_level="测试级别",
            created_by=cls.recorder,
        )

    def form_data(self, **changes):
        data = {
            "competition": self.competition.pk,
            "match_number": "TEST-002",
            "round_name": "第二轮",
            "kickoff_at": timezone.localtime(
                self.match.kickoff_at
            ).strftime("%Y-%m-%dT%H:%M"),
            "home_team": self.home_team.pk,
            "away_team": self.away_team.pk,
            "venue": self.venue.pk,
            "match_level": "测试级别",
            "status": Match.Status.SCHEDULED,
            "notes": "测试备注",
        }
        data.update(changes)
        return data

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(
            reverse("scheduling:match_list")
        )

        self.assertRedirects(
            response,
            "/accounts/login/?next=/matches/",
            fetch_redirect_response=False,
        )

    def test_user_without_role_receives_403(self):
        self.client.force_login(self.no_role_user)

        response = self.client.get(
            reverse("scheduling:match_list")
        )

        self.assertEqual(response.status_code, 403)

    def test_referee_can_view_but_cannot_change_matches(self):
        self.client.force_login(self.referee)

        list_response = self.client.get(
            reverse("scheduling:match_list")
        )
        detail_response = self.client.get(
            reverse(
                "scheduling:match_detail",
                args=[self.match.pk],
            )
        )
        create_response = self.client.get(
            reverse("scheduling:match_create")
        )
        update_response = self.client.get(
            reverse(
                "scheduling:match_update",
                args=[self.match.pk],
            )
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(create_response.status_code, 403)
        self.assertEqual(update_response.status_code, 403)

    def test_editing_roles_can_open_match_forms(self):
        for user in (self.recorder, self.scheduler):
            with self.subTest(username=user.username):
                self.client.force_login(user)

                create_response = self.client.get(
                    reverse("scheduling:match_create")
                )
                update_response = self.client.get(
                    reverse(
                        "scheduling:match_update",
                        args=[self.match.pk],
                    )
                )

                self.assertEqual(
                    create_response.status_code,
                    200,
                )
                self.assertEqual(
                    update_response.status_code,
                    200,
                )

    def test_recorder_can_create_match(self):
        self.client.force_login(self.recorder)
        original_count = Match.objects.count()

        response = self.client.post(
            reverse("scheduling:match_create"),
            self.form_data(),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Match.objects.count(),
            original_count + 1,
        )

        created_match = Match.objects.latest("pk")
        self.assertEqual(
            created_match.created_by,
            self.recorder,
        )
        self.assertEqual(
            created_match.assignment_status,
            Match.AssignmentStatus.DRAFT,
        )

    def test_recorder_can_update_match(self):
        self.client.force_login(self.recorder)

        response = self.client.post(
            reverse(
                "scheduling:match_update",
                args=[self.match.pk],
            ),
            self.form_data(round_name="修改后的轮次"),
        )

        self.assertEqual(response.status_code, 302)

        self.match.refresh_from_db()
        self.assertEqual(
            self.match.round_name,
            "修改后的轮次",
        )
        self.assertEqual(
            self.match.created_by,
            self.recorder,
        )

    def test_same_home_and_away_team_is_rejected(self):
        self.client.force_login(self.recorder)
        original_count = Match.objects.count()

        response = self.client.post(
            reverse("scheduling:match_create"),
            self.form_data(away_team=self.home_team.pk),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "主队和客队不能是同一支球队",
        )
        self.assertEqual(
            Match.objects.count(),
            original_count,
        )
