from __future__ import annotations

from typing import Any, Dict, List

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .scoring import DEFAULT_STRATEGY, STRATEGY_CHOICES, score_tasks
from .serializers import AnalyzeRequestSerializer

_LATEST_ANALYSIS: Dict[str, Any] | None = None
_LATEST_INPUT: Dict[str, Any] | None = None


class TaskAnalyzeView(APIView):
    """
    Accepts a batch of tasks, scores them, and caches the result.
    """

    def post(self, request, *args, **kwargs):
        serializer = AnalyzeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        strategy: str = serializer.validated_data["strategy"]
        tasks_payload: List[dict] = serializer.validated_data["tasks"]

        analysis = score_tasks(tasks_payload, strategy=strategy)
        generated_at = timezone.now()

        global _LATEST_ANALYSIS, _LATEST_INPUT
        _LATEST_INPUT = {
            "tasks": tasks_payload,
        }
        _LATEST_ANALYSIS = {
            "generated_at": generated_at,
            **analysis,
        }

        return Response(_LATEST_ANALYSIS, status=status.HTTP_200_OK)


class TaskSuggestView(APIView):
    """
    Returns the highest priority tasks from the most recent analysis.
    """

    def get(self, request, *args, **kwargs):
        if not _LATEST_INPUT:
            return Response(
                {"detail": "No analysis available. POST to /api/tasks/analyze/ first."},
                status=status.HTTP_404_NOT_FOUND,
            )

        limit_param = request.query_params.get("limit")
        strategy_param = request.query_params.get("strategy", DEFAULT_STRATEGY)

        if strategy_param not in STRATEGY_CHOICES:
            return Response(
                {"detail": f"strategy must be one of {', '.join(STRATEGY_CHOICES)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            limit = int(limit_param) if limit_param is not None else 3
        except ValueError:
            return Response(
                {"detail": "limit must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if limit <= 0:
            limit = 1

        analysis = score_tasks(_LATEST_INPUT["tasks"], strategy=strategy_param)
        generated_at = (
            _LATEST_ANALYSIS["generated_at"] if _LATEST_ANALYSIS else timezone.now()
        )
        tasks = analysis["tasks"][:limit]
        return Response(
            {
                "generated_at": generated_at,
                "strategy": strategy_param,
                "limit": limit,
                "tasks": tasks,
                "summary": analysis["summary"],
            },
            status=status.HTTP_200_OK,
        )
