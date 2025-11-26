import os
import re
import pytest
import requests
import yaml
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _expand_env_in_string(value):
    """Expand environment variables in string with ${VAR:-default} syntax."""
    if not isinstance(value, str):
        return value
    
    pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
    
    def replace_env(match):
        env_var = match.group(1)
        default = match.group(2) if match.group(2) is not None else ''
        return os.environ.get(env_var, default)
    
    return re.sub(pattern, replace_env, value)


def _expand_env_in_dict(data):
    """Recursively expand environment variables in dictionary."""
    if isinstance(data, dict):
        return {key: _expand_env_in_dict(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_expand_env_in_dict(item) for item in data]
    elif isinstance(data, str):
        return _expand_env_in_string(data)
    return data


class APIClient:
    """Simple API client for making HTTP requests."""
    
    def __init__(self, host, auth=None, timeout=30):
        self.host = host.strip() if host else ''
        self.auth = auth or {}
        self.timeout = timeout
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE", "PATCH"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _build_url(self, endpoint):
        """Build full URL from host and endpoint."""
        host = self.host.rstrip('/')
        endpoint = endpoint.lstrip('/') if endpoint else ''
        return f"{host}/{endpoint}"
    
    def _prepare_headers(self, headers=None):
        """Prepare headers with authentication."""
        prepared_headers = headers.copy() if headers else {}
        return prepared_headers
    
    def _prepare_params(self, params=None):
        """Prepare query parameters with authentication if ApiKeyAuth is set."""
        prepared_params = params.copy() if params else {}
        if self.auth.get('ApiKeyAuth'):
            prepared_params['key'] = self.auth['ApiKeyAuth']
        return prepared_params
    
    def make_request(self, endpoint, params=None, headers=None, method='GET', json=None, data=None):
        """Make an HTTP request to the API."""
        url = self._build_url(endpoint)
        prepared_headers = self._prepare_headers(headers)
        prepared_params = self._prepare_params(params)
        
        response = self.session.request(
            method=method.upper(),
            url=url,
            params=prepared_params,
            headers=prepared_headers,
            json=json,
            data=data,
            timeout=self.timeout
        )
        return response
    
    def get(self, endpoint, headers=None, params=None):
        """Make a GET request."""
        return self.make_request(endpoint, params=params, headers=headers, method='GET')
    
    def post(self, endpoint, headers=None, params=None, json=None, data=None):
        """Make a POST request."""
        return self.make_request(endpoint, params=params, headers=headers, method='POST', json=json, data=data)
    
    def put(self, endpoint, headers=None, params=None, json=None, data=None):
        """Make a PUT request."""
        return self.make_request(endpoint, params=params, headers=headers, method='PUT', json=json, data=data)
    
    def delete(self, endpoint, headers=None, params=None):
        """Make a DELETE request."""
        return self.make_request(endpoint, params=params, headers=headers, method='DELETE')
    
    def patch(self, endpoint, headers=None, params=None, json=None, data=None):
        """Make a PATCH request."""
        return self.make_request(endpoint, params=params, headers=headers, method='PATCH', json=json, data=data)


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "smoke: For all success scenarios"
    )


@pytest.fixture(scope="session")
def config():
    """Load configuration from config.yml file with environment variable expansion."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
    
    try:
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found at: {config_path}")
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing config.yml: {e}")
    
    if raw_config is None:
        raw_config = {}
    
    expanded_config = _expand_env_in_dict(raw_config)
    return expanded_config


@pytest.fixture(scope="session")
def api_host(config):
    """Get API host from configuration."""
    host = config.get('api', {}).get('host', '')
    return host.strip() if host else ''


@pytest.fixture(scope="session")
def auth(config):
    """Get authentication configuration."""
    return config.get('auth', {})


@pytest.fixture(scope="session")
def api_client(api_host, auth):
    """Create an API client instance."""
    return APIClient(host=api_host, auth=auth)


@pytest.fixture(scope="session")
def config_test_data(config):
    """Load test_data from config fixture."""
    return config.get('test_data', {})
