from django.urls import path
from . import views

app_name = 'web_view'

urlpatterns = [
    path('upload/',views.UploadView.as_view(),name='upload'),
    path('chat/',views.AskView.as_view(),name='ask'),
    path('voice-chat/',views.VoiceChatView.as_view(),name='voice-ask'),
]