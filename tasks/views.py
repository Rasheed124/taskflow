from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from .forms import TaskForm, CategoryForm
from .models import Task, Category

TASKS_PER_PAGE = 3


class RequestUserFormMixin:
    """Pass the authenticated user to a user-aware model form."""

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs


class UserOwnedTaskQuerysetMixin:
    """Limit object lookup to tasks owned by the authenticated user."""

    def get_queryset(self):
        return Task.objects.filter(user=self.request.user)


class TaskListView(LoginRequiredMixin, ListView):
    model = Task
    template_name = "tasks/task_list.html"
    context_object_name = "tasks"
    paginate_by = TASKS_PER_PAGE
    http_method_names = ["get"]

    def get(self, request, *args, **kwargs):
        # Canonicalize blank filters while preserving the existing URL behavior.
        params = request.GET.copy()
        for key in list(params.keys()):
            if not params.get(key, "").strip():
                params.pop(key)

        if params.urlencode() != request.GET.urlencode():
            if params:
                return redirect(f"{request.path}?{params.urlencode()}")
            return redirect(request.path)

        return super().get(request, *args, **kwargs)

    def paginate_queryset(self, queryset, page_size):
        """Keep forgiving page-number handling from the previous view."""
        paginator = self.get_paginator(
            queryset,
            page_size,
            orphans=self.get_paginate_orphans(),
            allow_empty_first_page=self.get_allow_empty(),
        )
        page_number = (
            self.kwargs.get(self.page_kwarg)
            or self.request.GET.get(self.page_kwarg)
            or 1
        )
        page = paginator.get_page(page_number)
        return paginator, page, page.object_list, page.has_other_pages()

    def get_queryset(self):
        self.today = timezone.localdate()
        self.user_tasks = Task.objects.filter(user=self.request.user)
        tasks = self.user_tasks

        self.query = self.request.GET.get("q", "").strip()
        self.status = self.request.GET.get("status", "")
        self.priority = self.request.GET.get("priority", "")
        self.sort = self.request.GET.get("sort", "newest")
        self.schedule = self.request.GET.get("schedule", "")

        if self.query:
            tasks = tasks.filter(
                Q(title__icontains=self.query)
                | Q(description__icontains=self.query)
            )

        if self.status == "completed":
            tasks = tasks.filter(completed=True)
        elif self.status == "pending":
            tasks = tasks.filter(completed=False)

        if self.priority in Task.Priority.values:
            tasks = tasks.filter(priority=self.priority)

        if self.schedule == "today":
            tasks = tasks.filter(due_date=self.today)
        elif self.schedule == "upcoming":
            tasks = tasks.filter(due_date__gt=self.today)
        elif self.schedule == "overdue":
            tasks = tasks.filter(
                due_date__lt=self.today,
                completed=False,
            )

        sort_options = {
            "newest": ("-created_at",),
            "oldest": ("created_at",),
            "due_earliest": ("due_date", "-created_at"),
            "due_latest": ("-due_date", "-created_at"),
        }
        priority_order = Case(
            When(priority="high", then=Value(1)),
            When(priority="medium", then=Value(2)),
            When(priority="low", then=Value(3)),
            output_field=IntegerField(),
        )

        if self.sort == "priority_high":
            return tasks.order_by(priority_order, "-created_at")
        if self.sort == "priority_low":
            return tasks.order_by(priority_order.desc(), "-created_at")

        return tasks.order_by(
            *sort_options.get(self.sort, sort_options["newest"])
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        pagination_params = self.request.GET.copy()
        pagination_params.pop("page", None)
        stats = self.user_tasks.aggregate(
            total_count=Count("id"),
            completed_count=Count("id", filter=Q(completed=True)),
            pending_count=Count("id", filter=Q(completed=False)),
            overdue_count=Count(
                "id",
                filter=Q(due_date__lt=self.today, completed=False),
            ),
        )
        total_count = stats["total_count"]
        completion_rate = (
            stats["completed_count"] / total_count * 100
            if total_count
            else 0
        )

        context.update(
            {
                "page_base_url": pagination_params.urlencode(),
                "query": self.query,
                "status": self.status,
                "priority": self.priority,
                "sort": self.sort,
                "schedule": self.schedule,
                "today": self.today,
                "total_tasks": total_count,
                "completed_tasks": stats["completed_count"],
                "pending_tasks": stats["pending_count"],
                "overdue_tasks": stats["overdue_count"],
                "completion_rate": round(completion_rate),
            }
        )
        return context


class TaskCreateView(LoginRequiredMixin, RequestUserFormMixin, CreateView):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    success_url = reverse_lazy("tasks:list")
    http_method_names = ["get", "post"]

    def form_valid(self, form):
        # Set the owner before model validation; the form only exposes
        # categories belonging to this same user.
        form.instance.user = self.request.user
        form.instance.full_clean()
        response = super().form_valid(form)
        messages.success(self.request, "Task created successfully.")
        return response


class TaskDetailView(
    LoginRequiredMixin,
    UserOwnedTaskQuerysetMixin,
    DetailView,
):
    model = Task
    template_name = "tasks/task_detail.html"
    context_object_name = "task"
    pk_url_kwarg = "task_id"
    http_method_names = ["get"]


class TaskUpdateView(
    LoginRequiredMixin,
    UserOwnedTaskQuerysetMixin,
    RequestUserFormMixin,
    UpdateView,
):
    model = Task
    form_class = TaskForm
    template_name = "tasks/task_form.html"
    context_object_name = "task"
    pk_url_kwarg = "task_id"
    http_method_names = ["get", "post"]

    def get_success_url(self):
        return reverse(
            "tasks:detail",
            kwargs={"task_id": self.object.pk},
        )


class TaskDeleteView(
    LoginRequiredMixin,
    UserOwnedTaskQuerysetMixin,
    DeleteView,
):
    model = Task
    template_name = "tasks/task_confirm_delete.html"
    context_object_name = "task"
    pk_url_kwarg = "task_id"
    success_url = reverse_lazy("tasks:list")
    http_method_names = ["get", "post"]


@login_required
@require_POST
def task_toggle_complete(request, task_id):
    task = get_object_or_404(
        Task,
        pk=task_id,
        user=request.user,
    )

    task.completed = not task.completed
    task.save(update_fields=["completed", "updated_at"])

    return redirect("tasks:list")




# ==================================== CATEGORY VIEWS REDERNG =============================================================


class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "tasks/categories/category_list.html"
    context_object_name = "categories"
    http_method_names = ["get"]

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user).annotate(
            task_count=Count(
                "tasks",
                filter=Q(tasks__user=self.request.user),
            )
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task_stats = Task.objects.filter(user=self.request.user).aggregate(
            categorized_tasks=Count(
                "id",
                filter=Q(category__isnull=False),
            ),
            uncategorized_tasks=Count(
                "id",
                filter=Q(category__isnull=True),
            ),
        )
        context.update(
            {
                "total_categories": self.object_list.count(),
                **task_stats,
            }
        )
        return context


class UserOwnedCategoryQuerysetMixin:
    """Limit category lookup to the current user's categories."""

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)


