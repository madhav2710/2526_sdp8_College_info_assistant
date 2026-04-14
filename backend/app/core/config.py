"""
Configuration Management System for RAG Chat Integration

This module provides comprehensive configuration management with validation,
dynamic updates, and environment variable handling for all RAG settings.

Requirements addressed:
- 6.1: Load configuration from environment variables
- 6.2: Support configurable parameters
- 6.3: Apply configuration changes without code changes
- 6.4: Validate configuration parameters at startup
- 6.5: Fail gracefully with clear error messages
"""

import os
import logging
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass, field
from enum import Enum
import json
from pathlib import Path
import google.generativeai as genai

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""

    pass


class ConfigValidationError(ConfigurationError):
    """Raised when configuration validation fails"""

    pass


class ConfigUpdateError(ConfigurationError):
    """Raised when dynamic configuration update fails"""

    pass


class LogLevel(Enum):
    """Supported logging levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration settings"""

    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str

    def validate(self) -> List[str]:
        """Validate database configuration"""
        errors = []

        if not self.supabase_url:
            errors.append("SUPABASE_URL is required")
        elif not self.supabase_url.startswith(("http://", "https://")):
            errors.append("SUPABASE_URL must be a valid URL")

        if not self.supabase_key:
            errors.append("SUPABASE_KEY is required")

        if not self.supabase_service_role_key:
            errors.append("SUPABASE_SERVICE_ROLE_KEY is required")

        return errors


@dataclass
class AIConfig:
    """AI service configuration settings"""

    gemini_api_key: Optional[str]
    embedding_model: str = "models/embedding-001"
    generation_model: str = "gemini-1.5-flash"
    max_retries: int = 3
    retry_delay: float = 1.0
    retry_backoff_factor: float = 2.0
    max_retry_delay: float = 60.0

    def validate(self) -> List[str]:
        """Validate AI configuration"""
        errors = []

        # Gemini API key is optional but recommended
        if not self.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY not configured - RAG functionality will be limited"
            )

        # Validate model names
        if not self.embedding_model:
            errors.append("RAG_EMBEDDING_MODEL cannot be empty")

        if not self.generation_model:
            errors.append("RAG_GENERATION_MODEL cannot be empty")

        # Validate retry parameters
        if self.max_retries < 0:
            errors.append("RAG_MAX_RETRIES cannot be negative")

        if self.retry_delay < 0:
            errors.append("RAG_RETRY_DELAY cannot be negative")

        if self.retry_backoff_factor <= 0:
            errors.append("RAG_RETRY_BACKOFF_FACTOR must be positive")

        if self.max_retry_delay <= 0:
            errors.append("RAG_MAX_RETRY_DELAY must be positive")

        return errors


@dataclass
class RAGConfig:
    """RAG system configuration settings"""

    chunk_size: int = 1500
    chunk_overlap: int = 300
    similarity_threshold: float = 0.7
    max_chunks_per_query: int = 5

    def validate(self) -> List[str]:
        """Validate RAG configuration"""
        errors = []

        # Validate chunk parameters
        if self.chunk_size <= 0:
            errors.append("RAG_CHUNK_SIZE must be positive")
        elif self.chunk_size > 10000:
            errors.append("RAG_CHUNK_SIZE should not exceed 10000 characters")

        if self.chunk_overlap < 0:
            errors.append("RAG_CHUNK_OVERLAP cannot be negative")
        elif self.chunk_overlap >= self.chunk_size:
            errors.append("RAG_CHUNK_OVERLAP must be less than RAG_CHUNK_SIZE")

        # Validate similarity threshold
        if not 0.0 <= self.similarity_threshold <= 1.0:
            errors.append("RAG_SIMILARITY_THRESHOLD must be between 0.0 and 1.0")

        # Validate max chunks
        if self.max_chunks_per_query <= 0:
            errors.append("RAG_MAX_CHUNKS_PER_QUERY must be positive")
        elif self.max_chunks_per_query > 20:
            errors.append(
                "RAG_MAX_CHUNKS_PER_QUERY should not exceed 20 for performance reasons"
            )

        return errors


