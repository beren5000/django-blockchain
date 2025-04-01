from django import forms
from .models import UserDataRegistry, RegistryUser
from apps.user.models import User

class RegistryCreationForm(forms.ModelForm):
    whitelist_addresses = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 4,
            'placeholder': '0x1234567890abcdef1234567890abcdef12345678\n0xabcdef1234567890abcdef1234567890abcdef12\n...'
        }),
        required=False,
        help_text="Enter Ethereum addresses (one per line) to whitelist. Leave empty to only include yourself."
    )
    
    class Meta:
        model = UserDataRegistry
        fields = ['name', 'description', 'network']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'network': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_whitelist_addresses(self):
        addresses = self.cleaned_data.get('whitelist_addresses', '')
        if not addresses.strip():
            return []
            
        # Split by newline and clean
        address_list = [addr.strip() for addr in addresses.split('\n') if addr.strip()]
        
        # Basic validation for Ethereum addresses
        for addr in address_list:
            if not addr.startswith('0x') or len(addr) != 42:
                raise forms.ValidationError(f"'{addr}' is not a valid Ethereum address. It should start with '0x' and be 42 characters long.")
        
        return address_list

class UserAdditionForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.filter(wallet_address__isnull=False),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        label="Select Users to Add"
    )

class UserDataUpdateForm(forms.Form):
    image_reference = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label="Image Reference (IPFS CID or URL)",
        help_text="Enter an IPFS hash (recommended) or URL for your image"
    )