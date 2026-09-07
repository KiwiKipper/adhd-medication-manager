from django.shortcuts import render, HttpResponse

# Create your views here.
def home(request):
    return render(request, "home.html")


def todos(request):
    items = TodoItem.objects.all()
    return render(request, "todos.html", {"todos": items})