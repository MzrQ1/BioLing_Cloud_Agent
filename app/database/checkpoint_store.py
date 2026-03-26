"""检查点存储 - LangGraph状态持久化"""
from typing import Dict, Optional
import json
from datetime import datetime

class CheckpointStore:
    def __init__(self):
        self._checkpoints: Dict[str, Dict] = {}

    def save_checkpoint(
        self,
        session_id: str,
        node_name: str,
        state: Dict,
        metadata: Optional[Dict] = None
    ) -> bool:
        if session_id not in self._checkpoints:
            self._checkpoints[session_id] = {
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "current_node": node_name,
                "history": []
            }

        self._checkpoints[session_id]["current_node"] = node_name
        self._checkpoints[session_id]["updated_at"] = datetime.now().isoformat()

        self._checkpoints[session_id]["history"].append({
            "node": node_name,
            "timestamp": datetime.now().isoformat(),
            "state_summary": self._summarize_state(state)
        })

        if len(self._checkpoints[session_id]["history"]) > 100:
            self._checkpoints[session_id]["history"] = \
                self._checkpoints[session_id]["history"][-50:]

        return True

    def get_checkpoint(self, session_id: str) -> Optional[Dict]:
        return self._checkpoints.get(session_id)

    def get_state_history(self, session_id: str) -> list:
        checkpoint = self._checkpoints.get(session_id)
        if checkpoint:
            return checkpoint.get("history", [])
        return []

    def clear_checkpoint(self, session_id: str) -> bool:
        if session_id in self._checkpoints:
            del self._checkpoints[session_id]
            return True
        return False

    def _summarize_state(self, state: Dict) -> Dict:
        return {
            "risk_level": state.get("risk_level", "unknown"),
            "next_node": state.get("next_node", "unknown"),
            "has_report": bool(state.get("report_content")),
            "has_suggestion": bool(state.get("suggestion"))
        }
