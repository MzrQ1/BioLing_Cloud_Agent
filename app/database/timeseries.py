"""时序数据库 - SQLite持久化存储传感器数据"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import json
from sqlalchemy import func, and_

from .database import get_db_context
from .models import PhysiologicalData

class TimeSeriesDB:
    """
    时序数据库 - SQLite持久化
    
    功能：
    - 传感器原始数据存储
    - 时间范围查询
    - 数据清理
    """

    def write(self, user_id: str, data_point: Dict) -> bool:
        """
        写入传感器数据点
        
        Args:
            user_id: 用户ID
            data_point: 数据点字典，包含timestamp, heart_rate, ibi, sdnn等
            
        Returns:
            是否写入成功
        """
        with get_db_context() as db:
            timestamp_str = data_point.get("timestamp")
            if isinstance(timestamp_str, str):
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                except ValueError:
                    timestamp = datetime.utcnow()
            else:
                timestamp = datetime.utcnow()
            
            sensors = data_point.get("sensors", data_point)
            
            record = PhysiologicalData(
                user_id=user_id,
                device_id=data_point.get("device_id"),
                timestamp=timestamp,
                heart_rate=sensors.get("heart_rate"),
                ibi_mean=sensors.get("mean_ibi"),
                ibi_list=json.dumps(sensors.get("ibi", [])),
                sdnn=sensors.get("sdnn"),
                rmssd=sensors.get("rmssd"),
                stress_index=sensors.get("stress_index"),
                emotion=sensors.get("emotion"),
                risk_level=sensors.get("risk_level")
            )
            db.add(record)
            
        return True

    def write_batch(self, user_id: str, data_points: List[Dict]) -> bool:
        """
        批量写入传感器数据
        
        Args:
            user_id: 用户ID
            data_points: 数据点列表
            
        Returns:
            是否写入成功
        """
        with get_db_context() as db:
            records = []
            for dp in data_points:
                timestamp_str = dp.get("timestamp")
                if isinstance(timestamp_str, str):
                    try:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    except ValueError:
                        timestamp = datetime.utcnow()
                else:
                    timestamp = datetime.utcnow()
                
                sensors = dp.get("sensors", dp)
                
                record = PhysiologicalData(
                    user_id=user_id,
                    device_id=dp.get("device_id"),
                    timestamp=timestamp,
                    heart_rate=sensors.get("heart_rate"),
                    ibi_mean=sensors.get("mean_ibi"),
                    ibi_list=json.dumps(sensors.get("ibi", [])),
                    sdnn=sensors.get("sdnn"),
                    rmssd=sensors.get("rmssd"),
                    stress_index=sensors.get("stress_index"),
                    emotion=sensors.get("emotion"),
                    risk_level=sensors.get("risk_level")
                )
                records.append(record)
            
            db.add_all(records)
            
        return True

    def query(self, user_id: str, time_range: str = "24h") -> List[Dict]:
        """
        查询时间范围内的数据
        
        Args:
            user_id: 用户ID
            time_range: 时间范围 (1h, 6h, 12h, 24h, 7d, 30d)
            
        Returns:
            数据点列表
        """
        with get_db_context() as db:
            hours = self._parse_time_range(time_range)
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            results = db.query(PhysiologicalData).filter(
                and_(
                    PhysiologicalData.user_id == user_id,
                    PhysiologicalData.timestamp >= cutoff
                )
            ).order_by(PhysiologicalData.timestamp).all()
            
            return [self._record_to_dict(r) for r in results]

    def query_range(
        self,
        user_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[Dict]:
        """
        查询指定时间范围的数据
        
        Args:
            user_id: 用户ID
            start_time: 开始时间
            end_time: 结束时间
            
        Returns:
            数据点列表
        """
        with get_db_context() as db:
            results = db.query(PhysiologicalData).filter(
                and_(
                    PhysiologicalData.user_id == user_id,
                    PhysiologicalData.timestamp >= start_time,
                    PhysiologicalData.timestamp <= end_time
                )
            ).order_by(PhysiologicalData.timestamp).all()
            
            return [self._record_to_dict(r) for r in results]

    def get_latest(self, user_id: str, limit: int = 10) -> List[Dict]:
        """
        获取最近的数据点
        
        Args:
            user_id: 用户ID
            limit: 返回数量
            
        Returns:
            数据点列表
        """
        with get_db_context() as db:
            results = db.query(PhysiologicalData).filter(
                PhysiologicalData.user_id == user_id
            ).order_by(PhysiologicalData.timestamp.desc()).limit(limit).all()
            
            return [self._record_to_dict(r) for r in reversed(results)]

    def get_aggregated(
        self,
        user_id: str,
        time_range: str = "24h",
        interval: str = "1h"
    ) -> List[Dict]:
        """
        获取聚合数据（按时间间隔）
        
        Args:
            user_id: 用户ID
            time_range: 时间范围
            interval: 聚合间隔 (1h, 6h, 1d)
            
        Returns:
            聚合数据列表
        """
        with get_db_context() as db:
            hours = self._parse_time_range(time_range)
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            results = db.query(
                func.strftime('%Y-%m-%d %H:00', PhysiologicalData.timestamp).label('hour'),
                func.avg(PhysiologicalData.heart_rate).label('avg_hr'),
                func.avg(PhysiologicalData.sdnn).label('avg_sdnn'),
                func.avg(PhysiologicalData.stress_index).label('avg_stress'),
                func.count(PhysiologicalData.id).label('count')
            ).filter(
                and_(
                    PhysiologicalData.user_id == user_id,
                    PhysiologicalData.timestamp >= cutoff
                )
            ).group_by('hour').order_by('hour').all()
            
            return [
                {
                    "timestamp": r.hour,
                    "avg_heart_rate": float(r.avg_hr or 0),
                    "avg_sdnn": float(r.avg_sdnn or 0),
                    "avg_stress_index": float(r.avg_stress or 0),
                    "sample_count": r.count
                }
                for r in results
            ]

    def delete_old_data(self, user_id: str, days: int = 30) -> int:
        """
        删除旧数据
        
        Args:
            user_id: 用户ID
            days: 保留天数
            
        Returns:
            删除的记录数
        """
        with get_db_context() as db:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            deleted = db.query(PhysiologicalData).filter(
                and_(
                    PhysiologicalData.user_id == user_id,
                    PhysiologicalData.timestamp < cutoff
                )
            ).delete()
            
            return deleted

    def get_statistics(self, user_id: str, time_range: str = "24h") -> Dict:
        """
        获取统计信息
        
        Args:
            user_id: 用户ID
            time_range: 时间范围
            
        Returns:
            统计信息字典
        """
        with get_db_context() as db:
            hours = self._parse_time_range(time_range)
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            
            stats = db.query(
                func.avg(PhysiologicalData.heart_rate).label('avg_hr'),
                func.min(PhysiologicalData.heart_rate).label('min_hr'),
                func.max(PhysiologicalData.heart_rate).label('max_hr'),
                func.avg(PhysiologicalData.sdnn).label('avg_sdnn'),
                func.avg(PhysiologicalData.stress_index).label('avg_stress'),
                func.count(PhysiologicalData.id).label('total')
            ).filter(
                and_(
                    PhysiologicalData.user_id == user_id,
                    PhysiologicalData.timestamp >= cutoff
                )
            ).first()
            
            if not stats or stats.total == 0:
                return {
                    "total_records": 0,
                    "avg_heart_rate": 0,
                    "min_heart_rate": 0,
                    "max_heart_rate": 0,
                    "avg_sdnn": 0,
                    "avg_stress_index": 0
                }
            
            return {
                "total_records": stats.total,
                "avg_heart_rate": float(stats.avg_hr or 0),
                "min_heart_rate": float(stats.min_hr or 0),
                "max_heart_rate": float(stats.max_hr or 0),
                "avg_sdnn": float(stats.avg_sdnn or 0),
                "avg_stress_index": float(stats.avg_stress or 0)
            }

    def _record_to_dict(self, record: PhysiologicalData) -> Dict:
        """将数据库记录转换为字典"""
        return {
            "timestamp": record.timestamp.isoformat() if record.timestamp else None,
            "data": {
                "user_id": record.user_id,
                "device_id": record.device_id,
                "heart_rate": record.heart_rate,
                "ibi_mean": record.ibi_mean,
                "ibi_list": json.loads(record.ibi_list) if record.ibi_list else [],
                "sdnn": record.sdnn,
                "rmssd": record.rmssd,
                "stress_index": record.stress_index,
                "emotion": record.emotion,
                "risk_level": record.risk_level
            }
        }

    def _parse_time_range(self, time_range: str) -> int:
        """解析时间范围为小时数"""
        time_map = {
            "1h": 1,
            "6h": 6,
            "12h": 12,
            "24h": 24,
            "7d": 168,
            "30d": 720
        }
        return time_map.get(time_range, 24)
