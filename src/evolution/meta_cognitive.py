"""
meta_cognitive.py - 元认知控制器
实现系统的自我认知、自我评估和自我调节能力
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from abc import ABC, abstractmethod
import json
import numpy as np
from collections import defaultdict, deque
import asyncio


class MetaCognitiveState(Enum):
    """元认知状态"""
    MONITORING = auto()      # 监控状态
    ANALYZING = auto()       # 分析状态
    PLANNING = auto()        # 规划状态
    EXECUTING = auto()       # 执行状态
    ADJUSTING = auto()       # 调整状态
    REFLECTING = auto()      # 反思状态


class LearningGoal(Enum):
    """学习目标类型"""
    PERFORMANCE = auto()     # 性能提升
    EFFICIENCY = auto()      # 效率提升
    ACCURACY = auto()        # 准确度提升
    ROBUSTNESS = auto()      # 鲁棒性提升
    GENERALIZATION = auto()  # 泛化能力提升
    CREATIVITY = auto()      # 创造力提升


@dataclass
class SelfAssessment:
    """自我评估结果"""
    timestamp: str
    component: str
    metrics: Dict[str, float]
    strengths: List[str]
    weaknesses: List[str]
    suggestions: List[str]
    confidence: float
    overall_score: float
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class MetaCognitiveConfig:
    """元认知配置"""
    monitoring_interval: int = 60  # 监控间隔(秒)
    assessment_threshold: float = 0.7  # 评估阈值
    memory_window: int = 100  # 记忆窗口大小
    learning_rate: float = 0.1  # 学习率
    exploration_rate: float = 0.3  # 探索率
    max_reflection_depth: int = 5  # 最大反思深度
    enable_self_modification: bool = True  # 启用自我修改
    safety_constraints: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetaCognitiveController(ABC):
    """元认知控制器基类"""
    
    @abstractmethod
    async def monitor(self) -> Dict[str, Any]:
        """监控系统状态"""
        pass
    
    @abstractmethod
    async def assess(self) -> SelfAssessment:
        """自我评估"""
        pass
    
    @abstractmethod
    async def reflect(self, depth: int = 3) -> Dict[str, Any]:
        """深度反思"""
        pass
    
    @abstractmethod
    async def adjust(self, adjustments: Dict[str, Any]) -> bool:
        """调整系统参数"""
        pass


class AutoMetaCognitiveController(MetaCognitiveController):
    """
    自动元认知控制器
    实现自主的自我认知和自我调节
    """
    
    def __init__(self, 
                 system_name: str = "AutoNewsAnalyzer",
                 config: Optional[MetaCognitiveConfig] = None):
        """
        初始化元认知控制器
        
        Args:
            system_name: 系统名称
            config: 配置
        """
        self.system_name = system_name
        self.config = config or MetaCognitiveConfig()
        self.logger = logging.getLogger(f"MetaCognitive.{system_name}")
        
        # 状态管理
        self.current_state = MetaCognitiveState.MONITORING
        self.state_history = deque(maxlen=self.config.memory_window)
        self.performance_history = deque(maxlen=self.config.memory_window)
        self.error_history = deque(maxlen=self.config.memory_window)
        
        # 自我模型
        self.self_model = {
            "capabilities": defaultdict(float),
            "limitations": defaultdict(float),
            "preferences": defaultdict(float),
            "knowledge": defaultdict(list)
        }
        
        # 目标系统
        self.learning_goals = {
            LearningGoal.PERFORMANCE: 0.8,
            LearningGoal.EFFICIENCY: 0.7,
            LearningGoal.ACCURACY: 0.9,
            LearningGoal.ROBUSTNESS: 0.6,
            LearningGoal.GENERALIZATION: 0.5
        }
        
        # 监控数据
        self.metrics = {
            "performance": [],
            "efficiency": [],
            "accuracy": [],
            "stability": [],
            "adaptability": []
        }
        
        # 真实性能指标提供者（由 EvolutionManager 注入）
        # 为空时退化为历史均值；历史也为空时返回中性值，绝不使用随机数
        self.metrics_provider: Optional[Callable[[], Dict[str, float]]] = None
        # 长期效果洞察提供者（由 EvolutionManager 注入）
        self.insight_provider: Optional[Callable[[], List[str]]] = None
        
        # 初始化
        self._initialize_self_model()
        self.logger.info(f"元认知控制器初始化完成: {system_name}")
    
    def _initialize_self_model(self):
        """初始化自我模型"""
        # 基础能力评估
        self.self_model["capabilities"]["knowledge_extraction"] = 0.7
        self.self_model["capabilities"]["pattern_recognition"] = 0.6
        self.self_model["capabilities"]["decision_making"] = 0.5
        self.self_model["capabilities"]["learning"] = 0.8
        
        # 已知限制
        self.self_model["limitations"]["computational_resources"] = 0.3
        self.self_model["limitations"]["knowledge_breadth"] = 0.4
        self.self_model["limitations"]["real_time_processing"] = 0.5
        
        # 学习偏好
        self.self_model["preferences"]["exploratory_learning"] = 0.7
        self.self_model["preferences"]["structured_learning"] = 0.3
        self.self_model["preferences"]["collaborative_learning"] = 0.5
    
    async def monitor(self) -> Dict[str, Any]:
        """
        监控系统状态
        
        Returns:
            监控数据字典
        """
        self.current_state = MetaCognitiveState.MONITORING
        self.state_history.append({
            "timestamp": datetime.now().isoformat(),
            "state": self.current_state.name,
            "duration": self.config.monitoring_interval
        })
        
        try:
            monitoring_data = {
                "timestamp": datetime.now().isoformat(),
                "system_metrics": await self._collect_system_metrics(),
                "performance_metrics": await self._collect_performance_metrics(),
                "resource_metrics": await self._collect_resource_metrics(),
                "knowledge_metrics": await self._collect_knowledge_metrics(),
                "anomalies": await self._detect_anomalies()
            }
            
            # 更新历史记录
            self.performance_history.append(monitoring_data)
            
            self.logger.debug(f"监控完成: {len(monitoring_data)} 项指标")
            return monitoring_data
            
        except Exception as e:
            self.logger.error(f"监控失败: {e}")
            self.error_history.append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "context": "monitoring"
            })
            return {"error": str(e)}
    
    async def _collect_system_metrics(self) -> Dict[str, float]:
        """收集系统指标"""
        import psutil
        import platform
        
        return {
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent,
            "process_count": len(psutil.pids()),
            "system_uptime": psutil.boot_time(),
            "python_version": platform.python_version()
        }
    
    async def _collect_performance_metrics(self) -> Dict[str, float]:
        """收集性能指标

        数据来源优先级：
        1. 外部注入的 metrics_provider（真实运行指标）
        2. 历史监控记录中性能指标的均值
        3. 中性默认值（无数据时）
        此前这里直接返回 random.uniform() 生成的随机数，导致元认知评估没有实际意义。
        """
        keys = ("processing_speed", "accuracy_rate", "error_rate",
                "learning_rate", "adaptation_speed")

        if self.metrics_provider is not None:
            try:
                provided = self.metrics_provider() or {}
                numeric = {
                    k: float(v) for k, v in provided.items()
                    if isinstance(v, (int, float)) and not isinstance(v, bool)
                }
                if numeric:
                    return numeric
            except Exception as e:
                self.logger.warning(f"读取外部性能指标失败: {e}")

        recent = [
            entry.get("performance_metrics", {})
            for entry in list(self.performance_history)[-5:]
            if isinstance(entry, dict)
        ]
        recent = [m for m in recent if m]
        if recent:
            averaged = {}
            for key in keys:
                values = [float(m[key]) for m in recent if key in m]
                averaged[key] = round(sum(values) / len(values), 4) if values else 0.0
            averaged["learning_rate"] = self.config.learning_rate
            return averaged

        return {
            "processing_speed": 0.0,
            "accuracy_rate": 0.0,
            "error_rate": 0.0,
            "learning_rate": self.config.learning_rate,
            "adaptation_speed": 0.0,
        }

    def set_metrics_provider(self, provider: Optional[Callable[[], Dict[str, float]]]) -> None:
        """注入真实性能指标来源（由进化管理器调用）"""
        self.metrics_provider = provider

    def set_insight_provider(self, provider: Optional[Callable[[], List[str]]]) -> None:
        """注入数据驱动的洞察来源（由进化管理器调用）"""
        self.insight_provider = provider
    
    async def _collect_resource_metrics(self) -> Dict[str, Any]:
        """收集资源指标"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        
        return {
            "thread_count": process.num_threads(),
            "open_files": len(process.open_files()),
            "connections": len(process.connections()),
            "memory_info": dict(process.memory_info()._asdict()),
            "cpu_times": dict(process.cpu_times()._asdict())
        }
    
    async def _collect_knowledge_metrics(self) -> Dict[str, Any]:
        """收集知识指标"""
        # 这里应该从知识管理模块获取数据
        # 暂时返回模拟数据
        return {
            "knowledge_base_size": 1500,
            "entity_count": 500,
            "relation_count": 1200,
            "learning_progress": 0.65,
            "knowledge_growth_rate": 0.1
        }
    
    async def _detect_anomalies(self) -> List[Dict[str, Any]]:
        """检测异常"""
        anomalies = []
        
        # 检查性能下降
        if len(self.performance_history) >= 5:
            recent_performance = [p.get("performance_metrics", {}).get("accuracy_rate", 0.8) 
                                for p in list(self.performance_history)[-5:]]
            if len(recent_performance) >= 3:
                trend = np.polyfit(range(len(recent_performance)), recent_performance, 1)[0]
                if trend < -0.1:  # 性能下降趋势
                    anomalies.append({
                        "type": "performance_decline",
                        "severity": "medium",
                        "description": f"检测到性能下降趋势: {trend:.3f}",
                        "suggestion": "检查最近的学习策略和数据处理流程"
                    })
        
        # 检查资源使用
        system_metrics = await self._collect_system_metrics()
        if system_metrics.get("memory_usage", 0) > 80:
            anomalies.append({
                "type": "high_memory_usage",
                "severity": "high",
                "description": f"内存使用率过高: {system_metrics['memory_usage']}%",
                "suggestion": "优化内存使用或增加系统资源"
            })
        
        return anomalies
    
    async def assess(self) -> SelfAssessment:
        """
        自我评估
        
        Returns:
            自我评估结果
        """
        self.current_state = MetaCognitiveState.ANALYZING
        
        try:
            # 收集各项指标
            monitoring_data = await self.monitor()
            performance_data = monitoring_data.get("performance_metrics", {})
            system_data = monitoring_data.get("system_metrics", {})
            
            # 计算综合得分
            performance_score = performance_data.get("accuracy_rate", 0.7) * 0.4
            efficiency_score = (1.0 - performance_data.get("error_rate", 0.1)) * 0.3
            stability_score = (100 - system_data.get("cpu_usage", 50)) / 100 * 0.2
            adaptability_score = performance_data.get("adaptation_speed", 0.5) * 0.1
            
            overall_score = performance_score + efficiency_score + stability_score + adaptability_score
            
            # 识别优缺点
            strengths = []
            weaknesses = []
            suggestions = []
            
            if performance_score > 0.8:
                strengths.append("高性能表现")
            else:
                weaknesses.append("性能有待提升")
                suggestions.append("优化算法参数和数据处理流程")
            
            if efficiency_score > 0.7:
                strengths.append("高效率运行")
            else:
                weaknesses.append("错误率偏高")
                suggestions.append("加强数据验证和错误处理机制")
            
            # 更新自我模型
            self._update_self_model(performance_data)
            
            assessment = SelfAssessment(
                timestamp=datetime.now().isoformat(),
                component=self.system_name,
                metrics=performance_data,
                strengths=strengths,
                weaknesses=weaknesses,
                suggestions=suggestions,
                confidence=min(overall_score * 1.2, 1.0),
                overall_score=overall_score
            )
            
            self.logger.info(f"自我评估完成: 综合得分 {overall_score:.3f}")
            return assessment
            
        except Exception as e:
            self.logger.error(f"自我评估失败: {e}")
            return SelfAssessment(
                timestamp=datetime.now().isoformat(),
                component=self.system_name,
                metrics={},
                strengths=[],
                weaknesses=["评估过程出错"],
                suggestions=["检查系统状态和监控功能"],
                confidence=0.1,
                overall_score=0.1
            )
    
    def _update_self_model(self, performance_data: Dict[str, float]):
        """更新自我模型"""
        # 根据性能数据更新能力评估
        accuracy = performance_data.get("accuracy_rate", 0.7)
        efficiency = 1.0 - performance_data.get("error_rate", 0.1)
        
        # 平滑更新
        alpha = 0.1
        self.self_model["capabilities"]["knowledge_extraction"] = (
            (1 - alpha) * self.self_model["capabilities"]["knowledge_extraction"] + 
            alpha * accuracy
        )
        
        self.self_model["capabilities"]["decision_making"] = (
            (1 - alpha) * self.self_model["capabilities"]["decision_making"] + 
            alpha * efficiency
        )
    
    async def reflect(self, depth: int = 3) -> Dict[str, Any]:
        """
        深度反思
        
        Args:
            depth: 反思深度
            
        Returns:
            反思结果
        """
        self.current_state = MetaCognitiveState.REFLECTING
        
        if depth > self.config.max_reflection_depth:
            depth = self.config.max_reflection_depth
        
        reflection_results = {
            "timestamp": datetime.now().isoformat(),
            "depth": depth,
            "insights": [],
            "lessons_learned": [],
            "future_improvements": [],
            "metacognitive_insights": []
        }
        
        try:
            # 第一层反思：性能分析
            assessment = await self.assess()
            reflection_results["insights"].append({
                "level": 1,
                "type": "performance_analysis",
                "content": f"当前系统表现: {assessment.overall_score:.3f}",
                "details": assessment.metrics
            })
            
            # 第二层反思：原因分析
            if depth >= 2:
                causes = await self._analyze_performance_causes(assessment)
                reflection_results["insights"].append({
                    "level": 2,
                    "type": "cause_analysis",
                    "content": "性能原因分析",
                    "details": causes
                })
            
            # 第三层反思：策略反思
            if depth >= 3:
                strategies = await self._reflect_on_strategies()
                reflection_results["insights"].append({
                    "level": 3,
                    "type": "strategy_reflection",
                    "content": "学习策略反思",
                    "details": strategies
                })
            
            # 提取经验教训
            reflection_results["lessons_learned"] = self._extract_lessons()
            
            # 生成改进建议
            reflection_results["future_improvements"] = self._generate_improvements()
            
            # 元认知洞察
            reflection_results["metacognitive_insights"] = await self._gain_metacognitive_insights()
            
            self.logger.info(f"深度反思完成 (深度: {depth})")
            return reflection_results
            
        except Exception as e:
            self.logger.error(f"反思过程失败: {e}")
            return {
                "error": str(e),
                "depth": depth,
                "insights": []
            }
    
    async def _analyze_performance_causes(self, assessment: SelfAssessment) -> Dict[str, Any]:
        """分析性能原因"""
        causes = {
            "internal_factors": [],
            "external_factors": [],
            "systemic_factors": []
        }
        
        # 内部因素
        if "性能有待提升" in assessment.weaknesses:
            causes["internal_factors"].append({
                "factor": "算法效率",
                "description": "当前算法在处理复杂模式时效率不高",
                "evidence": f"准确率: {assessment.metrics.get('accuracy_rate', 0):.3f}"
            })
        
        # 外部因素
        system_metrics = await self._collect_system_metrics()
        if system_metrics.get("cpu_usage", 0) > 70:
            causes["external_factors"].append({
                "factor": "计算资源",
                "description": "CPU使用率较高，可能影响处理速度",
                "evidence": f"CPU使用率: {system_metrics['cpu_usage']}%"
            })
        
        return causes
    
    async def _reflect_on_strategies(self) -> Dict[str, Any]:
        """反思学习策略"""
        strategies = {
            "current_strategies": [],
            "effectiveness": {},
            "potential_improvements": []
        }
        
        # 当前策略
        strategies["current_strategies"] = [
            {"name": "监督学习", "weight": 0.4},
            {"name": "强化学习", "weight": 0.3},
            {"name": "迁移学习", "weight": 0.2},
            {"name": "元学习", "weight": 0.1}
        ]
        
        # 策略有效性（基于历史数据）
        if self.performance_history:
            recent_scores = [
                p.get("performance_metrics", {}).get("accuracy_rate", 0.7) 
                for p in list(self.performance_history)[-10:]
            ]
            if recent_scores:
                avg_score = sum(recent_scores) / len(recent_scores)
                strategies["effectiveness"] = {
                    "average_performance": avg_score,
                    "trend": "stable" if len(recent_scores) < 2 or 
                            abs(recent_scores[-1] - recent_scores[0]) < 0.05 else "changing",
                    "consistency": np.std(recent_scores) if len(recent_scores) > 1 else 0
                }
        
        # 改进建议
        strategies["potential_improvements"] = [
            "增加探索性学习比例",
            "引入对抗学习提升鲁棒性",
            "优化知识迁移策略"
        ]
        
        return strategies
    
    def _extract_lessons(self) -> List[str]:
        """提取经验教训"""
        lessons = []
        
        if self.error_history:
            recent_errors = list(self.error_history)[-5:]
            error_types = defaultdict(int)
            for error in recent_errors:
                error_type = error.get("context", "unknown")
                error_types[error_type] += 1
            
            for error_type, count in error_types.items():
                if count >= 2:
                    lessons.append(f"频繁出现 {error_type} 错误，需要加强相关模块的稳定性")
        
        if self.performance_history:
            recent_performance = [p.get("performance_metrics", {}).get("accuracy_rate", 0.7) 
                                for p in list(self.performance_history)[-10:]]
            if len(recent_performance) >= 5:
                variance = np.var(recent_performance)
                if variance > 0.01:
                    lessons.append("系统性能波动较大，需要提升稳定性")
        
        return lessons if lessons else ["系统运行平稳，无重大经验教训"]
    
    def _generate_improvements(self) -> List[Dict[str, str]]:
        """生成改进建议"""
        improvements = []
        
        # 基于自我模型
        for capability, score in self.self_model["capabilities"].items():
            if score < 0.6:
                improvements.append({
                    "area": "capability",
                    "target": capability,
                    "action": f"提升{capability}能力",
                    "priority": "high" if score < 0.5 else "medium"
                })
        
        # 基于目标系统
        for goal, target in self.learning_goals.items():
            current_score = self._estimate_goal_progress(goal)
            if current_score < target * 0.8:
                improvements.append({
                    "area": "goal",
                    "target": goal.name,
                    "action": f"加强{goal.name.lower()}相关学习",
                    "priority": "high"
                })
        
        return improvements if improvements else [
            {
                "area": "maintenance",
                "target": "system",
                "action": "持续监控和优化",
                "priority": "low"
            }
        ]
    
    def _estimate_goal_progress(self, goal: LearningGoal) -> float:
        """估计目标进展"""
        # 简化的估计逻辑
        goal_mapping = {
            LearningGoal.PERFORMANCE: self.self_model["capabilities"].get("knowledge_extraction", 0.7),
            LearningGoal.ACCURACY: 0.8,  # 从监控数据获取更准确
            LearningGoal.EFFICIENCY: 0.7,
            LearningGoal.ROBUSTNESS: 0.6
        }
        return goal_mapping.get(goal, 0.5)
    
    async def _gain_metacognitive_insights(self) -> List[str]:
        """获取元认知洞察

        优先使用长期效果评估器提供的、可由数据集复算的洞察；
        没有数据源时才退回规则启发式。
        """
        if self.insight_provider is not None:
            try:
                provided = self.insight_provider() or []
                if provided:
                    return list(provided)
            except Exception as e:
                self.logger.warning(f"读取数据驱动洞察失败: {e}")

        insights = []
        
        # 洞察1：学习效率
        learning_rate = self.config.learning_rate
        if learning_rate < 0.05:
            insights.append("学习率过低，可能需要增加探索性学习")
        elif learning_rate > 0.3:
            insights.append("学习率过高，可能导致不稳定")
        
        # 洞察2：知识增长
        knowledge_metrics = await self._collect_knowledge_metrics()
        growth_rate = knowledge_metrics.get("knowledge_growth_rate", 0)
        if growth_rate < 0.05:
            insights.append("知识增长速度缓慢，可能需要扩展学习领域")
        
        # 洞察3：自我认知精度
        recent_assessments = list(self.state_history)[-5:]
        assessment_count = sum(1 for a in recent_assessments 
                             if a.get("state") == MetaCognitiveState.ANALYZING.name)
        if assessment_count < 2:
            insights.append("自我评估频率不足，可能影响自我认知精度")
        
        return insights if insights else ["系统元认知运行正常，无特殊洞察"]
    
    async def adjust(self, adjustments: Dict[str, Any]) -> bool:
        """
        调整系统参数
        
        Args:
            adjustments: 调整参数
            
        Returns:
            是否成功
        """
        self.current_state = MetaCognitiveState.ADJUSTING
        
        try:
            applied_adjustments = []
            
            # 调整学习率
            if "learning_rate" in adjustments:
                new_rate = adjustments["learning_rate"]
                if 0.01 <= new_rate <= 0.5:
                    self.config.learning_rate = new_rate
                    applied_adjustments.append(f"学习率调整为 {new_rate}")
            
            # 调整探索率
            if "exploration_rate" in adjustments:
                new_rate = adjustments["exploration_rate"]
                if 0.1 <= new_rate <= 0.5:
                    self.config.exploration_rate = new_rate
                    applied_adjustments.append(f"探索率调整为 {new_rate}")
            
            # 调整监控间隔
            if "monitoring_interval" in adjustments:
                new_interval = adjustments["monitoring_interval"]
                if 10 <= new_interval <= 600:
                    self.config.monitoring_interval = new_interval
                    applied_adjustments.append(f"监控间隔调整为 {new_interval} 秒")
            
            # 调整学习目标权重
            if "learning_goals" in adjustments:
                for goal_name, weight in adjustments["learning_goals"].items():
                    try:
                        goal = LearningGoal[goal_name.upper()]
                        if 0 <= weight <= 1:
                            self.learning_goals[goal] = weight
                            applied_adjustments.append(f"学习目标 {goal_name} 权重调整为 {weight}")
                    except KeyError:
                        self.logger.warning(f"未知的学习目标: {goal_name}")
            
            # 记录调整
            if applied_adjustments:
                adjustment_record = {
                    "timestamp": datetime.now().isoformat(),
                    "adjustments": adjustments,
                    "applied": applied_adjustments,
                    "result": "success"
                }
                self.state_history.append(adjustment_record)
                
                self.logger.info(f"成功应用 {len(applied_adjustments)} 项调整")
                return True
            else:
                self.logger.warning("没有有效的调整参数")
                return False
                
        except Exception as e:
            self.logger.error(f"调整失败: {e}")
            self.error_history.append({
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "context": "adjustment",
                "adjustments": adjustments
            })
            return False
    
    async def evolve_strategy(self) -> Dict[str, Any]:
        """
        进化学习策略
        
        Returns:
            新策略配置
        """
        self.current_state = MetaCognitiveState.PLANNING
        
        try:
            # 基于当前表现调整策略
            assessment = await self.assess()
            current_score = assessment.overall_score
            
            # 分析策略效果
            strategy_effectiveness = await self._analyze_strategy_effectiveness()
            
            # 生成新策略
            new_strategy = {
                "timestamp": datetime.now().isoformat(),
                "based_on": {
                    "current_score": current_score,
                    "assessment": assessment.to_dict(),
                    "strategy_analysis": strategy_effectiveness
                },
                "new_parameters": {},
                "rationale": []
            }
            
            # 根据表现调整学习率
            if current_score < 0.6:
                # 表现不佳，增加学习率
                new_learning_rate = min(self.config.learning_rate * 1.3, 0.3)
                new_strategy["new_parameters"]["learning_rate"] = new_learning_rate
                new_strategy["rationale"].append(
                    f"当前得分 {current_score:.3f} 较低，提高学习率至 {new_learning_rate}"
                )
            elif current_score > 0.9:
                # 表现很好，降低学习率避免过拟合
                new_learning_rate = max(self.config.learning_rate * 0.8, 0.01)
                new_strategy["new_parameters"]["learning_rate"] = new_learning_rate
                new_strategy["rationale"].append(
                    f"当前得分 {current_score:.3f} 较高，降低学习率至 {new_learning_rate} 避免过拟合"
                )
            
            # 调整探索率
            error_rate = assessment.metrics.get("error_rate", 0.1)
            if error_rate > 0.15:
                # 错误率高，降低探索率
                new_exploration_rate = max(self.config.exploration_rate * 0.7, 0.1)
                new_strategy["new_parameters"]["exploration_rate"] = new_exploration_rate
                new_strategy["rationale"].append(
                    f"错误率 {error_rate:.3f} 较高，降低探索率至 {new_exploration_rate}"
                )
            elif error_rate < 0.05:
                # 错误率低，可以增加探索
                new_exploration_rate = min(self.config.exploration_rate * 1.2, 0.5)
                new_strategy["new_parameters"]["exploration_rate"] = new_exploration_rate
                new_strategy["rationale"].append(
                    f"错误率 {error_rate:.3f} 较低，增加探索率至 {new_exploration_rate}"
                )
            
            # 应用新策略
            if new_strategy["new_parameters"]:
                success = await self.adjust(new_strategy["new_parameters"])
                new_strategy["applied"] = success
                
                if success:
                    self.logger.info(f"策略进化完成: {len(new_strategy['new_parameters'])} 项调整")
                else:
                    self.logger.warning("策略进化但未成功应用")
            
            return new_strategy
            
        except Exception as e:
            self.logger.error(f"策略进化失败: {e}")
            return {
                "error": str(e),
                "evolved": False
            }
    
    async def _analyze_strategy_effectiveness(self) -> Dict[str, Any]:
        """分析策略有效性"""
        if len(self.performance_history) < 5:
            return {"insufficient_data": True}
        
        recent_performance = list(self.performance_history)[-10:]
        scores = [p.get("performance_metrics", {}).get("accuracy_rate", 0.7) 
                 for p in recent_performance]
        
        if len(scores) >= 3:
            # 计算趋势
            x = range(len(scores))
            slope, intercept = np.polyfit(x, scores, 1)
            trend = "improving" if slope > 0.01 else "declining" if slope < -0.01 else "stable"
            
            # 计算波动性
            volatility = np.std(scores)
            
            return {
                "trend": trend,
                "slope": float(slope),
                "volatility": float(volatility),
                "average_score": float(np.mean(scores)),
                "data_points": len(scores)
            }
        
        return {"insufficient_data": True}
    
    def get_status_report(self) -> Dict[str, Any]:
        """
        获取状态报告
        
        Returns:
            状态报告
        """
        return {
            "system_name": self.system_name,
            "current_state": self.current_state.name,
            "config": self.config.to_dict(),
            "self_model_summary": {
                "capabilities": dict(self.self_model["capabilities"]),
                "limitations": dict(self.self_model["limitations"]),
                "learning_goals": {k.name: v for k, v in self.learning_goals.items()}
            },
            "statistics": {
                "state_history_count": len(self.state_history),
                "performance_history_count": len(self.performance_history),
                "error_history_count": len(self.error_history),
                "last_assessment_time": self.state_history[-1]["timestamp"] if self.state_history else None
            },
            "timestamp": datetime.now().isoformat()
        }
    
    def save_state(self, filepath: str) -> bool:
        """
        保存状态到文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否成功
        """
        try:
            state_data = {
                "config": self.config.to_dict(),
                "self_model": self.self_model,
                "learning_goals": {k.name: v for k, v in self.learning_goals.items()},
                "current_state": self.current_state.name,
                "state_history": list(self.state_history),
                "performance_history": list(self.performance_history),
                "error_history": list(self.error_history),
                "saved_at": datetime.now().isoformat()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"状态已保存到: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存状态失败: {e}")
            return False
    
    def load_state(self, filepath: str) -> bool:
        """
        从文件加载状态
        
        Args:
            filepath: 文件路径
            
        Returns:
            是否成功
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # 恢复配置
            self.config = MetaCognitiveConfig(**state_data["config"])
            
            # 恢复自我模型
            self.self_model = state_data["self_model"]
            
            # 恢复学习目标
            self.learning_goals = {
                LearningGoal[k.upper()]: v 
                for k, v in state_data["learning_goals"].items()
            }
            
            # 恢复状态
            self.current_state = MetaCognitiveState[state_data["current_state"]]
            
            # 恢复历史数据
            self.state_history = deque(state_data["state_history"], 
                                    maxlen=self.config.memory_window)
            self.performance_history = deque(state_data["performance_history"],
                                        maxlen=self.config.memory_window)
            self.error_history = deque(state_data["error_history"],
                                    maxlen=self.config.memory_window)
            
            self.logger.info(f"状态已从 {filepath} 加载")
            return True
            
        except Exception as e:
            self.logger.error(f"加载状态失败: {e}")
            return False