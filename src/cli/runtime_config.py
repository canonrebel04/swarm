"""
Runtime configuration and model scanning utilities.

Provides user-friendly configuration and discovery of available models.
"""

import yaml
import os
from typing import List, Dict, Optional
import requests
from urllib.parse import urlparse


class RuntimeConfig:
    """Manage runtime configuration and model discovery."""
    
    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        """Load configuration from YAML file."""
        if not os.path.exists(self.config_path):
            return self._create_default_config()
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f) or {}
    
    def _create_default_config(self) -> dict:
        """Create default configuration."""
        return {
            'runtimes': {
                'default': 'mistral-vibe',
                'orchestrator': 'mistral-vibe',
                'scout': 'mistral-vibe',
                'developer': 'claude-code',
                'builder': 'codex',
                'tester': 'gemini',
                'available': [
                    'mistral-vibe',
                    'openclaw',
                    'hermes',
                    'gemini',
                    'claude-code',
                    'echo'
                ]
            },
            'runtime_settings': {
                'mistral-vibe': {
                    'model': 'mistral-small',
                    'max_tokens': 4096,
                    'temperature': 0.7
                },
                'openclaw': {
                    'model': 'default',
                    'thinking': 'medium'
                }
            },
            'model_providers': {
                'mistral': {
                    'api_url': 'https://api.mistral.ai',
                    'models_endpoint': '/v1/models'
                },
                'claude': {
                    'api_url': 'https://api.anthropic.com',
                    'models_endpoint': '/v1/models'
                }
            }
        }
    
    def save_config(self) -> None:
        """Save configuration to file."""
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f, sort_keys=False)
    
    def get_default_runtime(self, role: Optional[str] = None) -> str:
        """Get default runtime for a specific role or overall default."""
        if role and f"{role}" in self.config.get('runtimes', {}):
            return self.config['runtimes'][role]
        return self.config['runtimes']['default']
    
    def set_default_runtime(self, runtime: str, role: Optional[str] = None) -> None:
        """Set default runtime for a specific role or overall default."""
        if role:
            self.config.setdefault('runtimes', {})[role] = runtime
        else:
            self.config['runtimes']['default'] = runtime
        self.save_config()
    
    def get_available_runtimes(self) -> List[str]:
        """Get list of available runtimes."""
        return self.config.get('runtimes', {}).get('available', [])
    
    def add_runtime(self, runtime_name: str) -> None:
        """Add a runtime to available list."""
        if runtime_name not in self.get_available_runtimes():
            self.config.setdefault('runtimes', {}).setdefault('available', []).append(runtime_name)
            self.save_config()
    
    def get_runtime_settings(self, runtime: str) -> dict:
        """Get settings for a specific runtime."""
        return self.config.get('runtime_settings', {}).get(runtime, {})
    
    def set_runtime_settings(self, runtime: str, settings: dict) -> None:
        """Set settings for a specific runtime."""
        self.config.setdefault('runtime_settings', {})[runtime] = settings
        self.save_config()
    
    def scan_provider_models(self, provider: str) -> Optional[List[dict]]:
        """Scan provider API for available models."""
        provider_config = self.config.get('model_providers', {}).get(provider)
        if not provider_config:
            return None
        
        try:
            api_url = provider_config['api_url']
            models_endpoint = provider_config['models_endpoint']
            
            # Validate URL
            if not self._is_valid_url(api_url):
                return None
            
            response = requests.get(
                f"{api_url}{models_endpoint}",
                timeout=5,
                headers={'Accept': 'application/json'}
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])  # Standard format
            else:
                return None
                
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Error scanning {provider} models: {e}")
            return None
    
    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid."""
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except ValueError:
            return False
    
    def list_models_with_sources(self) -> List[Dict]:
        """List all models with their sources (configured or scanned)."""
        models = []
        
        # Add configured models
        for runtime, settings in self.config.get('runtime_settings', {}).items():
            if 'model' in settings:
                models.append({
                    'runtime': runtime,
                    'model': settings['model'],
                    'source': 'configured',
                    'status': 'available'
                })
        
        # Add provider models (scan if needed)
        for provider, config in self.config.get('model_providers', {}).items():
            provider_models = self.scan_provider_models(provider)
            if provider_models:
                for model in provider_models:
                    models.append({
                        'runtime': provider,
                        'model': model.get('id', 'unknown'),
                        'source': f'{provider}_api',
                        'status': 'available'
                    })
        
        return models
    
    def interactive_config(self) -> None:
        """Interactive configuration wizard."""
        print("Swarm Runtime Configuration")
        print("=" * 40)
        
        # Show current configuration
        print("\nCurrent Configuration:")
        print(f"Default Runtime: {self.get_default_runtime()}")
        print(f"Available Runtimes: {', '.join(self.get_available_runtimes())}")
        
        # Show available models
        models = self.list_models_with_sources()
        print(f"\nAvailable Models ({len(models)}):")
        for model in models:
            print(f"  - {model['model']} ({model['source']})")
        
        # Configuration options
        while True:
            print("\nOptions:")
            print("1. Change default runtime")
            print("2. Add/remove available runtimes")
            print("3. Configure runtime settings")
            print("4. Scan for provider models")
            print("5. Save and exit")
            
            choice = input("Enter choice (1-5): ").strip()
            
            if choice == '1':
                self._configure_default_runtime()
            elif choice == '2':
                self._configure_available_runtimes()
            elif choice == '3':
                self._configure_runtime_settings()
            elif choice == '4':
                self._scan_and_display_models()
            elif choice == '5':
                self.save_config()
                print("Configuration saved!")
                break
            else:
                print("Invalid choice. Please try again.")
    
    def _configure_default_runtime(self) -> None:
        """Configure default runtime."""
        available = self.get_available_runtimes()
        print(f"\nAvailable runtimes: {', '.join(available)}")
        
        runtime = input("Enter default runtime: ").strip()
        if runtime in available:
            self.set_default_runtime(runtime)
            print(f"Default runtime set to: {runtime}")
        else:
            print(f"Error: {runtime} not in available runtimes")
    
    def _configure_available_runtimes(self) -> None:
        """Configure available runtimes."""
        print("\nCurrent available runtimes:")
        for i, runtime in enumerate(self.get_available_runtimes(), 1):
            print(f"{i}. {runtime}")
        
        print("\nOptions:")
        print("1. Add runtime")
        print("2. Remove runtime")
        
        choice = input("Enter choice (1-2): ").strip()
        
        if choice == '1':
            runtime = input("Enter runtime to add: ").strip()
            self.add_runtime(runtime)
            print(f"Added: {runtime}")
        elif choice == '2':
            runtime = input("Enter runtime to remove: ").strip()
            if runtime in self.get_available_runtimes():
                self.config['runtimes']['available'].remove(runtime)
                self.save_config()
                print(f"Removed: {runtime}")
            else:
                print(f"Error: {runtime} not found")
    
    def _configure_runtime_settings(self) -> None:
        """Configure runtime-specific settings."""
        available = self.get_available_runtimes()
        print(f"\nConfigure settings for which runtime?")
        for i, runtime in enumerate(available, 1):
            print(f"{i}. {runtime}")
        
        choice = input("Enter runtime number: ").strip()
        try:
            runtime = available[int(choice) - 1]
            
            print(f"\nConfiguring {runtime}")
            settings = {}
            
            if runtime in ['mistral-vibe', 'openclaw']:
                settings['model'] = input("Model: ").strip() or self.get_runtime_settings(runtime).get('model', '')
                settings['max_tokens'] = int(input("Max tokens: ").strip() or "4096")
                settings['temperature'] = float(input("Temperature (0.0-1.0): ").strip() or "0.7")
            
            self.set_runtime_settings(runtime, settings)
            print(f"Settings saved for {runtime}")
            
        except (ValueError, IndexError):
            print("Invalid choice")
    
    def _scan_and_display_models(self) -> None:
        """Scan and display available models from providers."""
        print("\nScanning for available models...")
        
        models = self.list_models_with_sources()
        if not models:
            print("No models found. Check your provider URLs and API keys.")
            return
        
        print(f"Found {len(models)} models:")
        for model in models:
            print(f"  - {model['model']} ({model['source']})")


def configure_runtimes():
    """Entry point for runtime configuration."""
    config = RuntimeConfig()
    config.interactive_config()


if __name__ == "__main__":
    configure_runtimes()
