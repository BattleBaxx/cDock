import os
from dotenv import load_dotenv


class Config:
    def __init__(self, socket_url, cert_path, tlf_verify_path, config_path, id_color, stack_color, image_color, updated_color, created_color):
        self.socket_url = socket_url
        self.cert_path = cert_path
        self.tls_verify_path = tlf_verify_path
        self.config_path = config_path
        self.header_color = header_color

    @staticmethod
    def load_env_from_file( path: str):
        if path:
            load_dotenv(path)
        else:
            load_dotenv()
        socket_url = os.getenv("DOCKER_SOCKET_URL")
        cert_path = os.getenv("DOCKER_CERT_PATH")
        tls_verify_path = os.getenv("DOCKER_TLS_VERIFY_PATH")
        config_path = os.getenv("DOCKER_CONFIG_PATH")
        header_color = os.getenv("HEADER_COLOR")
        if not socket_url:
            socket_url = "unix://var/run/docker.sock"
        return Config(socket_url, cert_path, tls_verify_path, config_path, id_color, stack_color, image_color, updated_color, created_color)



