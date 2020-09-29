from django.shortcuts import render
from .models import Course


# Create your views here.
def all_courses(request):
    courses = Course.objects.all()
    return render(request, "courses.html", {"courses": courses})
