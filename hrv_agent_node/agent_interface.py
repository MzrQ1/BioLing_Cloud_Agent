"""
HRV Agent Interface - 智能体调用接口

此模块提供标准化的智能体调用接口，
使外部智能体能够方便地调用HRV分析功能。

接口遵循常见的智能体节点规范，
支持JSON格式的输入输出，
适用于各种智能体平台集成。
"""

import json
import numpy as np
from hrv_analyzer import analyze_hrv, HRVAgentNode

class HRVAgentInterface:
    """HRV智能体调用接口"""
    
    def __init__(self):
        """初始化接口"""
        self.analyzer = HRVAgentNode()
    
    def process_request(self, request):
        """
        处理智能体请求
        
        参数:
            request: dict，请求数据
            
        返回:
            dict: 响应数据
        """
        try:
            # 解析请求
            nni = request.get('nni')
            signal = request.get('signal')
            rpeaks = request.get('rpeaks')
            sampling_rate = request.get('sampling_rate', 1000)
            show = request.get('show', False)
            
            # 转换数据格式
            if nni:
                nni = np.array(nni)
            if signal:
                signal = np.array(signal)
            if rpeaks:
                rpeaks = np.array(rpeaks)
            
            # 执行分析
            results = analyze_hrv(
                nni=nni,
                signal=signal,
                rpeaks=rpeaks,
                sampling_rate=sampling_rate,
                show=show
            )
            
            # 构建响应
            response = {
                "status": "success",
                "data": results,
                "message": "HRV分析成功",
                "metadata": {
                    "module": "HRV Agent Node",
                    "version": "1.0.0",
                    "features": self.analyzer.get_supported_features()
                }
            }
            
        except Exception as e:
            # 错误处理
            response = {
                "status": "error",
                "message": str(e),
                "data": None,
                "metadata": {
                    "module": "HRV Agent Node",
                    "version": "1.0.0"
                }
            }
        
        return response
    
    def process_json_request(self, json_str):
        """
        处理JSON格式的请求
        
        参数:
            json_str: str，JSON格式的请求字符串
            
        返回:
            str: JSON格式的响应字符串
        """
        try:
            request = json.loads(json_str)
            response = self.process_request(request)
            return json.dumps(response, indent=2)
        except json.JSONDecodeError:
            return json.dumps({
                "status": "error",
                "message": "Invalid JSON format",
                "data": None
            }, indent=2)
    
    def get_info(self):
        """
        获取接口信息
        
        返回:
            dict: 接口信息
        """
        return self.analyzer.get_info()
    
    def health_check(self):
        """
        健康检查
        
        返回:
            dict: 健康状态
        """
        return {
            "status": "healthy",
            "module": "HRV Agent Node",
            "version": "1.0.0"
        }

# 便捷函数
def process_hrv_request(request):
    """
    便捷函数：处理HRV请求
    
    参数:
        request: dict，请求数据
        
    返回:
        dict: 响应数据
    """
    interface = HRVAgentInterface()
    return interface.process_request(request)

def process_hrv_json_request(json_str):
    """
    便捷函数：处理JSON格式的HRV请求
    
    参数:
        json_str: str，JSON格式的请求字符串
        
    返回:
        str: JSON格式的响应字符串
    """
    interface = HRVAgentInterface()
    return interface.process_json_request(json_str)

# 命令行接口
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 从命令行参数读取JSON文件
        if sys.argv[1] == "--info":
            # 显示模块信息
            interface = HRVAgentInterface()
            info = interface.get_info()
            print(json.dumps(info, indent=2))
        
        elif sys.argv[1] == "--health":
            # 健康检查
            interface = HRVAgentInterface()
            health = interface.health_check()
            print(json.dumps(health, indent=2))
        
        elif sys.argv[1] == "--test":
            # 运行测试
            # 生成示例数据
            nni = list(np.random.normal(800, 50, 75))  # 1分钟数据
            
            # 构建测试请求
            test_request = {
                "nni": nni,
                "show": True
            }
            
            # 处理请求
            interface = HRVAgentInterface()
            response = interface.process_request(test_request)
            print(json.dumps(response, indent=2))
        
        else:
            # 从文件读取JSON请求
            try:
                with open(sys.argv[1], 'r', encoding='utf-8') as f:
                    json_str = f.read()
                
                interface = HRVAgentInterface()
                response = interface.process_json_request(json_str)
                print(response)
                
            except FileNotFoundError:
                print(json.dumps({
                    "status": "error",
                    "message": f"File not found: {sys.argv[1]}"
                }, indent=2))
    
    else:
        # 交互式模式
        print("HRV Agent Interface - 交互式模式")
        print("输入JSON格式的请求，或输入'info'查看模块信息")
        print("输入'quit'退出")
        
        interface = HRVAgentInterface()
        
        while True:
            try:
                user_input = input("$ ")
                
                if user_input.lower() == 'quit':
                    break
                
                elif user_input.lower() == 'info':
                    info = interface.get_info()
                    print(json.dumps(info, indent=2))
                
                elif user_input.lower() == 'health':
                    health = interface.health_check()
                    print(json.dumps(health, indent=2))
                
                else:
                    # 处理JSON输入
                    response = interface.process_json_request(user_input)
                    print(response)
                    
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")
