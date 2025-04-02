import logging
import json
import os
import solcx
from web3 import Web3
from django.conf import settings
from datetime import datetime
from django.utils import timezone

logger = logging.getLogger(__name__)

# Instead of installing at import time, use a function
def ensure_solc_installed():
    try:
        # Check if already installed
        if '0.8.15' not in solcx.get_installed_solc_versions():
            solcx.install_solc('0.8.15')
        
        # Set as the version to use
        solcx.set_solc_version('0.8.15')
        return True
    except Exception as e:
        logger.error(f"Failed to install solc: {str(e)}")
        return False

class RegistryDeploymentService:
    def __init__(self, network='sepolia'):
        self.network = network
        # Set up web3 provider
        if network == 'sepolia':
            self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URL))
        else:
            # Default to local development network
            self.w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
        
        # Verify connection
        if not self.w3.is_connected():
            raise ConnectionError(f"Cannot connect to {network} network. Check your provider.")
    
    def compile_contract(self):
        """Compile the UserDataRegistry contract and return bytecode and ABI"""
        # Ensure the compiler is installed
        ensure_solc_installed()
        
        contract_path = os.path.join(settings.BASE_DIR, 'contracts', 'UserDataRegistry.sol')
        with open(contract_path, 'r') as file:
            contract_source = file.read()
        
        compiled_sol = solcx.compile_source(
            contract_source,
            output_values=['abi', 'bin'],
            solc_version='0.8.15'
        )
        
        # Extract contract data
        contract_id, contract_interface = compiled_sol.popitem()
        bytecode = contract_interface['bin']
        abi = contract_interface['abi']
        
        return {'bin': bytecode,'abi': abi}
    
    def deploy_registry(self, owner_address, private_key, initial_users):
        """Deploy UserDataRegistry contract with initial authorized users list"""
        try:
            compiled_contract = self.compile_contract()
            
            Contract = self.w3.eth.contract(
                abi=compiled_contract['abi'],
                bytecode=compiled_contract['bin'] 
            )
            
            initial_users = list(set([
                self.w3.to_checksum_address(addr) 
                for addr in initial_users 
                if addr.startswith('0x') and len(addr) == 42
            ]))
            
            owner_address = self.w3.to_checksum_address(owner_address)
            if owner_address not in initial_users:
                initial_users.insert(0, owner_address)
            
            constructor_args = [initial_users]
            
            nonce = self.w3.eth.get_transaction_count(owner_address)
            gas_price = self.w3.eth.gas_price
            
            gas_estimate = Contract.constructor(initial_users).estimateGas({'from': owner_address})
            
            transaction = {
                'from': owner_address,
                'gas': int(gas_estimate * 1.2),
                'gasPrice': gas_price,
                'nonce': nonce,
            }
            
            tx_data = Contract.constructor(initial_users).build_transaction(transaction)
            
            signed_tx = self.w3.eth.account.sign_transaction(tx_data, private_key)
            
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return {
                'success': True,
                'contract_address': tx_receipt.contractAddress,
                'transaction_hash': tx_hash.hex(),
            }
        
        except ValueError as e:
            # More specific error handling for contract-related errors
            if "execution reverted" in str(e):
                return {'success': False, 'error': 'Contract execution reverted. You may not be authorized.'}
            else:
                return {'success': False, 'error': f'Invalid input: {str(e)}'}
        except Exception as e:
            # General error
            return {'success': False, 'error': f'Blockchain error: {str(e)}'}
    
    def get_registry_contract(self, contract_address):
        """Get a contract instance at the specified address"""
        compiled_contract = self.compile_contract()
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(contract_address),
            abi=compiled_contract['abi']
        )
        return contract
    
    def update_user_data(self, contract_address, user_address, private_key, image_reference):
        """Update a user's data in the registry"""
        try:
            # Get contract
            contract = self.get_registry_contract(contract_address)
            
            # Build transaction
            nonce = self.w3.eth.get_transaction_count(user_address)
            gas_price = self.w3.eth.gas_price
            
            # Estimate gas
            gas_estimate = contract.functions.updateUserData(image_reference).estimateGas({
                'from': user_address
            }) * 12 // 10  # Add 20% buffer
            
            transaction = {
                'from': user_address,
                'gas': gas_estimate,
                'gasPrice': gas_price,
                'nonce': nonce,
            }
            
            # Build transaction
            tx_data = contract.functions.updateUserData(image_reference).build_transaction(transaction)
            
            # Sign transaction
            signed_tx = self.w3.eth.account.sign_transaction(tx_data, private_key)
            
            # Send transaction
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for transaction receipt
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return {
                'success': True,
                'transaction_hash': tx_hash.hex(),
                'gas_used': tx_receipt.gasUsed
            }
            
        except ValueError as e:
            # More specific error handling for contract-related errors
            if "execution reverted" in str(e):
                return {'success': False, 'error': 'Contract execution reverted. You may not be authorized.'}
            else:
                return {'success': False, 'error': f'Invalid input: {str(e)}'}
        except Exception as e:
            # General error
            return {'success': False, 'error': f'Blockchain error: {str(e)}'}
    
    def get_user_data(self, contract_address, user_address):
        """Get a user's data from the registry"""
        try:
            # Get contract
            contract = self.get_registry_contract(contract_address)
            
            # Call function
            result = contract.functions.getUserData(user_address).call()
            
            # Parse result
            return {
                'success': True,
                'image_reference': result[0],
                'timestamp': result[1],
                'exists': result[2],
                'timestamp_readable': datetime.fromtimestamp(result[1]).strftime('%Y-%m-%d %H:%M:%S') if result[1] > 0 else None
            }
            
        except ValueError as e:
            # More specific error handling for contract-related errors
            if "execution reverted" in str(e):
                return {'success': False, 'error': 'Contract execution reverted. You may not be authorized.'}
            else:
                return {'success': False, 'error': f'Invalid input: {str(e)}'}
        except Exception as e:
            # General error
            return {'success': False, 'error': f'Blockchain error: {str(e)}'}
    
    def prepare_registry_deployment(self, owner_address, initial_users):
        """Prepare data for deploying registry contract via MetaMask"""
        try:
            compiled_contract = self.compile_contract()
            
            # Create contract instance
            Contract = self.w3.eth.contract(
                abi=compiled_contract['abi'],
                bytecode=compiled_contract['bin']
            )
            
            # Process initial users list with proper checksum
            initial_users = list(set([
                self.w3.to_checksum_address(addr) 
                for addr in initial_users 
                if addr.startswith('0x') and len(addr) == 42
            ]))
            
            # Ensure owner is included in authorized users
            owner_address = self.w3.to_checksum_address(owner_address)
            if owner_address not in initial_users:
                initial_users.insert(0, owner_address)
            
            # Get gas price
            gas_price = self.w3.eth.gas_price
            
            # Estimate gas
            try:
                gas_estimate = Contract.constructor(initial_users).estimateGas({'from': owner_address})
                gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
            except Exception as e:
                # Fallback to a reasonable default if estimation fails
                gas_limit = 5000000
            
            # Build dummy transaction to get data field
            dummy_tx = Contract.constructor(initial_users).build_transaction({
                'from': owner_address,
                'gas': 0,  # MetaMask will estimate
                'gasPrice': 0,  # MetaMask will set this
                'nonce': 0  # MetaMask will set this
            })
                
            # Build transaction data for MetaMask
            transaction_data = {
                'from': owner_address,
                'gas': hex(gas_limit),  # MetaMask requires hex values
                'gasPrice': hex(gas_price),
                'data': dummy_tx['data'],
                'chainId': hex(self.w3.eth.chain_id)  # Add chain ID
            }
            
            return {
                'success': True,
                'transaction_data': transaction_data
            }
        
        except Exception as e:
            import traceback
            print(traceback.format_exc())  # Add detailed logging
            return {
                'success': False,
                'error': str(e)
            }
    
    def prepare_update_user_data(self, contract_address, wallet_address, image_reference):
        """Prepare data for updating user data via MetaMask"""
        try:
            # Get contract instance
            contract = self.get_registry_contract(contract_address)
            wallet_address = self.w3.to_checksum_address(wallet_address)
            
            # Get gas price
            gas_price = self.w3.eth.gas_price
            
            # Estimate gas
            try:
                # Create function call object
                function_call = contract.functions.updateUserData(image_reference)
                
                # Estimate gas
                gas_estimate = function_call.estimateGas({'from': wallet_address})
                gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
            except Exception as e:
                # Fallback to a reasonable default if estimation fails
                gas_limit = 200000  # More conservative default for a simple update
            
            # Build dummy transaction to get data field
            dummy_tx = contract.functions.updateUserData(image_reference).build_transaction({
                'from': wallet_address,
                'gas': 0,  # MetaMask will estimate
                'gasPrice': 0,  # MetaMask will set this
                'nonce': 0  # MetaMask will set this
            })
                
            # Build transaction data for MetaMask
            transaction_data = {
                'from': wallet_address,
                'to': contract_address,  # Important: include the "to" address
                'gas': hex(gas_limit),  # MetaMask requires hex values
                'gasPrice': hex(gas_price),
                'data': dummy_tx['data'],
                'chainId': hex(self.w3.eth.chain_id)  # Add chain ID
            }
            
            return {
                'success': True,
                'transaction_data': transaction_data
            }
        
        except Exception as e:
            import traceback
            logger.exception(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }