from rest_framework import serializers
from .models import Prompts


class PromptsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Prompts
        fields = ('text',)