@dataclass
class SecurityConfig:
    """Security configuration settings"""

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    def validate(self) -> List[str]:
        """Validate security configuration"""
        errors = []

        if not self.jwt_secret_key:
            errors.append("JWT_SECRET_KEY is required")
        elif len(self.jwt_secret_key) < 32:
            errors.append("JWT_SECRET_KEY should be at least 32 characters long")

        if self.jwt_algorithm not in [
            "HS256",
            "HS384",
            "HS512",
            "RS256",
            "RS384",
            "RS512",
        ]:
            errors.append("JWT_ALGORITHM must be a valid JWT algorithm")

        if self.jwt_access_token_expire_minutes <= 0:
            errors.append("JWT_ACCESS_TOKEN_EXPIRE_MINUTES must be positive")

        return errors


@dataclass
class FileConfig:
    """File upload configuration settings"""

    max_file_size_mb: int = 50
    allowed_file_extensions: List[str] = field(
        default_factory=lambda: [".pdf", ".doc", ".docx", ".txt"]
    )

    def validate(self) -> List[str]:
        """Validate file configuration"""
        errors = []

        if self.max_file_size_mb <= 0:
            errors.append("MAX_FILE_SIZE_MB must be positive")
        elif self.max_file_size_mb > 500:
            errors.append("MAX_FILE_SIZE_MB should not exceed 500MB")

        if not self.allowed_file_extensions:
            errors.append("ALLOWED_FILE_EXTENSIONS cannot be empty")

        # Validate extensions format
        for ext in self.allowed_file_extensions:
            if not ext.startswith("."):
                errors.append(f"File extension '{ext}' must start with a dot")

        return errors


@dataclass
class RateLimitConfig:
    """Rate limiting configuration settings"""

    enabled: bool = True
    default_rate_limit_per_minute: int = 60

    def validate(self) -> List[str]:
        """Validate rate limiting configuration"""
        errors = []

        if self.default_rate_limit_per_minute <= 0:
            errors.append("DEFAULT_RATE_LIMIT_PER_MINUTE must be positive")
        elif self.default_rate_limit_per_minute > 1000:
            errors.append("DEFAULT_RATE_LIMIT_PER_MINUTE should not exceed 1000")

        return errors


@dataclass
class ApplicationConfig:
    """Application-level configuration settings"""

    app_name: str = "College Platform API"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: LogLevel = LogLevel.INFO
    cors_allowed_origins: List[str] = field(
        default_factory=lambda: [
            "http://localhost",
            "http://localhost:5173",
            "http://localhost:5174",
            "http://localhost:5175",
        ]
    )

    def validate(self) -> List[str]:
        """Validate application configuration"""
        errors = []

        if not self.app_name:
            errors.append("APP_NAME cannot be empty")

        if not self.app_version:
            errors.append("APP_VERSION cannot be empty")

        if not self.cors_allowed_origins:
            errors.append("CORS_ALLOWED_ORIGINS cannot be empty")

        for origin in self.cors_allowed_origins:
            if not origin.startswith(("http://", "https://")):
                errors.append(f"Invalid CORS origin: {origin}")

        return errors


