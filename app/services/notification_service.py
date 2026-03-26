"""通知服务 - 设备联动和推送"""
from typing import Dict, Optional
import json

class NotificationService:
    def __init__(self):
        self._device_queue = []

    def send_device_command(self, command: Dict) -> bool:
        device = command.get("device")
        action = command.get("action")
        duration = command.get("duration_seconds", 300)
        intensity = command.get("intensity", "medium")

        device_command = {
            "device": device,
            "action": action,
            "duration_seconds": duration,
            "intensity": intensity,
            "status": "pending"
        }

        self._device_queue.append(device_command)

        return True

    def get_pending_commands(self, device: Optional[str] = None) -> list:
        if device:
            return [c for c in self._device_queue if c.get("device") == device]
        return self._device_queue.copy()

    def clear_command(self, command: Dict) -> bool:
        if command in self._device_queue:
            self._device_queue.remove(command)
            return True
        return False

    def send_push_notification(self, user_id: str, title: str, body: str) -> bool:
        notification = {
            "user_id": user_id,
            "title": title,
            "body": body
        }

        return True
