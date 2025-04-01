from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, CreateView, FormView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from .models import UserDataRegistry, RegistryUser
from .forms import RegistryCreationForm, UserAdditionForm, UserDataUpdateForm
from .services import RegistryDeploymentService

import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

import logging
logger = logging.getLogger(__name__)

class RegistryListView(LoginRequiredMixin, ListView):
    model = UserDataRegistry
    template_name = 'contract/registry_list.html'
    context_object_name = 'registries'
    
    def get_queryset(self):
        # Show registries where user is admin or member
        user = self.request.user
        # Use Q objects to combine the conditions in a single query
        return UserDataRegistry.objects.filter(
            Q(admin=user) | Q(users__user=user)
        ).distinct()

class RegistryDetailView(LoginRequiredMixin, DetailView):
    model = UserDataRegistry
    template_name = 'contract/registry_detail.html'
    context_object_name = 'registry'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['registry_users'] = self.object.users.all()
        
        # Check if current user is admin
        context['is_admin'] = (self.object.admin == self.request.user)
        
        # Check if current user is a member
        context['is_member'] = self.object.users.filter(user=self.request.user).exists()
        
        # Get current user's registry data if they're a member
        if context['is_member'] and self.object.deployed:
            registry_user = self.object.users.get(user=self.request.user)
            
            # If user has a wallet address
            if self.request.user.wallet_address:
                service = RegistryDeploymentService(network=self.object.network)
                user_data = service.get_user_data(self.object.address, self.request.user.wallet_address)
                context['user_data'] = user_data
                context['update_form'] = UserDataUpdateForm(initial={
                    'image_reference': user_data.get('image_reference', '')
                })
        
        # If admin and registry is deployed, add user addition form
        if context['is_admin'] and self.object.deployed:
            context['user_form'] = UserAdditionForm()
        
        return context

class CreateRegistryView(LoginRequiredMixin, CreateView):
    model = UserDataRegistry
    form_class = RegistryCreationForm
    template_name = 'contract/registry_create.html'
    success_url = reverse_lazy('registry_list')
    
    def form_valid(self, form):
        form.instance.admin = self.request.user
        response = super().form_valid(form)
        
        whitelist_addresses = form.cleaned_data.get('whitelist_addresses', [])
        self.request.session['whitelist_addresses'] = whitelist_addresses
        
        messages.success(self.request, 'Registry created successfully. You can now deploy it.')
        return response

class DeployRegistryView(LoginRequiredMixin, View):
    # This is the right approach for MetaMask integration
    def post(self, request, pk):
        registry = get_object_or_404(UserDataRegistry, pk=pk, admin=request.user)
        
        # Check if already deployed
        if registry.deployed:
            messages.error(request, 'Registry is already deployed.')
            return redirect('registry_detail', pk=pk)
        
        # Check if user has wallet connected
        if not request.user.wallet_address:
            messages.error(request, 'You need to connect your wallet first.')
            return redirect('registry_detail', pk=pk)
        
        try:
            # Get initial users (admin + whitelist)
            initial_users = [request.user.wallet_address]
            
            # Add whitelist addresses from session if they exist
            whitelist_addresses = request.session.get('whitelist_addresses', [])
            if whitelist_addresses:
                initial_users.extend(whitelist_addresses)
                # Clear from session after use
                del request.session['whitelist_addresses']
                request.session.modified = True
            
            # Deploy contract
            service = RegistryDeploymentService(network=registry.network)
            
            # For MetaMask integration, you don't send the transaction from Django
            # Instead, you should return the transaction data to be signed by MetaMask
            # For demonstration, we'll use our deploy_registry method differently:
            
            deployment_data = service.prepare_registry_deployment(
                request.user.wallet_address,
                initial_users
            )
            
            # Here you would return this data to the browser for MetaMask signing
            
            # For simplicity in this demo, let's just create the registry entry:
            if request.POST.get('deployed_address') and request.POST.get('tx_hash'):
                # In a real app, these would come from MetaMask after user signs
                registry.address = request.POST.get('deployed_address')
                registry.transaction_hash = request.POST.get('tx_hash')
                registry.deployed = True
                registry.deployment_date = timezone.now()
                registry.save()
                
                # Create admin as first registry user
                RegistryUser.objects.create(
                    registry=registry,
                    user=request.user,
                    wallet_address=request.user.wallet_address,
                    is_authorized=True
                )
                
                # Also create entries for whitelist addresses
                for address in whitelist_addresses:
                    # Try to find a user with this wallet address
                    user = User.objects.filter(wallet_address=address).first()
                    RegistryUser.objects.create(
                        registry=registry,
                        user=user,  # May be None if no matching user
                        wallet_address=address,
                        is_authorized=True
                    )
                
                messages.success(request, f'Registry deployed successfully!')
            else:
                messages.error(request, 'Missing deployment data.')
                
        except Exception as e:
            messages.error(request, f'Error during deployment: {str(e)}')
        
        return redirect('registry_detail', pk=pk)

