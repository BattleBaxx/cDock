import os

from dotenv import load_dotenv


class Config:
    def __init__(self, docker_socket_url, docker_cert_path, docker_tls_verify_path, docker_config_path,
                 client_list_all_containers, tui_header_color):
        # Docker daemon options
        self.docker_socket_url = docker_socket_url
        self.docker_cert_path = docker_cert_path
        self.docker_tls_verify_path = docker_tls_verify_path
        self.docker_config_path = docker_config_path

        # Docker API Client options
        self.client_list_all_containers = client_list_all_containers

        # TUI options
        self.tui_header_color = tui_header_color

    @staticmethod
    def load_env_from_file(path: str):
        if path:
            load_dotenv(path)
        else:
            load_dotenv()

        config = {
            # Docker daemon options
            'docker_socket_url': os.getenv("DOCKER_SOCKET_URL", "unix://var/run/docker.sock"),
            'docker_cert_path': os.getenv("DOCKER_CERT_PATH"),
            'docker_tls_verify_path': os.getenv("DOCKER_TLS_VERIFY_PATH"),
            'docker_config_path': os.getenv("DOCKER_CONFIG_PATH"),

            # Docker API Client options
            'client_list_all_containers': os.getenv("DOCKER_API_LIST_ALL_CONTAINERS", False),

            # TUI options
            'tui_header_color': os.getenv("TUI_HEADER_COLOR")
        }

        return Config(**config)
