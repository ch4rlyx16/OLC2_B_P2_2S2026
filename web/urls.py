from django.urls import path

from . import views

urlpatterns = [
    path('', views.editor, name='editor'),
    path('api/ejecutar', views.api_ejecutar, name='api_ejecutar'),
]
