from django.shortcuts import render

from .models import Match

def schedule_basic(request):
    return render(request, 'fllfms/schedule_basic.html', context={
        'matches': Match.objects.all().order_by('schedule', 'number')})
