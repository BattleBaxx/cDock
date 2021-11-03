import os

from dotenv import load_dotenv


class Config:
    def __init__(self, socket_url, cert_path, tlf_verify_path, config_path, header_color):
        self.socket_url = socket_url
        self.cert_path = cert_path
        self.tls_verify_path = tlf_verify_path
        self.config_path = config_path
        self.header_color = header_color

    @staticmethod
    def load_env_from_file(path: str):
        if path:
            load_dotenv(path)
        else:
            load_dotenv()

        # Docker environment variables
        socket_url = os.getenv("DOCKER_SOCKET_URL", "unix://var/run/docker.sock")
        cert_path = os.getenv("DOCKER_CERT_PATH")
        tls_verify_path = os.getenv("DOCKER_TLS_VERIFY_PATH")
        config_path = os.getenv("DOCKER_CONFIG_PATH")

        # Colour environment variables
        header_color = os.getenv("HEADER_COLOR")

        return Config(socket_url, cert_path, tls_verify_path, config_path, header_color)
