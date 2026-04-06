from django.shortcuts import render
from django.views import View


class UploadView(View):
    def get(self,request):
        return render(request,'upload.html')


class AskView(View):
    def get(self,request):
        return render(request,'ask.html')


class VoiceChatView(View):

    def get(self,request):
        return render(request, "voice.html")