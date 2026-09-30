from django.test import TestCase
from django.contrib.auth.models import User, Group
from django.core.management import call_command
from django.urls import reverse
from .models import Team

class DeploymentSmokeTests(TestCase):
    def test_home_redirects_to_protected_admin(self):
        response = self.client.get("/", follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertEqual(response.redirect_chain[0], ("/admin/", 302))

    def test_admin_can_login_and_create_team(self):
        User.objects.create_superuser("test-admin", "admin@example.test", "test-password")
        self.assertTrue(self.client.login(username="test-admin", password="test-password"))
        response = self.client.post(reverse("admin:scheduling_team_add"), {
            "name": "Deployment test team", "short_name": "TEST", "is_active": "on", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Team.objects.filter(name="Deployment test team").exists())

    def test_role_setup_is_repeatable(self):
        call_command("setup_roles", verbosity=0)
        before = {group.name: set(group.permissions.values_list("pk", flat=True)) for group in Group.objects.all()}
        call_command("setup_roles", verbosity=0)
        after = {group.name: set(group.permissions.values_list("pk", flat=True)) for group in Group.objects.all()}
        self.assertEqual(before, after)
        self.assertEqual(len(after), 3)
        self.assertTrue(all(after.values()))
