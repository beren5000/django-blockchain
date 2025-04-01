from django.db import models
from apps.user.models import User

class UserDataRegistry(models.Model):

    NETWORK_CHOICES = [
        ('sepolia', 'Ethereum Sepolia Testnet'),
        ('goerli', 'Ethereum Goerli Testnet'),
        ('mumbai', 'Polygon Mumbai Testnet'),
    ]

    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    admin = models.ForeignKey(User, on_delete=models.CASCADE, related_name='administered_registries')
    
    # Deployment information
    address = models.CharField(max_length=42, blank=True, null=True)
    transaction_hash = models.CharField(max_length=66, blank=True, null=True)
    network = models.CharField(max_length=50, default='sepolia', choices=NETWORK_CHOICES)
    deployed = models.BooleanField(default=False)
    deployment_date = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({'Deployed' if self.deployed else 'Not Deployed'})"
    
    class Meta:
        verbose_name = "User Data Registry"
        verbose_name_plural = "User Data Registries"


class RegistryUser(models.Model):
    registry = models.ForeignKey(UserDataRegistry, on_delete=models.CASCADE, related_name='users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='registry_memberships')
    wallet_address = models.CharField(max_length=42)
    is_authorized = models.BooleanField(default=True)
    
    # User data (duplicated from blockchain for quick access)
    image_reference = models.TextField(blank=True, null=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} in {self.registry.name}"
    
    class Meta:
        unique_together = ['registry', 'wallet_address']
