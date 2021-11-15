import os

from dotenv import load_dotenv


class Config:
    def __init__(self, docker_socket_url, docker_cert_path, docker_tls_verify_path, docker_config_path,
                 client_list_all_containers, tui_header_color, default_style, selected_row_style, selected_col_style,
                 priority_attributes):
        # Docker daemon options
        self.docker_socket_url = docker_socket_url
        self.docker_cert_path = docker_cert_path
        self.docker_tls_verify_path = docker_tls_verify_path
        self.docker_config_path = docker_config_path

        # Docker API Client options
        self.client_list_all_containers = client_list_all_containers

        # TUI options
        self.tui_header_color = tui_header_color
        self.default_style = default_style
        self.selected_row_style = selected_row_style
        self.selected_col_style = selected_col_style
        self.priority_attributes = priority_attributes

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
            'tui_header_color': os.getenv("TUI_HEADER_COLOR"),
            'default_style': os.getenv("DEFAULT_STYLE"),
            'selected_row_style': os.getenv("SELECTED_ROW_STYLE"),
            'selected_col_style': os.getenv("SELECTED_COL_STYLE"),
            'priority_attributes': os.getenv("PRIORITY_ATTRIBUTES", "name,status,cpu,mem_usage,ior/s,iow/s,rx/s,tx/s")
        }

        return Config(**config)
