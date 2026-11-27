from django.urls import path
from . import views

app_name = "tasks"

urlpatterns = [
    path("", views.TaskListView.as_view(), name="list"),
    path("create/", views.TaskCreateView.as_view(), name="create"),
    path("<int:task_id>/", views.TaskDetailView.as_view(), name="detail"),
    path("<int:task_id>/edit/", views.TaskUpdateView.as_view(), name="update"),
    path("<int:task_id>/delete/", views.TaskDeleteView.as_view(), name="delete"),
    path(
        "<int:task_id>/toggle-complete/",
        views.task_toggle_complete,
        name="toggle_complete",
    ),

    path(
        "categories/",
        views.CategoryListView.as_view(),
        name="category_list",
    ),
    path(
        "categories/create/",
        views.CategoryCreateView.as_view(),
        name="category_create",
    ),
    path(
        "categories/<int:category_id>/edit/",
        views.CategoryUpdateView.as_view(),
        name="category_update",
    ),
    path(
        "categories/<int:category_id>/delete/",
        views.CategoryDeleteView.as_view(),
        name="category_delete",
    ),
]

