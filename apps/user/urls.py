from django.urls import path
from .views import LogoutView, RegisterView, LoginView, GetNonceView, VerifySignatureView, dashboard

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('get-nonce/', GetNonceView.as_view(), name='get_nonce'),
    path('verify-signature/', VerifySignatureView.as_view(), name='verify_signature'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('dashboard/', dashboard, name='dashboard'),
]