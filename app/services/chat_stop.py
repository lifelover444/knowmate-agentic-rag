from __future__ import annotations

from dataclasses import dataclass
from threading import Lock


@dataclass
class StopState:
    session_id: str
    generation_id: str
    stopped: bool = False
    reason: str = "用户已停止生成"


class ChatStopRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._active: dict[str, StopState] = {}

    def register(self, session_id: str, generation_id: str) -> StopState:
        with self._lock:
            state = StopState(session_id=session_id, generation_id=generation_id)
            self._active[session_id] = state
            return state

    def unregister(self, session_id: str, generation_id: str) -> None:
        with self._lock:
            state = self._active.get(session_id)
            if state and state.generation_id == generation_id:
                self._active.pop(session_id, None)

    def stop_session(self, session_id: str, reason: str = "用户已停止生成") -> bool:
        with self._lock:
            state = self._active.get(session_id)
            if state is None:
                return False
            state.stopped = True
            state.reason = reason
            return True

    def is_stopped(self, session_id: str, generation_id: str) -> tuple[bool, str]:
        with self._lock:
            state = self._active.get(session_id)
            if state is None or state.generation_id != generation_id:
                return False, ""
            return state.stopped, state.reason
