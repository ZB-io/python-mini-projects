import os
import re
import pytest
import requests
import yaml
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _expand_env_in_string(value):
    """Expand environment variables in string with format ${VAR:-default}."""
    if not isinstance(value, str):
        return value
    
    pattern = r'\$\{([^}]+)\}'
    
    def replace_env(match):
        content = match.group(1)
        if ':-' in content:
            var_name, default = content.split(':-', 1)
        else:
            var_name = content
            default = ''
        return os.environ.get(var_name, default)
    
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
    
    def __init__(self, base_url, auth_token=None, timeout=30):
        self.base_url = base_url.strip().rstrip('/')
        self.auth_token = auth_token
        self.timeout = timeout
        self.session = self._create_session()
    
    def _create_session(self):
        """Create a session with retry configuration."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE", "PATCH"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _get_headers(self, headers=None):
        """Build headers with authentication."""
        default_headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        if self.auth_token:
            default_headers['Authorization'] = f'Bearer {self.auth_token}'
        
        if headers:
            default_headers.update(headers)
        
        return default_headers
    
    def _build_url(self, endpoint):
        """Build full URL from endpoint."""
        endpoint = endpoint.strip().lstrip('/')
        return f"{self.base_url}/{endpoint}"
    
    def make_request(self, endpoint, params=None, headers=None, method='GET', json=None, data=None):
        """Make an HTTP request."""
        url = self._build_url(endpoint)
        request_headers = self._get_headers(headers)
        
        response = self.session.request(
            method=method.upper(),
            url=url,
            params=params,
            headers=request_headers,
            json=json,
            data=data,
            timeout=self.timeout
        )
        
        return response
    
    def get(self, endpoint, headers=None, params=None):
        """Make a GET request."""
        return self.make_request(endpoint, params=params, headers=headers, method='GET')
    
    def post(self, endpoint, json=None, data=None, headers=None, params=None):
        """Make a POST request."""
        return self.make_request(endpoint, params=params, headers=headers, method='POST', json=json, data=data)
    
    def put(self, endpoint, json=None, data=None, headers=None, params=None):
        """Make a PUT request."""
        return self.make_request(endpoint, params=params, headers=headers, method='PUT', json=json, data=data)
    
    def patch(self, endpoint, json=None, data=None, headers=None, params=None):
        """Make a PATCH request."""
        return self.make_request(endpoint, params=params, headers=headers, method='PATCH', json=json, data=data)
    
    def delete(self, endpoint, headers=None, params=None):
        """Make a DELETE request."""
        return self.make_request(endpoint, params=params, headers=headers, method='DELETE')


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "smoke: For all success scenarios"
    )


@pytest.fixture(scope="session")
def config():
    """Load configuration from config.yml file."""
    config_path = os.path.join(os.path.dirname(__file__), 'config.yml')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            raw_config = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Error parsing config.yml: {e}")
    
    if raw_config is None:
        raise ValueError("Configuration file is empty")
    
    expanded_config = _expand_env_in_dict(raw_config)
    
    return expanded_config


@pytest.fixture(scope="session")
def api_host(config):
    """Get API host from configuration."""
    return config.get('api', {}).get('host', '').strip()


@pytest.fixture(scope="session")
def auth(config):
    """Get auth configuration."""
    return config.get('auth', {})


@pytest.fixture(scope="session")
def bearer_token(auth):
    """Get bearer token from auth configuration."""
    return auth.get('bearerAuth', '')


@pytest.fixture(scope="session")
def api_client(api_host, bearer_token):
    """Create API client instance."""
    client = APIClient(
        base_url=api_host,
        auth_token=bearer_token if bearer_token else None,
        timeout=30
    )
    yield client
    client.session.close()


@pytest.fixture(scope="session")
def config_test_data(config):
    """Load test_data from config fixture."""
    return config.get('test_data', {})


@pytest.fixture(scope="session")
def test_user_id(config_test_data):
    """Get test userId from test_data."""
    return config_test_data.get('userId', '')


@pytest.fixture(scope="session")
def test_product_id(config_test_data):
    """Get test productId from test_data."""
    return config_test_data.get('productId', '')


@pytest.fixture(scope="session")
def test_order_id(config_test_data):
    """Get test orderId from test_data."""
    return config_test_data.get('orderId', '')
