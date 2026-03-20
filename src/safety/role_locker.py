"""
Role locker system for enforcing valid role transitions and preventing role drift.

This module validates handoffs between roles based on the role contract graph
defined in the YAML contracts, ensuring agents cannot transition to roles they
are not authorized to handoff to.
"""

import yaml
from pathlib import Path
from typing import Dict, List, Set
from dataclasses import dataclass


class RoleViolation(Exception):
    """Exception raised when a role transition violates contract constraints."""
    def __init__(self, from_role: str, to_role: str, message: str):
        self.from_role = from_role
        self.to_role = to_role
        self.message = message
        super().__init__(f"Role violation: {from_role} → {to_role}: {message}")


@dataclass
class RoleContract:
    """Role contract with handoff constraints."""
    name: str
    description: str
    allowed_handoff_to: List[str]
    forbidden_handoff_to: List[str]
    allowed_actions: List[str]
    forbidden_actions: List[str]


class RoleLocker:
    """Enforces role transition constraints based on YAML contracts."""
    
    def __init__(self, contracts_dir: str = "src/roles/contracts"):
        self.contracts_dir = contracts_dir
        self.role_contracts: Dict[str, RoleContract] = {}
        self._load_role_contracts()
    
    def _load_role_contracts(self) -> None:
        """Load role contracts from YAML files."""
        contracts_path = Path(self.contracts_dir)
        
        if not contracts_path.exists():
            raise FileNotFoundError(f"Contracts directory not found: {contracts_path}")
        
        for yaml_file in contracts_path.glob("*.yaml"):
            try:
                with open(yaml_file, 'r') as f:
                    contract_data = yaml.safe_load(f)
                    
                role_name = yaml_file.stem
                contract = RoleContract(
                    name=role_name,
                    description=contract_data.get('description', ''),
                    allowed_handoff_to=contract_data.get('handoff_to', []),
                    forbidden_handoff_to=contract_data.get('forbidden_handoff_to', []),
                    allowed_actions=contract_data.get('may', []),
                    forbidden_actions=contract_data.get('may_not', [])
                )
                self.role_contracts[role_name] = contract
                
            except Exception as e:
                raise RuntimeError(f"Failed to load contract {yaml_file}: {e}")
    
    def validate_handoff(self, from_role: str, to_role: str) -> bool:
        """
        Validate a role handoff transition.
        
        Args:
            from_role: Current role attempting handoff
            to_role: Target role for handoff
            
        Returns:
            True if handoff is valid
            
        Raises:
            RoleViolation: If handoff violates contract constraints
        """
        # Check if roles exist
        if from_role not in self.role_contracts:
            raise RoleViolation(from_role, to_role, f"Unknown source role: {from_role}")
        
        if to_role not in self.role_contracts:
            raise RoleViolation(from_role, to_role, f"Unknown target role: {to_role}")
        
        from_contract = self.role_contracts[from_role]
        
        # Check forbidden handoffs first (take precedence)
        if to_role in from_contract.forbidden_handoff_to:
            raise RoleViolation(
                from_role, to_role,
                f"{from_role} is explicitly forbidden from handing off to {to_role}"
            )
        
        # Check allowed handoffs
        if from_contract.allowed_handoff_to:
            if to_role not in from_contract.allowed_handoff_to:
                raise RoleViolation(
                    from_role, to_role,
                    f"{from_role} can only handoff to {from_contract.allowed_handoff_to}, not {to_role}"
                )
        
        # If no explicit allowed list and not forbidden, handoff is permitted
        return True
    
    def get_allowed_handoffs(self, role: str) -> List[str]:
        """Get list of roles that the specified role can handoff to."""
        if role not in self.role_contracts:
            return []
        
        contract = self.role_contracts[role]
        # If no explicit allowed list, return all roles except forbidden ones
        if not contract.allowed_handoff_to:
            all_roles = set(self.role_contracts.keys())
            forbidden = set(contract.forbidden_handoff_to)
            return list(all_roles - forbidden)
        
        return contract.allowed_handoff_to
    
    def get_role_contract(self, role: str) -> RoleContract | None:
        """Get the contract for a specific role."""
        return self.role_contracts.get(role)
    
    def list_roles(self) -> List[str]:
        """List all known roles."""
        return list(self.role_contracts.keys())


# Global instance for easy access
role_locker = RoleLocker()
