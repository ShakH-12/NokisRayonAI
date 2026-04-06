from django.db import models


class Prompts(models.Model):
    user_ip = models.GenericIPAddressField(blank=True, null=True)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Prompt: {self.text[:30]}'

    class Meta:
        verbose_name = 'Prompt'
        verbose_name_plural = 'Prompts'