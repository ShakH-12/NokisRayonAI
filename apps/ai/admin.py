from django.contrib import admin
from .models import Prompts


@admin.register(Prompts)
class PromptsAdmin(admin.ModelAdmin):
    list_display = ('text',)