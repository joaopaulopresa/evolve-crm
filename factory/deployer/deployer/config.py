import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Config:
    git_dir: Path = field(default_factory=lambda: Path(os.environ.get("GIT_DIR", "/repo.git")))
    state_dir: Path = field(default_factory=lambda: Path(os.environ.get("STATE_DIR", "/state")))
    work_dir: Path = field(default_factory=lambda: Path(os.environ.get("WORK_DIR", "/work")))
    factory_key: str = field(default_factory=lambda: os.environ.get("FACTORY_KEY", ""))
    git_url: str = field(
        default_factory=lambda: os.environ.get("GIT_URL", "git://git:9418/repo.git")
    )
    crm_url: str = field(default_factory=lambda: os.environ.get("CRM_URL", "http://crm-api:8000"))
