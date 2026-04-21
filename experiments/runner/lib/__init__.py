"""공용 헬퍼 모듈 패키지 (runner/lib).

주의:
- ``lib`` 를 import 해도 heavy 의존성(`yaml`, `pandas`) 를 eager 하게 끌어오지 않도록,
  여기서는 **아무것도 import 하지 않는다**. 각 하위 모듈을 직접 import 해서 쓸 것.

예:
    from lib.logger import get_logger
    from lib.metrics import evaluate_run    # yaml 필요
    from lib.stream_parser import parse_stream
"""
