"""구조화 로거 (user rule 4: 로그로 에러 파악 용이).

콘솔 + (선택)파일 핸들러. 에러는 traceback 까지 기록.
"""

from __future__ import annotations

import logging
import sys
from logging import Logger
from pathlib import Path


_DEF_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"


def get_logger(
    name: str,
    *,
    level: int = logging.INFO,
    log_file: Path | None = None,
) -> Logger:
    """모듈별 로거를 반환한다.

    Args:
        name: logger 이름 (보통 ``__name__``)
        level: 로그 레벨
        log_file: 설정 시 파일로도 기록
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    # 중복 핸들러 방지 (pytest/runtime 에서 여러번 import 될 때)
    if logger.handlers:
        return logger

    formatter = logging.Formatter(_DEF_FORMAT)

    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_h = logging.FileHandler(log_file, encoding="utf-8")
        file_h.setFormatter(formatter)
        logger.addHandler(file_h)

    logger.propagate = False
    return logger
