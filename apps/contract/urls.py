from django.urls import path
from .views import (
    RegistryListView,
    RegistryDetailView,
    CreateRegistryView,
    DeployRegistryView,
    AddRegistryUsersView,
    UpdateUserDataView,
    PrepareDeploymentView,
    ConfirmDeploymentView
)

urlpatterns = [
    path('registries/', RegistryListView.as_view(), name='registry_list'),
    path('registries/<int:pk>/', RegistryDetailView.as_view(), name='registry_detail'),
    path('registries/create/', CreateRegistryView.as_view(), name='registry_create'),
    path('registries/<int:pk>/deploy/', DeployRegistryView.as_view(), name='registry_deploy'),
    path('registries/<int:pk>/add-users/', AddRegistryUsersView.as_view(), name='registry_add_users'),
    path('registries/<int:pk>/update-data/', UpdateUserDataView.as_view(), name='update_user_data'),
    path('registries/<int:pk>/prepare-deployment/', PrepareDeploymentView.as_view(), name='prepare_deployment'),
    path('registries/<int:pk>/confirm-deployment/', ConfirmDeploymentView.as_view(), name='confirm_deployment'),
]