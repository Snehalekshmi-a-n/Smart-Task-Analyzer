from datetime import date, timedelta

from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .scoring import score_tasks


class TaskAnalyzerEndpointsTests(APITestCase):
    def setUp(self):
        from . import views

        views._LATEST_ANALYSIS = None
        views._LATEST_INPUT = None

        self.payload = {
            "strategy": "high_impact",
            "tasks": [
                {
                    "title": "Fix login bug",
                    "due_date": "2025-11-30",
                    "estimated_hours": 3,
                    "importance": 8,
                    "dependencies": [],
                },
                {
                    "title": "Update onboarding docs",
                    "estimated_hours": 5,
                    "importance": 4,
                    "dependencies": [1],
                },
            ],
        }

    def test_analyze_returns_scores(self):
        response = self.client.post(
            reverse("task-analyze"), self.payload, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["strategy"], "high_impact")
        self.assertEqual(len(response.data["tasks"]), 2)
        self.assertTrue(all("score" in task for task in response.data["tasks"]))

    def test_suggest_reuses_latest_payload(self):
        self.client.post(reverse("task-analyze"), self.payload, format="json")
        response = self.client.get(
            reverse("task-suggest") + "?limit=1&strategy=fastest_wins"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["strategy"], "fastest_wins")
        self.assertEqual(len(response.data["tasks"]), 1)

    def test_suggest_without_analysis_fails(self):
        response = self.client.get(reverse("task-suggest"))
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ScoringLogicTests(SimpleTestCase):
    def test_overdue_tasks_have_higher_urgency(self):
        today = date.today()
        tasks = [
            {
                "title": "Overdue bug",
                "due_date": (today - timedelta(days=1)).isoformat(),
                "estimated_hours": 2,
                "importance": 5,
                "dependencies": [],
            },
            {
                "title": "Future task",
                "due_date": (today + timedelta(days=10)).isoformat(),
                "estimated_hours": 2,
                "importance": 5,
                "dependencies": [],
            },
        ]

        result = score_tasks(tasks, strategy="deadline_driven")
        scores = {task["title"]: task["score"] for task in result["tasks"]}
        self.assertGreater(scores["Overdue bug"], scores["Future task"])

    def test_high_importance_dominates_in_high_impact(self):
        today = date.today().isoformat()
        tasks = [
            {
                "title": "Critical feature",
                "due_date": today,
                "estimated_hours": 4,
                "importance": 10,
                "dependencies": [],
            },
            {
                "title": "Minor enhancement",
                "due_date": today,
                "estimated_hours": 4,
                "importance": 2,
                "dependencies": [],
            },
        ]
        result = score_tasks(tasks, strategy="high_impact")
        scores = {task["title"]: task["score"] for task in result["tasks"]}
        self.assertGreater(scores["Critical feature"], scores["Minor enhancement"])

    def test_dependency_bonus_in_smart_balance(self):
        today = date.today().isoformat()
        tasks = [
            {
                "title": "Foundation task",
                "due_date": today,
                "estimated_hours": 4,
                "importance": 5,
                "dependencies": [],
            },
            {
                "title": "Follow-up task",
                "due_date": today,
                "estimated_hours": 4,
                "importance": 5,
                "dependencies": [1],
            },
        ]
        result = score_tasks(tasks, strategy="smart_balance")
        scores = {task["title"]: task["score"] for task in result["tasks"]}
        self.assertGreater(scores["Foundation task"], scores["Follow-up task"])
