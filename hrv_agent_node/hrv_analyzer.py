"""
HRV Agent Node - 短时间心率分析模块

此模块专为1-2分钟短时间心率数据设计，提供核心HRV参数计算功能，
适用于智能体节点调用。

支持的输入格式：
1. NNI序列 (相邻R波间隔，毫秒单位)
2. 原始ECG信号 (需提供采样率)
3. R波峰位置

输出：
- 核心HRV特征参数字典
- 可选的可视化图表
"""

import numpy as np
from scipy import signal
from scipy.integrate import simps
import matplotlib.pyplot as plt

class HRVAgentNode:
    """HRV智能体分析节点"""
    
    def __init__(self):
        """初始化HRV分析器"""
        self.name = "HRV Agent Node"
        self.version = "1.0.0"
        self.supported_features = [
            "sdnn",       # 全部NNI标准差
            "rmssd",      # 连续差值均方根
            "pnn50",      # >50ms差值百分比
            "lf",         # 低频功率
            "hf",         # 高频功率
            "lf_hf_ratio", # LF/HF比值
            "sd1",        # Poincaré短轴
            "sd2",        # Poincaré长轴
            "hr_mean",    # 平均心率
            "hr_std"       # 心率标准差
        ]
    
    def analyze(self, nni=None, signal=None, rpeaks=None, sampling_rate=1000, show=False):
        """
        分析心率数据并返回核心HRV特征
        
        参数:
            nni: list或numpy数组，NNI序列 (毫秒单位)
            signal: list或numpy数组，原始ECG信号
            rpeaks: list或numpy数组，R波峰位置
            sampling_rate: float，ECG采样率 (Hz)
            show: bool，是否显示分析结果
            
        返回:
            dict: HRV特征参数
        """
        # 1. 数据预处理
        nni = self._preprocess_input(nni, signal, rpeaks, sampling_rate)
        
        if nni is None or len(nni) < 10:
            raise ValueError("数据不足，至少需要10个NNI间隔")
        
        # 2. 计算HRV参数
        results = {}
        
        # 时域分析
        time_domain_results = self._time_domain_analysis(nni)
        results.update(time_domain_results)
        
        # 频域分析
        frequency_results = self._frequency_domain_analysis(nni)
        results.update(frequency_results)
        
        # 非线性分析
        nonlinear_results = self._nonlinear_analysis(nni)
        results.update(nonlinear_results)
        
        # 3. 显示结果
        if show:
            self._plot_results(nni, results)
        
        return results
    
    def _preprocess_input(self, nni, signal, rpeaks, sampling_rate):
        """处理输入数据"""
        if nni is not None:
            nni = np.array(nni)
            # 转换单位：如果值<10，认为是秒，转换为毫秒
            if np.max(nni) < 10:
                nni = nni * 1000
            return nni
        
        elif rpeaks is not None:
            rpeaks = np.array(rpeaks)
            # 计算NNI
            nni = np.diff(rpeaks)
            # 转换单位
            if np.max(nni) < 10:
                nni = nni * 1000
            return nni
        
        elif signal is not None:
            # 这里简化处理，实际应该使用biosppy进行R波检测
            # 为了减少依赖，这里返回None，建议用户提供NNI或R波峰
            print("警告: 原始ECG信号需要R波检测，建议直接提供NNI或R波峰")
            return None
        
        else:
            raise ValueError("至少需要提供nni、signal或rpeaks中的一种")
    
    def _time_domain_analysis(self, nni):
        """时域分析"""
        results = {}
        
        # 基本统计
        results['hr_mean'] = 60000 / np.mean(nni)
        results['hr_std'] = np.std(60000 / nni)
        
        # SDNN - 全部NNI标准差
        results['sdnn'] = np.std(nni)
        
        # RMSSD - 连续差值均方根
        diff_nni = np.diff(nni)
        results['rmssd'] = np.sqrt(np.mean(diff_nni**2))
        
        # pNN50 - >50ms差值百分比
        nn50 = np.sum(np.abs(diff_nni) > 50)
        results['pnn50'] = (nn50 / len(diff_nni)) * 100 if len(diff_nni) > 0 else 0
        
        return results
    
    def _frequency_domain_analysis(self, nni):
        """频域分析 (Welch方法)"""
        results = {}
        
        # 时间向量 (秒)
        t = np.cumsum(nni) / 1000.0
        
        # 重采样到均匀时间序列 (4Hz)
        fs = 4.0
        t_resampled = np.arange(t[0], t[-1], 1/fs)
        nni_resampled = np.interp(t_resampled, t, nni)
        
        # 去除均值
        nni_resampled = nni_resampled - np.mean(nni_resampled)
        
        # Welch功率谱密度
        f, Pxx = signal.welch(nni_resampled, fs=fs, nperseg=256, noverlap=128)
        
        # 频带定义 (短时间分析)
        vlf_band = (0.00, 0.04)
        lf_band = (0.04, 0.15)
        hf_band = (0.15, 0.40)
        
        # 计算各频带功率
        def band_power(freqs, psd, band):
            band_indices = np.logical_and(freqs >= band[0], freqs <= band[1])
            return simps(psd[band_indices], freqs[band_indices])
        
        lf = band_power(f, Pxx, lf_band)
        hf = band_power(f, Pxx, hf_band)
        
        results['lf'] = lf
        results['hf'] = hf
        results['lf_hf_ratio'] = lf / hf if hf > 0 else 0
        
        return results
    
    def _nonlinear_analysis(self, nni):
        """非线性分析"""
        results = {}
        
        # Poincaré图分析
        diff_nni = np.diff(nni)
        
        # SD1 (短轴) - 短期变异性
        sd1 = np.sqrt(np.mean(diff_nni**2) / 2)
        
        # SD2 (长轴) - 长期变异性
        # 计算相邻NNI的和
        sum_nni = nni[:-1] + nni[1:]
        sd2 = np.sqrt(2 * np.var(sum_nni))
        
        results['sd1'] = sd1
        results['sd2'] = sd2
        
        return results
    
    def _plot_results(self, nni, results):
        """绘制分析结果"""
        fig, axes = plt.subplots(2, 2, figsize=(12, 10))
        
        # 1. NNI序列
        axes[0, 0].plot(nni)
        axes[0, 0].set_title('NNI序列')
        axes[0, 0].set_xlabel('样本')
        axes[0, 0].set_ylabel('NNI (ms)')
        
        # 2. 心率序列
        hr = 60000 / nni
        axes[0, 1].plot(hr)
        axes[0, 1].set_title('心率序列')
        axes[0, 1].set_xlabel('样本')
        axes[0, 1].set_ylabel('心率 (bpm)')
        
        # 3. Poincaré图
        axes[1, 0].scatter(nni[:-1], nni[1:], s=10, alpha=0.5)
        axes[1, 0].set_title('Poincaré图')
        axes[1, 0].set_xlabel('NNI(n) (ms)')
        axes[1, 0].set_ylabel('NNI(n+1) (ms)')
        
        # 4. 结果表格
        axes[1, 1].axis('tight')
        axes[1, 1].axis('off')
        
        # 准备表格数据
        table_data = []
        for key, value in results.items():
            if isinstance(value, float):
                table_data.append([key, f"{value:.2f}"])
            else:
                table_data.append([key, str(value)])
        
        table = axes[1, 1].table(
            cellText=table_data,
            colLabels=['参数', '值'],
            cellLoc='center',
            loc='center'
        )
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1, 1.5)
        
        plt.tight_layout()
        plt.show()
    
    def get_supported_features(self):
        """获取支持的特征列表"""
        return self.supported_features
    
    def get_info(self):
        """获取模块信息"""
        return {
            "name": self.name,
            "version": self.version,
            "supported_features": self.supported_features,
            "description": "短时间心率变异性分析智能体节点"
        }

# 便捷函数
def analyze_hrv(nni=None, signal=None, rpeaks=None, sampling_rate=1000, show=False):
    """
    便捷函数：分析心率数据
    
    参数:
        nni: list或numpy数组，NNI序列 (毫秒单位)
        signal: list或numpy数组，原始ECG信号
        rpeaks: list或numpy数组，R波峰位置
        sampling_rate: float，ECG采样率 (Hz)
        show: bool，是否显示分析结果
        
    返回:
        dict: HRV特征参数
    """
    analyzer = HRVAgentNode()
    return analyzer.analyze(nni, signal, rpeaks, sampling_rate, show)

# 示例用法
if __name__ == "__main__":
    # 生成示例NNI数据 (1分钟，约75bpm)
    nni = np.random.normal(800, 50, 75)  # 75个样本，约1分钟
    
    # 分析
    results = analyze_hrv(nni=nni, show=True)
    
    print("分析结果:")
    for key, value in results.items():
        if isinstance(value, float):
            print(f"{key}: {value:.2f}")
        else:
            print(f"{key}: {value}")
