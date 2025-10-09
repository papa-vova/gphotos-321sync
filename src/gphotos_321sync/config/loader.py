"""Configuration loader with multi-source support."""

import toml
import os
from pathlib import Path
from typing import Dict, Any, Optional
import platformdirs
from .schema import Config


class ConfigLoader:
    """Loads configuration from multiple sources with priority."""

    def __init__(self, app_name: str = "gphotos-sync") -> None:
        self.app_name = app_name
        self._config: Optional[Config] = None

    def load(self) -> Config:
        """Load configuration from all sources."""
        # 1. Start with defaults (shipped with app)
        config_dict = self._load_defaults()

        # 2. Merge system config
        system_config = self._load_system_config()
        if system_config:
            config_dict = self._deep_merge(config_dict, system_config)

        # 3. Merge user config
        user_config = self._load_user_config()
        if user_config:
            config_dict = self._deep_merge(config_dict, user_config)

        # 4. Override with environment variables
        config_dict = self._apply_env_overrides(config_dict)

        # 5. Validate and create Config object
        self._config = Config(**config_dict)

        return self._config

    def _load_defaults(self) -> Dict[str, Any]:
        """Load default configuration shipped with app."""
        # Try multiple possible locations for defaults
        possible_paths = [
            Path(__file__).parent.parent.parent.parent / "config" / "defaults.toml",
            Path.cwd() / "config" / "defaults.toml",
            Path(__file__).parent / "defaults.toml",
        ]

        for defaults_path in possible_paths:
            if defaults_path.exists():
                return toml.load(defaults_path)

        raise FileNotFoundError(
            f"Default config not found. Searched: {[str(p) for p in possible_paths]}"
        )

    def _load_system_config(self) -> Optional[Dict[str, Any]]:
        """Load system-wide configuration."""
        if os.name == "nt":  # Windows
            system_path = (
                Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData"))
                / self.app_name
                / "config.toml"
            )
        else:  # Linux/Mac
            system_path = Path(f"/etc/{self.app_name}/config.toml")

        if system_path.exists():
            return toml.load(system_path)

        return None

    def _load_user_config(self) -> Optional[Dict[str, Any]]:
        """Load user-specific configuration."""
        user_config_dir = platformdirs.user_config_dir(self.app_name)
        user_config_path = Path(user_config_dir) / "config.toml"

        if user_config_path.exists():
            return toml.load(user_config_path)

        return None

    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries."""
        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Override config with environment variables."""
        # Environment variables format: GPHOTOS_SECTION_SUBSECTION_KEY
        prefix = f"{self.app_name.upper().replace('-', '_')}_"

        for env_key, env_value in os.environ.items():
            if not env_key.startswith(prefix):
                continue

            # Parse key path: GPHOTOS_DATABASE_POSTGRESQL_HOST -> database.postgresql.host
            key_path = env_key[len(prefix) :].lower().split("_")

            # Navigate to the right place in config dict
            current = config
            for part in key_path[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set value (with type conversion)
            final_key = key_path[-1]
            current[final_key] = self._convert_env_value(env_value)

        return config

    def _convert_env_value(self, value: str) -> Any:
        """Convert string environment variable to appropriate type."""
        # Boolean
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Number
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # List (comma-separated)
        if "," in value:
            return [v.strip() for v in value.split(",")]

        # String
        return value

    def save_user_config(self, config: Config) -> None:
        """Save user configuration."""
        user_config_dir = platformdirs.user_config_dir(self.app_name)
        user_config_path = Path(user_config_dir) / "config.toml"

        # Ensure directory exists
        user_config_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dict and save
        config_dict = config.model_dump()
        with open(user_config_path, "w") as f:
            toml.dump(config_dict, f)

    @property
    def config(self) -> Config:
        """Get loaded configuration."""
        if self._config is None:
            self._config = self.load()
        return self._config


# Global instance
_loader = ConfigLoader()


def get_config() -> Config:
    """Get global configuration instance."""
    return _loader.config


def reload_config() -> Config:
    """Reload configuration from all sources."""
    return _loader.load()
