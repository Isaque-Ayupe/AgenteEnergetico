from django.urls import path
from . import views

urlpatterns = [
    path('optimize/', views.optimize_environment, name='optimize_environment'),
]
