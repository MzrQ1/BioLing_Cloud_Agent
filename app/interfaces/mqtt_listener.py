"""MQTT监听器 - 接收ESP32传感器数据"""
import json
from typing import Callable, Optional
from datetime import datetime

class MQTTListener:
    def __init__(self, broker: str = "localhost", port: int = 1883, topic: str = "biolid/esp32/sensor_data"):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = None
        self._callback: Optional[Callable] = None
        self._connected = False

    def set_callback(self, callback: Callable):
        self._callback = callback

    def connect(self) -> bool:
        try:
            import paho.mqtt.client as mqtt

            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    self._connected = True
                    client.subscribe(self.topic)
                else:
                    self._connected = False

            def on_message(client, userdata, msg):
                try:
                    payload = json.loads(msg.payload.decode())
                    processed_data = self._process_payload(payload)
                    if self._callback:
                        self._callback(processed_data)
                except json.JSONDecodeError:
                    pass

            self.client = mqtt.Client()
            self.client.on_connect = on_connect
            self.client.on_message = on_message
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()

            return True
        except ImportError:
            return False
        except Exception:
            return False

    def disconnect(self):
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def _process_payload(self, payload: dict) -> dict:
        ibi_list = payload.get("ibi", [])
        sdnn = payload.get("sdnn", 0)

        mean_ibi = sum(ibi_list) / len(ibi_list) if ibi_list else 0
        heart_rate = 60000 / mean_ibi if mean_ibi > 0 else 0

        rmssd = 0
        if len(ibi_list) >= 2:
            diffs = [ibi_list[i+1] - ibi_list[i] for i in range(len(ibi_list)-1)]
            rmssd = (sum(d*d for d in diffs) / len(diffs)) ** 0.5

        processed = {
            "user_id": payload.get("user_id", "unknown"),
            "device_id": payload.get("device_id", "esp32_001"),
            "timestamp": payload.get("timestamp", datetime.now().isoformat()),
            "sensors": {
                "heart_rate": round(heart_rate, 1),
                "ibi": ibi_list,
                "sdnn": sdnn,
                "mean_ibi": round(mean_ibi, 1),
                "rmssd": round(rmssd, 1)
            }
        }
        return processed
