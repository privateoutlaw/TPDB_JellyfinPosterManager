"""Offline tests: never load local credentials or use a real media server."""
import sys
import types
from config_example import Config as ExampleConfig


class TestConfig(ExampleConfig):
    JELLYFIN_URL = 'http://jellyfin.test'
    JELLYFIN_API_KEY = 'test-key'
    TPDB_EMAIL = ''
    TPDB_PASSWORD = ''


config = types.ModuleType('config')
config.Config = TestConfig
sys.modules['config'] = config
