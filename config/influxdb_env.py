#!/usr/bin/env python3
from __future__ import annotations

import os
from enum import Enum
from typing import Final


class InfluxDBEnvironment(Enum):
    """Enum for InfluxDB environments"""

    LOCAL = "local"
    PRODUCTION = "production"


# Environment configuration
# Change this to switch between local and production
CURRENT_ENVIRONMENT: Final[InfluxDBEnvironment] = InfluxDBEnvironment.LOCAL

# Configuration file paths
CONFIG_PATHS: Final[dict[InfluxDBEnvironment, str]] = {
    InfluxDBEnvironment.LOCAL: "config/influxdb_config_local.json",
    InfluxDBEnvironment.PRODUCTION: "config/influxdb_config.json",
}

# Environment variable override
ENV_VAR_NAME: Final[str] = "INFLUXDB_ENV"


def get_current_environment() -> InfluxDBEnvironment:
    """Get the current InfluxDB environment"""
    env_str = os.getenv(ENV_VAR_NAME)
    if env_str:
        try:
            return InfluxDBEnvironment(env_str.lower())
        except ValueError:
            print(
                f"Warning: Invalid INFLUXDB_ENV value '{env_str}'. Using default: {CURRENT_ENVIRONMENT.value}"
            )

    return CURRENT_ENVIRONMENT


def get_config_path(environment: InfluxDBEnvironment | None = None) -> str:
    """Get the config file path for the specified environment"""
    if environment is None:
        environment = get_current_environment()

    return CONFIG_PATHS[environment]


def get_production_config_path() -> str:
    """Get the production config file path"""
    return CONFIG_PATHS[InfluxDBEnvironment.PRODUCTION]


def get_local_config_path() -> str:
    """Get the local config file path"""
    return CONFIG_PATHS[InfluxDBEnvironment.LOCAL]


def is_local_environment() -> bool:
    """Check if we're using the local environment"""
    return get_current_environment() == InfluxDBEnvironment.LOCAL


def is_production_environment() -> bool:
    """Check if we're using the production environment"""
    return get_current_environment() == InfluxDBEnvironment.PRODUCTION


def print_environment_info() -> None:
    """Print current environment information"""
    env = get_current_environment()
    config_path = get_config_path(env)
    print(f"Current InfluxDB Environment: {env.value.upper()}")
    print(f"Config File: {config_path}")
    print(
        f"Override with: export {ENV_VAR_NAME}={InfluxDBEnvironment.LOCAL.value} or {InfluxDBEnvironment.PRODUCTION.value}"
    )


if __name__ == "__main__":
    print_environment_info()
