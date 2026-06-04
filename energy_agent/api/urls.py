from django.urls import path
from . import views

urlpatterns = [
    path('health', views.health_view, name='health'),
    path('telemetry', views.telemetry_view, name='telemetry'),
    path('zones', views.create_zone, name='create_zone'),
    path('zones/<str:zone_id>', views.zone_detail, name='zone_detail'),
    path('agents/toggle', views.toggle_agent_control, name='toggle_agent_control'),
    path('error-simulation', views.error_simulation, name='error_simulation'),
    path('optimize/', views.optimize_environment, name='optimize_environment'),
    
    # Dynamic creation routes (no fixtures)
    path('agents', views.create_agent, name='create_agent'),
    path('alerts', views.create_alert, name='create_alert'),
    path('reports', views.create_report, name='create_report'),
]
