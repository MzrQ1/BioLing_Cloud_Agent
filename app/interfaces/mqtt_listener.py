"""MQTT监听器 - 接收ESP32传感器数据"""
import json
from typing import Callable, Optional
from datetime import datetime

from app.database.ibi_buffer import get_ibi_buffer


class MQTTListener:
    """
    MQTT 监听器 - 支持两种数据格式：
    
    1. 单个 IBI 值（ESP32 实时心跳）：纯数字字符串，如 "850.23"
       - 每次心跳发送一个 IBI 值（单位：毫秒）
       - 自动存入 IBI 缓冲区
    
    2. JSON 格式（批量/测试用）：
       {
         "user_id": "user_001",
         "device_id": "esp32_001",
         "ibi": [812, 825, 818],
         "sdnn": 28.5
       }
    """

    def __init__(self, broker: str = "localhost", port: int = 1883,
                 topic: str = "biolid/esp32/sensor_data"):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client = None
        self._callback: Optional[Callable] = None
        self._connected = False
        self._ibi_buffer = None

    def set_callback(self, callback: Callable):
        """设置数据处理回调"""
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
                    payload_str = msg.payload.decode().strip()
                    self._handle_message(payload_str)
                except Exception:
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

    def _get_ibi_buffer(self):
        """懒加载 IBI 缓冲区"""
        if self._ibi_buffer is None:
            self._ibi_buffer = get_ibi_buffer()
        return self._ibi_buffer

    def _handle_message(self, payload_str: str):
        """
        处理 MQTT 消息
        
        支持两种格式：
        1. 纯数字字符串：单个 IBI 值，如 "850.23"
        2. JSON 对象：批量数据或带元数据的消息
        """
        try:
            data = json.loads(payload_str)

            if isinstance(data, (int, float)):
                ibi_buffer = self._get_ibi_buffer()
                result = ibi_buffer.add_ibi_from_mqtt(
                    str(data),
                    user_id=data.get("user_id", "default"),
                    device_id=data.get("device_id", "esp32_001")
                )
                if result.get("features") and self._callback:
                    self._callback(result["features"])
                return

            if isinstance(data, dict):
                user_id = data.get("user_id", "default")
                device_id = data.get("device_id", "esp32_001")

                ibi_list = data.get("ibi", [])
                
                if ibi_list and isinstance(ibi_list, list):
                    ibi_buffer = self._get_ibi_buffer()
                    
                    for ibi_val in ibi_list:
                        ibi_buffer.add_ibi(
                            float(ibi_val),
                            user_id=user_id,
                            device_id=device_id
                        )

                    features = ibi_buffer.extract_features(user_id)
                    if features and self._callback:
                        self._callback(features)
                    return

                processed_data = self._process_json_payload(data)
                if self._callback and processed_data:
                    self._callback(processed_data)
                return

        except json.JSONDecodeError:
            pass

        try:
            ibi_value = float(payload_str.strip())
            
            if 200 <= ibi_value <= 2000:
                ibi_buffer = self._get_ibi_buffer()
                result = ibi_buffer.add_ibi_from_mqtt(
                    payload_str,
                    user_id="default",
                    device_id="esp32_001"
                )
                
                if result.get("features") and self._callback:
                    self._callback(result["features"])
        except ValueError:
            pass

    def _process_json_payload(self, payload: dict) -> dict:
        """处理 JSON 格式的完整数据包"""
        ibi_list = payload.get("ibi", [])
        sdnn = payload.get("sdnn", 0)

        mean_ibi = sum(ibi_list) / len(ibi_list) if ibi_list else 0
        heart_rate = 60000 / mean_ibi if mean_ibi > 0 else 0

        rmssd = 0
        if len(ibi_list) >= 2:
            diffs = [ibi_list[i+1] - ibi_list[i] 
                    for i in range(len(ibi_list)-1)]
            rmssd = (sum(d*d for d in diffs) / len(diffs)) ** 0.5

        processed = {
            "user_id": payload.get("user_id", "unknown"),
            "device_id": payload.get("device_id", "esp32_001"),
            "timestamp": payload.get("timestamp", 
                                     datetime.now().isoformat()),
            "sensors": {
                "heart_rate": round(heart_rate, 1),
                "ibi": ibi_list,
                "sdnn": sdnn,
                "mean_ibi": round(mean_ibi, 1),
                "rmssd": round(rmssd, 1)
            }
        }
        return processed
