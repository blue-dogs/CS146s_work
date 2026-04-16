from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class Settings(BaseModel):
    """应用程序配置设置"""
    
    # 应用基本信息
    app_name: str = Field("Action Item Extractor", description="应用名称")
    app_version: str = Field("1.0.0", description="应用版本")
    debug: bool = Field(False, description="调试模式")
    
    # 服务器配置
    host: str = Field("0.0.0.0", description="服务器主机地址")
    port: int = Field(8000, description="服务器端口")
    
    # 数据库配置
    database_url: str = Field("", description="数据库URL（留空使用SQLite）")
    
    # LLM 配置
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama服务地址")
    ollama_model: str = Field("llama3.1:8b", description="默认LLM模型名称")
    llm_timeout: int = Field(30, description="LLM请求超时时间（秒）")
    use_llm_by_default: bool = Field(True, description="默认是否使用LLM")
    
    # 日志配置
    log_level: str = Field("INFO", description="日志级别")
    log_format: str = Field(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="日志格式"
    )
    
    # 路径配置
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[1])
    data_dir: Optional[Path] = None
    frontend_dir: Optional[Path] = None
    
    def __init__(self, **data: Any):
        super().__init__(**data)
        
        # 设置路径
        if self.data_dir is None:
            self.data_dir = self.base_dir / "data"
            
        if self.frontend_dir is None:
            self.frontend_dir = self.base_dir / "frontend"
    
    def get_database_path(self) -> Path:
        """获取数据库文件路径"""
        return self.data_dir / "app.db"
    
    def setup_logging(self) -> None:
        """配置日志系统"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format=self.log_format,
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        logger.info(f"Logging configured with level: {self.log_level}")
    
    def validate_configuration(self) -> Dict[str, Any]:
        """验证配置有效性"""
        issues: list[str] = []
        warnings: list[str] = []
        
        # 检查必要目录
        if not self.base_dir.exists():
            warnings.append(f"Base directory does not exist: {self.base_dir}")
        
        if not self.frontend_dir.exists():
            warnings.append(f"Frontend directory does not exist: {self.frontend_dir}")
        
        # 检查端口范围
        if not (1024 <= self.port <= 65535):
            issues.append(f"Invalid port number: {self.port}")
        
        # 检查日志级别
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level.upper() not in valid_levels:
            issues.append(f"Invalid log level: {self.log_level}")
        
        result = {
            "valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "settings": {
                "app_name": self.app_name,
                "app_version": self.app_version,
                "debug": self.debug,
                "host": self.host,
                "port": self.port,
                "ollama_model": self.ollama_model,
                "use_llm_by_default": self.use_llm_by_default,
                "log_level": self.log_level
            }
        }
        
        if issues:
            for issue in issues:
                logger.error(f"Configuration issue: {issue}")
        
        if warnings:
            for warning in warnings:
                logger.warning(f"Configuration warning: {warning}")
        
        return result


import os


def load_settings_from_env() -> dict:
    """从环境变量加载设置"""
    env_vars = {}
    env_prefix = "APP_"
    
    # 从.env文件加载（如果存在）
    env_file = ".env"
    if os.path.exists(env_file):
        try:
            with open(env_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        if key.startswith(env_prefix):
                            env_vars[key[len(env_prefix):].lower()] = value.strip('\"\'')
        except Exception as e:
            logger.warning(f"Failed to load .env file: {e}")
    
    # 从系统环境变量加载
    for key, value in os.environ.items():
        if key.startswith(env_prefix):
            env_key = key[len(env_prefix):].lower()
            env_vars[env_key] = value
    
    return env_vars


# 全局配置实例
settings = Settings(**load_settings_from_env())


def get_settings() -> Settings:
    """获取全局配置实例"""
    return settings


def reload_settings() -> Settings:
    """重新加载配置"""
    global settings
    settings = Settings(**load_settings_from_env())
    settings.setup_logging()
    return settings