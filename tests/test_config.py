import unittest
from cDock.config import Config

class TestConfig(unittest.TestCase):

    def test_config_with_path(self):
        config = Config.load_env_from_file("../tests/test.env")
        self.assertEqual(config.socket_url, "/var/run/docker.sock")
        self.assertEqual(config.cert_path, '/home/cert')
        self.assertEqual(config.tls_verify_path, "/home/tls_path")
        self.assertEqual(config.config_path, "/home/docker/config_path")


if __name__ == "__main__":
    unittest.main()
