import os
import re
import pytest
import requests
import yaml
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def _expand_env_in_string(value):
    """Expand environment variables in string with format ${VAR:-default}"""
    if not isinstance(value, str):
        return value
    
    pattern = r'\$\{([^}:]+)(?::-([^}]*))?\}'
    
    def replace_env(match):
        env_var = match.group(1)
        default = match.group(2) if match.group(2) is not None else ''
        return os.environ.get(env_var, default)
    
    return re.sub(pattern, replace_env, value)


def _expand_env_in_dict(data):
    """Recursively expand environment variables in dictionary"""
    if isinstance(data, dict):
        return {key: _expand_env_in_dict(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [_expand_env_in_dict(item) for item in data]
    elif isinstance(data, str):
        return _expand_env_in_string(data)
    return data


class APIClient:
    """Simple API client for making HTTP requests"""
    
    def __init__(self, host, auth=None, timeout=30, retries=3):
        self.host = host.strip() if host else ''
        self.auth = auth or {}
        self.timeout = timeout
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE", "PATCH"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def _build_url(self, endpoint):
        """Build full URL from host and endpoint"""
        host = self.host.rstrip('/')
        endpoint = endpoint.lstrip('/')
        return f"{host}/{endpoint}"
    
    def _get_default_headers(self):
        """Get default headers including auth"""
        headers = {}
        if self.auth.get('keystone'):
            headers['x-auth-token'] = self.auth['keystone']
        return headers
    
    def make_request(self, endpoint, params=None, headers=None, method='GET', json=None, data=None):
        """Make HTTP request to the API"""
        url = self._build_url(endpoint)
        request_headers = self._get_default_headers()
        if headers:
            request_headers.update(headers)
        
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
        """Make GET request"""
        return self.make_request(endpoint, params=params, headers=headers, method='GET')
    
    def post(self, endpoint, headers=None, params=None, json=None, data=None):
        """Make POST request"""
        return self.make_request(endpoint, params=params, headers=headers, method='POST', json=json, data=data)
    
    def put(self, endpoint, headers=None, params=None, json=None, data=None):
        """Make PUT request"""
        return self.make_request(endpoint, params=params, headers=headers, method='PUT', json=json, data=data)
    
    def delete(self, endpoint, headers=None, params=None):
        """Make DELETE request"""
        return self.make_request(endpoint, params=params, headers=headers, method='DELETE')
    
    def patch(self, endpoint, headers=None, params=None, json=None, data=None):
        """Make PATCH request"""
        return self.make_request(endpoint, params=params, headers=headers, method='PATCH', json=json, data=data)


def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "smoke: For all success scenarios"
    )


@pytest.fixture(scope="session")
def config():
    """Load configuration from config.yml file"""
    config_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(config_dir, 'config.yml')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_path, 'r') as f:
        raw_config = yaml.safe_load(f)
    
    if raw_config is None:
        raw_config = {}
    
    expanded_config = _expand_env_in_dict(raw_config)
    return expanded_config


@pytest.fixture(scope="session")
def api_host(config):
    """Get API host from configuration"""
    api_config = config.get('api', {})
    host = api_config.get('host', '')
    return host.strip() if host else ''


@pytest.fixture(scope="session")
def auth(config):
    """Get authentication configuration"""
    return config.get('auth', {})


@pytest.fixture(scope="session")
def keystone_token(auth):
    """Get keystone token from auth configuration"""
    return auth.get('keystone', '')


@pytest.fixture(scope="session")
def config_test_data(config):
    """Load test_data from config fixture"""
    return config.get('test_data', {})


@pytest.fixture(scope="session")
def api_client(config):
    """Create API client instance using configuration"""
    api_config = config.get('api', {})
    auth_config = config.get('auth', {})
    
    host = api_config.get('host', '')
    
    return APIClient(
        host=host,
        auth=auth_config,
        timeout=30,
        retries=3
    )