@dataclass
class SystemConfig:
    """Complete system configuration"""

    database: DatabaseConfig
    ai: AIConfig
    rag: RAGConfig
    security: SecurityConfig
    file: FileConfig
    rate_limit: RateLimitConfig
    application: ApplicationConfig

    def validate(self) -> List[str]:
        """Validate entire system configuration"""
        all_errors = []

        # Validate each configuration section
        all_errors.extend(self.database.validate())
        all_errors.extend(self.ai.validate())
        all_errors.extend(self.rag.validate())
        all_errors.extend(self.security.validate())
        all_errors.extend(self.file.validate())
        all_errors.extend(self.rate_limit.validate())
        all_errors.extend(self.application.validate())

        return all_errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization"""
        return {
            "database": {
                "supabase_url": self.database.supabase_url,
                "supabase_key": "***REDACTED***",  # Don't expose sensitive keys
                "supabase_service_role_key": "***REDACTED***",
            },
            "ai": {
                "gemini_api_key": "***REDACTED***" if self.ai.gemini_api_key else None,
                "embedding_model": self.ai.embedding_model,
                "generation_model": self.ai.generation_model,
                "max_retries": self.ai.max_retries,
                "retry_delay": self.ai.retry_delay,
                "retry_backoff_factor": self.ai.retry_backoff_factor,
                "max_retry_delay": self.ai.max_retry_delay,
            },
            "rag": {
                "chunk_size": self.rag.chunk_size,
                "chunk_overlap": self.rag.chunk_overlap,
                "similarity_threshold": self.rag.similarity_threshold,
                "max_chunks_per_query": self.rag.max_chunks_per_query,
            },
            "security": {
                "jwt_secret_key": "***REDACTED***",
                "jwt_algorithm": self.security.jwt_algorithm,
                "jwt_access_token_expire_minutes": self.security.jwt_access_token_expire_minutes,
            },
            "file": {
                "max_file_size_mb": self.file.max_file_size_mb,
                "allowed_file_extensions": self.file.allowed_file_extensions,
            },
            "rate_limit": {
                "enabled": self.rate_limit.enabled,
                "default_rate_limit_per_minute": self.rate_limit.default_rate_limit_per_minute,
            },
            "application": {
                "app_name": self.application.app_name,
                "app_version": self.application.app_version,
                "debug": self.application.debug,
                "log_level": self.application.log_level.value,
                "cors_allowed_origins": self.application.cors_allowed_origins,
            },
        }


class ConfigurationManager:
    """
    Centralized configuration management system with validation,
    dynamic updates, and environment variable handling.
    """

    def __init__(self):
        self._config: Optional[SystemConfig] = None
        self._config_file_path: Optional[Path] = None
        self._watchers: List[callable] = []

    def load_from_environment(self) -> SystemConfig:
        """
        Load configuration from environment variables with comprehensive validation.

        Returns:
            SystemConfig: Validated system configuration

        Raises:
            ConfigurationError: If configuration is invalid or missing required values
        """
        try:

            def resolve_env(primary_name: str, *alias_names: str) -> str:
                primary_value = (os.getenv(primary_name) or "").strip()
                alias_values = {
                    alias_name: (os.getenv(alias_name) or "").strip()
                    for alias_name in alias_names
                }

                if primary_value:
                    for alias_name, alias_value in alias_values.items():
                        if alias_value and alias_value != primary_value:
                            raise ConfigValidationError(
                                f"Conflicting env vars: {primary_name} and {alias_name}. "
                                "Use one unified Supabase project configuration."
                            )
                    return primary_value

                non_empty_aliases = {
                    alias_name: alias_value
                    for alias_name, alias_value in alias_values.items()
                    if alias_value
                }
                distinct_values = set(non_empty_aliases.values())

                if len(distinct_values) > 1:
                    conflict_names = ", ".join(sorted(non_empty_aliases.keys()))
                    raise ConfigValidationError(
                        f"Conflicting env aliases for {primary_name}: {conflict_names}. "
                        "Use one unified Supabase project configuration."
                    )

                return next(iter(distinct_values), "")

            def ensure_same_project(primary_value: str, secondary_name: str) -> None:
                secondary_value = (os.getenv(secondary_name) or "").strip()
                if (
                    secondary_value
                    and primary_value
                    and secondary_value != primary_value
                ):
                    raise ConfigValidationError(
                        f"{secondary_name} points to a different Supabase project. "
                        "This backend supports only one unified Supabase project."
                    )

            # Load database configuration
            database_config = DatabaseConfig(
                supabase_url=resolve_env("SUPABASE_URL", "supabase_url"),
                supabase_key=resolve_env("SUPABASE_KEY", "supabase_key"),
                supabase_service_role_key=resolve_env(
                    "SUPABASE_SERVICE_ROLE_KEY",
                    "SERVICE_ROLE_KEY",
                    "supabase_service_role_key",
                ),
            )

            for legacy_url_var in (
                "RAG_SUPABASE_URL",
                "SUPABASE_RAG_URL",
                "VECTOR_SUPABASE_URL",
            ):
                ensure_same_project(database_config.supabase_url, legacy_url_var)

            for legacy_key_var in (
                "RAG_SUPABASE_KEY",
                "SUPABASE_RAG_KEY",
                "VECTOR_SUPABASE_KEY",
            ):
                ensure_same_project(database_config.supabase_key, legacy_key_var)

            for legacy_service_var in (
                "RAG_SUPABASE_SERVICE_ROLE_KEY",
                "SUPABASE_RAG_SERVICE_ROLE_KEY",
                "VECTOR_SUPABASE_SERVICE_ROLE_KEY",
            ):
                ensure_same_project(
                    database_config.supabase_service_role_key, legacy_service_var
                )

            # Load AI configuration
            ai_config = AIConfig(
                gemini_api_key=os.getenv("GEMINI_API_KEY"),
                embedding_model=os.getenv(
                    "RAG_EMBEDDING_MODEL", "models/embedding-001"
                ),
                generation_model=os.getenv("RAG_GENERATION_MODEL", "gemini-1.5-flash"),
                max_retries=int(os.getenv("RAG_MAX_RETRIES", "3")),
                retry_delay=float(os.getenv("RAG_RETRY_DELAY", "1.0")),
                retry_backoff_factor=float(
                    os.getenv("RAG_RETRY_BACKOFF_FACTOR", "2.0")
                ),
                max_retry_delay=float(os.getenv("RAG_MAX_RETRY_DELAY", "60.0")),
            )

            # Load RAG configuration
            rag_config = RAGConfig(
                chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1500")),
                chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "300")),
                similarity_threshold=float(
                    os.getenv("RAG_SIMILARITY_THRESHOLD", "0.7")
                ),
                max_chunks_per_query=int(os.getenv("RAG_MAX_CHUNKS_PER_QUERY", "5")),
            )

            # Load security configuration
            security_config = SecurityConfig(
                jwt_secret_key=os.getenv("JWT_SECRET_KEY", ""),
                jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
                jwt_access_token_expire_minutes=int(
                    os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30")
                ),
            )

            # Load file configuration
            allowed_extensions = os.getenv(
                "ALLOWED_FILE_EXTENSIONS", ".pdf,.doc,.docx,.txt"
            )
            file_config = FileConfig(
                max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "50")),
                allowed_file_extensions=[
                    ext.strip() for ext in allowed_extensions.split(",")
                ],
            )

            # Load rate limiting configuration
            rate_limit_config = RateLimitConfig(
                enabled=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
                default_rate_limit_per_minute=int(
                    os.getenv("DEFAULT_RATE_LIMIT_PER_MINUTE", "60")
                ),
            )

            # Load application configuration
            log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
            try:
                log_level = LogLevel(log_level_str)
            except ValueError:
                logger.warning(
                    f"Invalid LOG_LEVEL '{log_level_str}', defaulting to INFO"
                )
                log_level = LogLevel.INFO

            application_config = ApplicationConfig(
                app_name=os.getenv("APP_NAME", "College Platform API"),
                app_version=os.getenv("APP_VERSION", "1.0.0"),
                debug=os.getenv("DEBUG", "false").lower() == "true",
                log_level=log_level,
                cors_allowed_origins=[
                    origin.strip()
                    for origin in os.getenv(
                        "CORS_ALLOWED_ORIGINS",
                        "http://localhost,http://localhost:5173,http://localhost:5174,http://localhost:5175",
                    ).split(",")
                    if origin.strip()
                ],
            )

            # Create complete system configuration
            system_config = SystemConfig(
                database=database_config,
                ai=ai_config,
                rag=rag_config,
                security=security_config,
                file=file_config,
                rate_limit=rate_limit_config,
                application=application_config,
            )

            # Validate configuration
            validation_errors = system_config.validate()
            if validation_errors:
                error_message = "Configuration validation failed:\n" + "\n".join(
                    f"  - {error}" for error in validation_errors
                )
                logger.error(error_message)
                raise ConfigValidationError(error_message)

            # Configure external services
            self._configure_external_services(system_config)

            # Store configuration
            self._config = system_config

            logger.info(
                "Configuration loaded and validated successfully from environment variables"
            )
            return system_config

        except (ValueError, TypeError) as e:
            error_message = (
                f"Failed to parse configuration from environment variables: {str(e)}"
            )
            logger.error(error_message)
            raise ConfigurationError(error_message)
        except ConfigValidationError:
            raise
        except Exception as e:
            error_message = f"Unexpected error loading configuration: {str(e)}"
            logger.error(error_message)
            raise ConfigurationError(error_message)

    def load_from_file(self, config_file_path: Union[str, Path]) -> SystemConfig:
        """
        Load configuration from JSON file with validation.

        Args:
            config_file_path: Path to configuration file

        Returns:
            SystemConfig: Validated system configuration

        Raises:
            ConfigurationError: If file cannot be loaded or configuration is invalid
        """
        config_path = Path(config_file_path)

        if not config_path.exists():
            raise ConfigurationError(f"Configuration file not found: {config_path}")

        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)

            raise ConfigurationError(
                "Loading configuration from file is not supported yet. "
                f"Parsed JSON from {config_path}, but this backend currently requires environment-based configuration."
            )

        except ConfigurationError:
            raise
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in configuration file: {str(e)}")
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration file: {str(e)}")

    def get_config(self) -> SystemConfig:
        """
        Get current system configuration, loading it if necessary.

        Returns:
            SystemConfig: Current system configuration

        Raises:
            ConfigurationError: If configuration cannot be loaded
        """
        if self._config is None:
            self._config = self.load_from_environment()
        return self._config

    def update_config(self, updates: Dict[str, Any]) -> None:
        """
        Dynamically update configuration parameters.

        Args:
            updates: Dictionary of configuration updates

        Raises:
            ConfigUpdateError: If update fails or results in invalid configuration
        """
        if self._config is None:
            raise ConfigUpdateError("No configuration loaded")

        try:
            # Create a copy of current configuration for validation
            current_dict = self._config.to_dict()

            # Apply updates (nested dictionary update)
            def update_nested_dict(d: dict, updates: dict):
                for key, value in updates.items():
                    if (
                        isinstance(value, dict)
                        and key in d
                        and isinstance(d[key], dict)
                    ):
                        update_nested_dict(d[key], value)
                    else:
                        d[key] = value

            update_nested_dict(current_dict, updates)

            raise ConfigUpdateError(
                "Dynamic configuration updates are not supported yet. "
                "Restart the application with updated environment variables instead."
            )

        except ConfigUpdateError:
            raise
        except Exception as e:
            raise ConfigUpdateError(f"Failed to update configuration: {str(e)}")

    def add_config_watcher(self, watcher: callable) -> None:
        """
        Add a configuration change watcher.

        Args:
            watcher: Callable that receives (config, updates) when configuration changes
        """
        self._watchers.append(watcher)

    def validate_current_config(self) -> List[str]:
        """
        Validate current configuration and return any errors.

        Returns:
            List of validation error messages
        """
        if self._config is None:
            return ["No configuration loaded"]

        return self._config.validate()

    def get_config_summary(self) -> Dict[str, Any]:
        """
        Get a summary of current configuration (with sensitive data redacted).

        Returns:
            Dictionary containing configuration summary
        """
        if self._config is None:
            return {"status": "not_loaded"}

        return {
            "status": "loaded",
            "validation_errors": self.validate_current_config(),
            "config": self._config.to_dict(),
        }

    def _configure_external_services(self, config: SystemConfig) -> None:
        """
        Configure external services based on configuration.

        Args:
            config: System configuration
        """
        try:
            # Configure Google Gemini AI
            if config.ai.gemini_api_key:
                genai.configure(api_key=config.ai.gemini_api_key)
                logger.info("Google Gemini AI configured successfully")
            else:
                logger.warning(
                    "GEMINI_API_KEY not configured - RAG functionality will be limited"
                )

            # Configure logging level
            logging.getLogger().setLevel(config.application.log_level.value)
            logger.info(f"Logging level set to {config.application.log_level.value}")

        except Exception as e:
            logger.warning(f"Failed to configure external services: {str(e)}")


# Global configuration manager instance
_config_manager: Optional[ConfigurationManager] = None


def get_config_manager() -> ConfigurationManager:
    """Get the global configuration manager instance"""
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigurationManager()
    return _config_manager


def get_system_config() -> SystemConfig:
    """Get the current system configuration"""
    return get_config_manager().get_config()


def validate_startup_configuration() -> None:
    """
    Validate configuration at application startup.

    Raises:
        ConfigurationError: If configuration is invalid
    """
    try:
        config_manager = get_config_manager()
        config = config_manager.get_config()

        validation_errors = config.validate()
        if validation_errors:
            error_message = "Startup configuration validation failed:\n" + "\n".join(
                f"  - {error}" for error in validation_errors
            )
            logger.error(error_message)
            raise ConfigurationError(error_message)

        logger.info("Startup configuration validation passed")

        # Log configuration summary (without sensitive data)
        summary = config_manager.get_config_summary()
        logger.info(
            f"Configuration loaded: {summary['config']['application']['app_name']} v{summary['config']['application']['app_version']}"
        )

        # Log warnings for optional but recommended settings
        if not config.ai.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY not configured - RAG functionality will be limited"
            )

        if config.application.debug:
            logger.warning("DEBUG mode is enabled - not recommended for production")

        if (
            config.security.jwt_secret_key
            == "your-super-secret-jwt-key-change-this-in-production"
        ):
            logger.warning(
                "Default JWT_SECRET_KEY detected - change this in production"
            )

    except ConfigurationError:
        raise
    except Exception as e:
        error_message = (
            f"Unexpected error during startup configuration validation: {str(e)}"
        )
        logger.error(error_message)
        raise ConfigurationError(error_message)
