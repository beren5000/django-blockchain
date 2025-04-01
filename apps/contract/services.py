import json
import os
from web3 import Web3
from solcx import compile_source, install_solc
from django.conf import settings
from datetime import datetime
from django.utils import timezone

# Install specific Solidity compiler version
install_solc('0.8.15')

class RegistryDeploymentService:
    def __init__(self, network='sepolia'):
        self.network = network
        # Set up web3 provider
        if network == 'sepolia':
            self.w3 = Web3(Web3.HTTPProvider(settings.WEB3_PROVIDER_URL))
        else:
            # Default to local development network
            self.w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
    
    def compile_contract(self):
        """Compile the UserDataRegistry contract and return bytecode and ABI"""
        contract_path = os.path.join(settings.BASE_DIR, 'contracts', 'UserDataRegistry.sol')
        with open(contract_path, 'r') as file:
            contract_source = file.read()
        
        compiled_sol = compile_source(
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
            
            tx_data = Contract.constructor(initial_users).buildTransaction(transaction)
            
            signed_tx = self.w3.eth.account.sign_transaction(tx_data, private_key)
            
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            tx_receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            return {
                'success': True,
                'contract_address': tx_receipt.contractAddress,
                'transaction_hash': tx_hash.hex(),
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_registry_contract(self, contract_address):
        """Get a contract instance at the specified address"""
        compiled_contract = self.compile_contract()
        contract = self.w3.eth.contract(
            address=contract_address,
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
            tx_data = contract.functions.updateUserData(image_reference).buildTransaction(transaction)
            
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
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
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
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
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
            
            # Get gas price - use a higher percentile for faster confirmations
            gas_price = self.w3.eth.gas_price
            
            # Estimate gas - don't use excessive amounts  
            try:
                gas_estimate = Contract.constructor(initial_users).estimateGas({'from': owner_address})
                gas_limit = int(gas_estimate * 1.2)  # Add 20% buffer
            except Exception as e:
                # Fallback to a reasonable default if estimation fails
                gas_limit = 5000000
                
            # Build transaction data for MetaMask
            transaction_data = {
                'from': owner_address,
                'gas': hex(gas_limit),  # MetaMask requires hex values
                'gasPrice': hex(gas_price),
                'data': Contract.constructor(initial_users).data_in_transaction
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