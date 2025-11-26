from __future__ import annotations

from typing import List

from rest_framework import serializers

from .scoring import DEFAULT_STRATEGY, STRATEGY_CHOICES


class TaskSerializer(serializers.Serializer):
    """
    Validates a single task payload and applies Smart Task Analyzer defaults.
    """

    id = serializers.IntegerField(read_only=True)
    title = serializers.CharField(allow_blank=False, trim_whitespace=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    estimated_hours = serializers.FloatField(required=False, min_value=0.1)
    importance = serializers.IntegerField(required=False, min_value=1, max_value=10)
    dependencies = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )

    def validate_title(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise serializers.ValidationError("Title is required.")
        return cleaned

    def validate(self, attrs: dict) -> dict:
        hours = attrs.get('estimated_hours')
        attrs['estimated_hours'] = float(hours) if hours else 2.0

        importance = attrs.get('importance')
        attrs['importance'] = int(importance) if importance else 5

        attrs['dependencies'] = attrs.get('dependencies') or []
        return attrs


class AnalyzeRequestSerializer(serializers.Serializer):
    """
    Wraps the full /analyze payload including optional strategy selection.
    """

    strategy = serializers.ChoiceField(
        choices=STRATEGY_CHOICES, required=False, allow_blank=False
    )
    tasks = TaskSerializer(many=True, allow_empty=False)

    def validate(self, attrs: dict) -> dict:
        tasks = attrs.get('tasks') or []
        if not tasks:
            raise serializers.ValidationError({"tasks": "Provide at least one task."})

        known_ids = set(range(1, len(tasks) + 1))
        for idx, task in enumerate(tasks, start=1):
            task['id'] = idx
            cleaned_deps: List[int] = []
            for dep in task.get('dependencies', []):
                if dep not in known_ids:
                    raise serializers.ValidationError(
                        {"dependencies": f"Task {idx} references unknown id {dep}."}
                    )
                if dep == idx:
                    raise serializers.ValidationError(
                        {"dependencies": f"Task {idx} cannot depend on itself."}
                    )
                cleaned_deps.append(dep)
            task['dependencies'] = cleaned_deps

        attrs['strategy'] = attrs.get('strategy') or DEFAULT_STRATEGY
        attrs['tasks'] = tasks
        return attrs