class AddRegistryUsersView(LoginRequiredMixin, View):
    def post(self, request, pk):
        registry = get_object_or_404(UserDataRegistry, pk=pk, admin=request.user)
        
        # Check if registry is deployed
        if not registry.deployed:
            messages.error(request, 'Registry must be deployed before adding users.')
            return redirect('registry_detail', pk=pk)
        
        form = UserAdditionForm(request.POST)
        if form.is_valid():
            users = form.cleaned_data['users']
            
            # Initialize service
            service = RegistryDeploymentService(network=registry.network)
            contract = service.get_registry_contract(registry.address)
            
            # In a real application, you should never handle private keys like this
            # Use web3 browser wallets like MetaMask instead
            private_key = request.POST.get('private_key')  # This is for demo only!
            
            with transaction.atomic():
                for user in users:
                    # Check if user has wallet address
                    if not user.wallet_address:
                        messages.warning(request, f'User {user.email} skipped - no wallet address.')
                        continue
                    
                    # Check if already in registry
                    if registry.users.filter(user=user).exists():
                        messages.warning(request, f'User {user.email} is already in the registry.')
                        continue
                    
                    try:
                        # Add to blockchain
                        # This would call the authorizeUser function in the contract
                        # For brevity, we'll skip the actual blockchain call here
                        # But in a real app, you'd authorize them on-chain first
                        
                        # Then add to database
                        RegistryUser.objects.create(
                            registry=registry,
                            user=user,
                            wallet_address=user.wallet_address,
                            is_authorized=True
                        )
                        
                        messages.success(request, f'User {user.email} added successfully.')
                    except Exception as e:
                        messages.error(request, f'Error adding user {user.email}: {str(e)}')
            
            return redirect('registry_detail', pk=pk)
        else:
            messages.error(request, 'Invalid form submission.')
            return redirect('registry_detail', pk=pk)

class UpdateUserDataView(LoginRequiredMixin, View):
    def post(self, request, pk):
        registry = get_object_or_404(UserDataRegistry, pk=pk)
        
        # Check if registry is deployed
        if not registry.deployed:
            messages.error(request, 'Registry must be deployed before updating data.')
            return redirect('registry_detail', pk=pk)
        
        # Check if user is a member
        try:
            registry_user = registry.users.get(user=request.user)
        except RegistryUser.DoesNotExist:
            messages.error(request, 'You are not a member of this registry.')
            return redirect('registry_detail', pk=pk)
        
        # Check if user has wallet
        if not request.user.wallet_address:
            messages.error(request, 'You need to connect your wallet first.')
            return redirect('registry_detail', pk=pk)
        
        form = UserDataUpdateForm(request.POST)
        if form.is_valid():
            image_reference = form.cleaned_data['image_reference']
            
            # Initialize service
            service = RegistryDeploymentService(network=registry.network)
            
            # In a real application, you should never handle private keys like this
            # Use web3 browser wallets like MetaMask instead
            private_key = request.POST.get('private_key')  # This is for demo only!
            
            try:
                # Update on blockchain
                update_result = service.update_user_data(
                    registry.address,
                    request.user.wallet_address,
                    private_key,
                    image_reference
                )
                
                if update_result['success']:
                    # Update local cache
                    registry_user.image_reference = image_reference
                    registry_user.last_updated = timezone.now()
                    registry_user.save()
                    
                    messages.success(request, 'Your data has been updated successfully.')
                else:
                    messages.error(request, f'Update failed: {update_result["error"]}')
            
            except Exception as e:
                messages.error(request, f'Error updating data: {str(e)}')
        else:
            messages.error(request, 'Invalid form submission.')
        
        return redirect('registry_detail', pk=pk)

