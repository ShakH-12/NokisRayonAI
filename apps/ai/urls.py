from django.urls import path
from . import views

app_name = 'ai'

urlpatterns = [
    path('upload_data/', views.UploadFileView.as_view(), name='upload_data'),
    path('ask/', views.AskView.as_view(), name='ask'),
    path('voice/', views.VoiceChatView.as_view(), name='voice_chat'),
    path('prompt/', views.ListCreatePrompt.as_view(), name='prompt'),
]