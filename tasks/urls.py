from django.urls import path

from .views import TaskAnalyzeView, TaskSuggestView

urlpatterns = [
    path('analyze/', TaskAnalyzeView.as_view(), name='task-analyze'),
    path('suggest/', TaskSuggestView.as_view(), name='task-suggest'),
]