@method_decorator(csrf_exempt, name='dispatch')
class PrepareDeploymentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            # Start with a quick database operation
            registry = get_object_or_404(UserDataRegistry, pk=pk, admin=request.user)
            
            if registry.deployed:
                return JsonResponse({'success': False, 'error': 'Registry already deployed'})
            
            # Parse request body quickly
            data = json.loads(request.body)
            wallet_address = data.get('wallet_address')
            
            if not wallet_address:
                return JsonResponse({'success': False, 'error': 'Wallet address required'})
            
            # Create service to access web3 instance
            service = RegistryDeploymentService(network=registry.network)
            
            # Try to convert to checksum address - this is fast
            try:
                wallet_address = service.w3.to_checksum_address(wallet_address)
            except ValueError as e:
                return JsonResponse(
                    {'success': False, 'error': f'Invalid wallet address: {str(e)}'}
                )
        
            # Get initial users from session - this is fast
            initial_users = [wallet_address]
            whitelist_addresses = request.session.get('whitelist_addresses', [])
            if whitelist_addresses:
                initial_users.extend([addr for addr in whitelist_addresses if addr.strip()])
            
            # Prepare deployment - this can be slow but we've optimized it above
            deployment_data = service.prepare_registry_deployment(wallet_address, initial_users)
            
            # Return the response
            return JsonResponse(deployment_data)
            
        except Exception as e:
            logger.error(f"Error in PrepareDeploymentView: {str(e)}", exc_info=True)
            return JsonResponse({'success': False, 'error': str(e)})

@method_decorator(csrf_exempt, name='dispatch')
class ConfirmDeploymentView(LoginRequiredMixin, View):
    def post(self, request, pk):
        try:
            registry = get_object_or_404(UserDataRegistry, pk=pk, admin=request.user)
            
            if registry.deployed:
                return JsonResponse({'success': False, 'error': 'Registry already deployed'})
            
            # Parse request body
            data = json.loads(request.body)
            transaction_hash = data.get('transaction_hash')
            contract_address = data.get('contract_address')
            
            if not transaction_hash or not contract_address:
                return JsonResponse({'success': False, 'error': 'Transaction hash and contract address required'})
            
            # Convert to checksum address
            try:
                service = RegistryDeploymentService(network=registry.network)
                contract_address = service.w3.to_checksum_address(contract_address)
            except ValueError as e:
                return JsonResponse(
                    {'success': False, 'error': f'Invalid contract address: {str(e)}'}
                )
            
            # Update registry
            registry.address = contract_address
            registry.transaction_hash = transaction_hash
            registry.deployed = True
            registry.deployment_date = timezone.now()
            registry.save()
            
            # Create admin user entry
            RegistryUser.objects.create(
                registry=registry,
                user=request.user,
                wallet_address=request.user.wallet_address,
                is_authorized=True
            )
            
            # Add whitelist users
            whitelist_addresses = request.session.get('whitelist_addresses', [])
            for address in whitelist_addresses:
                user = User.objects.filter(wallet_address=address).first()
                RegistryUser.objects.create(
                    registry=registry,
                    user=user,  # May be None
                    wallet_address=address,
                    is_authorized=True
                )
            
            # Clear session
            if 'whitelist_addresses' in request.session:
                del request.session['whitelist_addresses']
                request.session.modified = True
            
            return JsonResponse({'success': True})
            
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
