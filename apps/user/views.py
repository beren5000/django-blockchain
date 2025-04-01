from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.views.generic import View
from django.http import JsonResponse
from django.utils.crypto import get_random_string
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.contrib import messages

from .models import User
from .forms import UserRegistrationForm, UserLoginForm

import json
import secrets
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.auto import w3

# Traditional Email/Password Authentication Views
class RegisterView(View):
    template_name = 'user/register.html'
    
    def get(self, request):
        form = UserRegistrationForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.save()
            messages.success(request, "Registration successful. Please log in.")
            return redirect('login')
        return render(request, self.template_name, {'form': form})

class LoginView(View):
    template_name = 'user/login.html'
    
    def get(self, request):
        form = UserLoginForm()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, "Invalid email or password")
        return render(request, self.template_name, {'form': form})

# Blockchain Wallet Authentication Views
@method_decorator(csrf_exempt, name='dispatch')
class GetNonceView(View):
    def post(self, request):
        data = json.loads(request.body)
        wallet_address = data.get('wallet_address')
        
        if not wallet_address:
            return JsonResponse({'error': 'Wallet address is required'}, status=400)
        
        # Generate a random nonce
        nonce = secrets.token_hex(32)
        
        # Find or create user with this wallet address
        user, created = User.objects.get_or_create(
            wallet_address=wallet_address,
            defaults={'email': f'{wallet_address[:8]}@blockchain.user'}
        )
        
        # Update user's nonce
        user.nonce = nonce
        user.save()
        
        # Return nonce to the client for signing
        return JsonResponse({'nonce': nonce})

@method_decorator(csrf_exempt, name='dispatch')
class VerifySignatureView(View):
    def post(self, request):
        data = json.loads(request.body)
        wallet_address = data.get('wallet_address')
        signature = data.get('signature')
        
        if not wallet_address or not signature:
            return JsonResponse({'error': 'Wallet address and signature are required'}, status=400)
        
        try:
            # Get the user and their nonce
            user = User.objects.get(wallet_address=wallet_address)
            nonce = user.nonce
            
            # Message to verify
            message = f"Sign this message to login: {nonce}"
            
            # Verify the signature
            message_hash = encode_defunct(text=message)
            recovered_address = w3.eth.account.recover_message(message_hash, signature=signature)
            
            # Check if recovered address matches
            if recovered_address.lower() == wallet_address.lower():
                # Generate a new nonce for next login
                user.nonce = secrets.token_hex(32)
                user.save()
                
                # Log the user in
                login(request, user)
                return JsonResponse({'success': True, 'message': 'Authentication successful'})
            else:
                return JsonResponse({'error': 'Invalid signature'}, status=401)
                
        except User.DoesNotExist:
            return JsonResponse({'error': 'User not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)


class LogoutView(View):
    def get(self, request):
        logout(request)
        messages.success(request, "You have been logged out successfully.")
        return redirect('login')
    

@login_required
def dashboard(request):
    return render(request, 'user/dashboard.html')