class CategoryCreateView(
    LoginRequiredMixin,
    RequestUserFormMixin,
    CreateView,
):
    model = Category
    form_class = CategoryForm
    template_name = "tasks/categories/category_form.html"
    success_url = reverse_lazy("tasks:category_list")
    http_method_names = ["get", "post"]

    def form_valid(self, form):
        form.instance.user = self.request.user
        response = super().form_valid(form)
        messages.success(self.request, "Category created successfully.")
        return response


class CategoryUpdateView(
    LoginRequiredMixin,
    UserOwnedCategoryQuerysetMixin,
    RequestUserFormMixin,
    UpdateView,
):
    model = Category
    form_class = CategoryForm
    template_name = "tasks/categories/category_form.html"
    context_object_name = "category"
    pk_url_kwarg = "category_id"
    success_url = reverse_lazy("tasks:category_list")
    http_method_names = ["get", "post"]


class CategoryDeleteView(
    LoginRequiredMixin,
    UserOwnedCategoryQuerysetMixin,
    DeleteView,
):
    model = Category
    template_name = "tasks/categories/category_confirm_delete.html"
    context_object_name = "category"
    pk_url_kwarg = "category_id"
    success_url = reverse_lazy("tasks:category_list")
    http_method_names = ["get", "post"]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["task_count"] = self.object.tasks.count()
        return context
