"""
learning_planner.py - 学习规划器
规划系统的学习路径和进化方向
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from abc import ABC, abstractmethod
import json
import numpy as np
from collections import defaultdict, deque
import networkx as nx
from concurrent.futures import ThreadPoolExecutor


class LearningTaskType(Enum):
    """学习任务类型"""
    EXPLORATORY = auto()     # 探索性学习
    EXPLOITATIVE = auto()    # 利用性学习
    CONSOLIDATION = auto()   # 巩固学习
    TRANSFER = auto()        # 迁移学习
    META = auto()            # 元学习
    ADAPTIVE = auto()        # 适应性学习
    EVALUATION = auto()      # 评估学习


class LearningPriority(Enum):
    """学习优先级"""
    CRITICAL = auto()        # 关键
    HIGH = auto()            # 高
    MEDIUM = auto()          # 中
    LOW = auto()             # 低
    OPTIONAL = auto()        # 可选


class LearningStage(Enum):
    """学习阶段"""
    PLANNING = auto()        # 规划阶段
    EXECUTION = auto()       # 执行阶段
    EVALUATION = auto()      # 评估阶段
    ADJUSTMENT = auto()      # 调整阶段
    COMPLETED = auto()       # 完成阶段


@dataclass
class LearningObjective:
    """学习目标"""
    id: str
    description: str
    target_skill: str
    target_proficiency: float  # 0-1
    prerequisites: List[str]
    priority: LearningPriority
    estimated_duration: int  # 分钟
    dependencies: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LearningTask:
    """学习任务"""
    id: str
    objective_id: str
    task_type: LearningTaskType
    description: str
    instructions: List[str]
    resources: List[str]
    expected_outcomes: List[str]
    difficulty: float  # 0-1
    time_estimate: int  # 分钟
    stage: LearningStage = LearningStage.PLANNING
    progress: float = 0.0
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    results: Dict[str, Any] = field(default_factory=dict)
    feedback: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LearningPlan:
    """学习计划"""
    id: str
    version: str
    objectives: List[LearningObjective]
    tasks: List[LearningTask]
    schedule: Dict[str, List[str]]  # 时间 -> 任务ID列表
    constraints: Dict[str, Any]
    estimated_completion: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "objectives": [obj.to_dict() for obj in self.objectives],
            "tasks": [task.to_dict() for task in self.tasks],
            "schedule": self.schedule,
            "constraints": self.constraints,
            "estimated_completion": self.estimated_completion,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }


@dataclass
class LearningConfig:
    """学习配置"""
    max_concurrent_tasks: int = 3
    learning_rate: float = 0.1
    exploration_rate: float = 0.3
    retention_rate: float = 0.7
    transfer_learning_enabled: bool = True
    meta_learning_enabled: bool = True
    adaptive_learning_enabled: bool = True
    evaluation_interval: int = 60  # 分钟
    planning_horizon: int = 7  # 天
    min_task_duration: int = 10  # 分钟
    max_task_duration: int = 240  # 分钟
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class LearningPlanner(ABC):
    """学习规划器基类"""
    
    @abstractmethod
    async def analyze_learning_needs(self, assessment: Dict[str, Any]) -> List[LearningObjective]:
        """分析学习需求"""
        pass
    
    @abstractmethod
    async def create_learning_plan(self, objectives: List[LearningObjective]) -> LearningPlan:
        """创建学习计划"""
        pass
    
    @abstractmethod
    async def execute_learning_task(self, task: LearningTask) -> Dict[str, Any]:
        """执行学习任务"""
        pass
    
    @abstractmethod
    async def evaluate_learning_progress(self) -> Dict[str, Any]:
        """评估学习进展"""
        pass


class AutoLearningPlanner(LearningPlanner):
    """
    自动学习规划器
    实现智能的学习路径规划和执行管理
    """
    
    def __init__(self, 
                 system_name: str = "AutoNewsAnalyzer",
                 config: Optional[LearningConfig] = None):
        """
        初始化学习规划器
        
        Args:
            system_name: 系统名称
            config: 配置
        """
        self.system_name = system_name
        self.config = config or LearningConfig()
        self.logger = logging.getLogger(f"LearningPlanner.{system_name}")
        
        # 学习状态
        self.current_plan: Optional[LearningPlan] = None
        self.active_tasks: Dict[str, LearningTask] = {}
        self.completed_tasks: List[LearningTask] = []
        self.failed_tasks: List[LearningTask] = []
        
        # 学习历史
        self.learning_history: List[Dict[str, Any]] = []
        self.skill_proficiency: Dict[str, float] = defaultdict(float)
        self.knowledge_graph = nx.DiGraph()
        
        # 任务执行器
        self.executor = ThreadPoolExecutor(max_workers=self.config.max_concurrent_tasks)
        
        # 初始化技能库
        self._initialize_skills()
        
        self.logger.info(f"学习规划器初始化完成: {system_name}")
    
    def _initialize_skills(self):
        """初始化技能库"""
        # 基础技能
        base_skills = {
            "knowledge_extraction": 0.6,
            "pattern_recognition": 0.5,
            "decision_making": 0.4,
            "problem_solving": 0.5,
            "adaptation": 0.3,
            "creativity": 0.2
        }
        
        for skill, proficiency in base_skills.items():
            self.skill_proficiency[skill] = proficiency
        
        # 初始化知识图谱
        self.knowledge_graph.add_nodes_from(base_skills.keys())
        
        # 添加技能间的关系
        skill_relations = [
            ("knowledge_extraction", "pattern_recognition"),
            ("pattern_recognition", "decision_making"),
            ("decision_making", "problem_solving"),
            ("problem_solving", "adaptation"),
            ("adaptation", "creativity")
        ]
        
        self.knowledge_graph.add_edges_from(skill_relations)
    
    async def analyze_learning_needs(self, assessment: Dict[str, Any]) -> List[LearningObjective]:
        """
        分析学习需求
        
        Args:
            assessment: 系统评估结果
            
        Returns:
            学习目标列表
        """
        self.logger.info("开始分析学习需求")
        
        objectives = []
        
        # 从评估中提取性能缺口
        weaknesses = assessment.get("weaknesses", [])
        suggestions = assessment.get("suggestions", [])
        metrics = assessment.get("metrics", {})
        
        # 分析性能指标
        performance_gaps = self._identify_performance_gaps(metrics)
        
        # 根据弱点创建目标
        for weakness in weaknesses:
            objective = self._create_objective_from_weakness(weakness)
            if objective:
                objectives.append(objective)
        
        # 根据建议创建目标
        for suggestion in suggestions:
            objective = self._create_objective_from_suggestion(suggestion)
            if objective:
                objectives.append(objective)
        
        # 根据性能缺口创建目标
        for gap in performance_gaps:
            objective = self._create_objective_from_gap(gap)
            if objective:
                objectives.append(objective)
        
        # 添加元学习目标
        if self.config.meta_learning_enabled:
            meta_objective = self._create_meta_learning_objective()
            objectives.append(meta_objective)
        
        # 去除重复目标
        unique_objectives = []
        seen_ids = set()
        for obj in objectives:
            if obj.id not in seen_ids:
                seen_ids.add(obj.id)
                unique_objectives.append(obj)
        
        self.logger.info(f"分析完成: 创建了 {len(unique_objectives)} 个学习目标")
        return unique_objectives
    
    def _identify_performance_gaps(self, metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """识别性能缺口"""
        gaps = []
        
        # 定义性能阈值
        thresholds = {
            "accuracy_rate": 0.8,
            "processing_speed": 0.7,
            "error_rate": 0.1,
            "adaptation_speed": 0.6
        }
        
        for metric, value in metrics.items():
            if metric in thresholds:
                threshold = thresholds[metric]
                if metric == "error_rate":
                    # 错误率越低越好
                    if value > threshold:
                        gaps.append({
                            "metric": metric,
                            "current": value,
                            "target": threshold,
                            "gap": value - threshold
                        })
                else:
                    # 其他指标越高越好
                    if value < threshold:
                        gaps.append({
                            "metric": metric,
                            "current": value,
                            "target": threshold,
                            "gap": threshold - value
                        })
        
        return gaps
    
    def _create_objective_from_weakness(self, weakness: str) -> Optional[LearningObjective]:
        """根据弱点创建学习目标"""
        weakness_mapping = {
            "性能有待提升": {
                "skill": "knowledge_extraction",
                "target": 0.8,
                "priority": LearningPriority.HIGH
            },
            "错误率偏高": {
                "skill": "pattern_recognition",
                "target": 0.75,
                "priority": LearningPriority.CRITICAL
            },
            "稳定性不足": {
                "skill": "adaptation",
                "target": 0.7,
                "priority": LearningPriority.MEDIUM
            }
        }
        
        if weakness in weakness_mapping:
            mapping = weakness_mapping[weakness]
            objective_id = f"obj_{len(self.learning_history)}_{hash(weakness) % 1000}"
            
            return LearningObjective(
                id=objective_id,
                description=f"改善{weakness}",
                target_skill=mapping["skill"],
                target_proficiency=mapping["target"],
                prerequisites=self._get_skill_prerequisites(mapping["skill"]),
                priority=mapping["priority"],
                estimated_duration=120,
                metrics={"weakness": weakness}
            )
        
        return None
    
    def _get_skill_prerequisites(self, skill: str) -> List[str]:
        """获取技能的先决条件"""
        prerequisites = []
        
        # 在知识图谱中查找前置技能
        if skill in self.knowledge_graph:
            predecessors = list(self.knowledge_graph.predecessors(skill))
            prerequisites.extend(predecessors)
        
        return prerequisites
    
    def _create_objective_from_suggestion(self, suggestion: str) -> Optional[LearningObjective]:
        """根据建议创建学习目标"""
        suggestion_keywords = {
            "优化算法": "knowledge_extraction",
            "加强数据验证": "pattern_recognition",
            "提升稳定性": "adaptation",
            "增加探索": "creativity",
            "改进决策": "decision_making"
        }
        
        for keyword, skill in suggestion_keywords.items():
            if keyword in suggestion:
                objective_id = f"obj_sugg_{len(self.learning_history)}_{hash(suggestion) % 1000}"
                
                current_proficiency = self.skill_proficiency.get(skill, 0.5)
                target_proficiency = min(current_proficiency + 0.2, 0.9)
                
                return LearningObjective(
                    id=objective_id,
                    description=f"实现建议: {suggestion}",
                    target_skill=skill,
                    target_proficiency=target_proficiency,
                    prerequisites=self._get_skill_prerequisites(skill),
                    priority=LearningPriority.MEDIUM,
                    estimated_duration=90,
                    metrics={"suggestion": suggestion}
                )
        
        return None
    
    def _create_objective_from_gap(self, gap: Dict[str, Any]) -> Optional[LearningObjective]:
        """根据性能缺口创建学习目标"""
        gap_mapping = {
            "accuracy_rate": ("knowledge_extraction", 0.1),
            "processing_speed": ("problem_solving", 0.15),
            "error_rate": ("pattern_recognition", 0.2),
            "adaptation_speed": ("adaptation", 0.15)
        }
        
        metric = gap["metric"]
        if metric in gap_mapping:
            skill, improvement = gap_mapping[metric]
            
            current_proficiency = self.skill_proficiency.get(skill, 0.5)
            target_proficiency = min(current_proficiency + improvement, 0.9)
            
            objective_id = f"obj_gap_{metric}_{len(self.learning_history)}"
            
            return LearningObjective(
                id=objective_id,
                description=f"改善{metric} (当前: {gap['current']:.3f}, 目标: {gap['target']:.3f})",
                target_skill=skill,
                target_proficiency=target_proficiency,
                prerequisites=self._get_skill_prerequisites(skill),
                priority=LearningPriority.HIGH if gap["gap"] > 0.1 else LearningPriority.MEDIUM,
                estimated_duration=int(gap["gap"] * 200),  # 根据缺口大小估计时间
                metrics=gap
            )
        
        return None
    
    def _create_meta_learning_objective(self) -> LearningObjective:
        """创建元学习目标"""
        return LearningObjective(
            id=f"obj_meta_{len(self.learning_history)}",
            description="提升元学习能力，优化学习策略",
            target_skill="meta_learning",
            target_proficiency=0.7,
            prerequisites=["adaptation", "creativity"],
            priority=LearningPriority.MEDIUM,
            estimated_duration=180,
            metrics={"type": "meta_learning"}
        )
    
    async def create_learning_plan(self, objectives: List[LearningObjective]) -> LearningPlan:
        """
        创建学习计划
        
        Args:
            objectives: 学习目标列表
            
        Returns:
            学习计划
        """
        self.logger.info(f"开始创建学习计划: {len(objectives)} 个目标")
        
        # 对目标进行排序（按优先级和依赖关系）
        sorted_objectives = self._sort_objectives(objectives)
        
        # 为每个目标创建任务
        tasks = []
        for objective in sorted_objectives:
            objective_tasks = self._create_tasks_for_objective(objective)
            tasks.extend(objective_tasks)
        
        # 安排任务
        schedule = self._schedule_tasks(tasks)
        
        # 估计完成时间
        estimated_completion = self._estimate_completion_time(schedule)
        
        # 创建计划
        plan_id = f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        plan = LearningPlan(
            id=plan_id,
            version="1.0",
            objectives=sorted_objectives,
            tasks=tasks,
            schedule=schedule,
            constraints={
                "max_concurrent_tasks": self.config.max_concurrent_tasks,
                "max_daily_learning_time": 240,  # 4小时
                "min_break_interval": 30  # 30分钟
            },
            estimated_completion=estimated_completion
        )
        
        self.current_plan = plan
        self.logger.info(f"学习计划创建完成: {plan_id}")
        
        return plan
    
    def _sort_objectives(self, objectives: List[LearningObjective]) -> List[LearningObjective]:
        """对目标进行排序"""
        # 按优先级排序
        priority_order = {
            LearningPriority.CRITICAL: 0,
            LearningPriority.HIGH: 1,
            LearningPriority.MEDIUM: 2,
            LearningPriority.LOW: 3,
            LearningPriority.OPTIONAL: 4
        }
        
        # 考虑依赖关系
        sorted_objectives = []
        remaining = objectives.copy()
        added = set()
        
        while remaining:
            # 找到可以添加的目标（所有前置条件都已满足）
            for obj in remaining[:]:
                if all(prereq in added for prereq in obj.prerequisites):
                    sorted_objectives.append(obj)
                    added.add(obj.id)
                    remaining.remove(obj)
                    break
            else:
                # 如果没有目标满足条件，添加优先级最高的
                remaining.sort(key=lambda x: priority_order[x.priority])
                obj = remaining.pop(0)
                sorted_objectives.append(obj)
                added.add(obj.id)
        
        return sorted_objectives
    
    def _create_tasks_for_objective(self, objective: LearningObjective) -> List[LearningTask]:
        """为目标创建任务"""
        tasks = []
        
        # 根据目标类型创建不同任务
        task_types = self._determine_task_types(objective)
        
        for i, task_type in enumerate(task_types):
            task_id = f"task_{objective.id}_{i}"
            
            task = LearningTask(
                id=task_id,
                objective_id=objective.id,
                task_type=task_type,
                description=self._generate_task_description(objective, task_type, i),
                instructions=self._generate_task_instructions(objective, task_type),
                resources=self._generate_task_resources(objective, task_type),
                expected_outcomes=self._generate_expected_outcomes(objective, task_type),
                difficulty=objective.target_proficiency * 0.8,  # 难度基于目标精通度
                time_estimate=self._estimate_task_duration(objective, task_type)
            )
            
            tasks.append(task)
        
        return tasks
    
    def _determine_task_types(self, objective: LearningObjective) -> List[LearningTaskType]:
        """确定任务类型"""
        task_types = []
        
        # 根据技能类型和目标确定任务类型
        skill = objective.target_skill
        
        if skill in ["knowledge_extraction", "pattern_recognition"]:
            # 知识和模式识别：探索性学习为主
            task_types.extend([
                LearningTaskType.EXPLORATORY,
                LearningTaskType.CONSOLIDATION,
                LearningTaskType.EVALUATION
            ])
        
        elif skill in ["decision_making", "problem_solving"]:
            # 决策和问题解决：利用性学习为主
            task_types.extend([
                LearningTaskType.EXPLOITATIVE,
                LearningTaskType.ADAPTIVE,
                LearningTaskType.EVALUATION
            ])
        
        elif skill in ["adaptation", "creativity"]:
            # 适应和创造力：元学习和迁移学习
            task_types.extend([
                LearningTaskType.META,
                LearningTaskType.TRANSFER,
                LearningTaskType.EXPLORATORY
            ])
        
        else:
            # 默认任务类型
            task_types.extend([
                LearningTaskType.EXPLORATORY,
                LearningTaskType.CONSOLIDATION,
                LearningTaskType.EVALUATION
            ])
        
        return task_types
    
    def _generate_task_description(self, objective: LearningObjective, 
                                  task_type: LearningTaskType, 
                                  task_index: int) -> str:
        """生成任务描述"""
        descriptions = {
            LearningTaskType.EXPLORATORY: f"探索{objective.target_skill}的新方法和技巧",
            LearningTaskType.EXPLOITATIVE: f"优化和利用现有的{objective.target_skill}能力",
            LearningTaskType.CONSOLIDATION: f"巩固和加深对{objective.target_skill}的理解",
            LearningTaskType.TRANSFER: f"将{objective.target_skill}迁移到新领域",
            LearningTaskType.META: f"反思和改进{objective.target_skill}的学习策略",
            LearningTaskType.ADAPTIVE: f"适应性地调整{objective.target_skill}的应用"
        }
        
        return descriptions.get(task_type, f"提升{objective.target_skill}能力")
    
    def _generate_task_instructions(self, objective: LearningObjective, 
                                   task_type: LearningTaskType) -> List[str]:
        """生成任务指导"""
        base_instructions = [
            "仔细阅读相关材料",
            "实践并应用所学内容",
            "记录学习过程和收获",
            "反思学习效果",
            "根据反馈进行调整"
        ]
        
        # 根据任务类型添加特定指导
        specific_instructions = {
            LearningTaskType.EXPLORATORY: [
                "尝试至少三种不同的方法",
                "记录每种方法的优缺点",
                "对比分析不同方法的效果"
            ],
            LearningTaskType.EXPLOITATIVE: [
                "分析当前最佳实践",
                "寻找优化空间",
                "测试优化效果"
            ],
            LearningTaskType.TRANSFER: [
                "识别源领域和目标领域的相似性",
                "调整方法以适应新领域",
                "验证迁移效果"
            ]
        }
        
        instructions = base_instructions.copy()
        if task_type in specific_instructions:
            instructions.extend(specific_instructions[task_type])
        
        return instructions
    
    def _generate_task_resources(self, objective: LearningObjective, 
                                task_type: LearningTaskType) -> List[str]:
        """生成任务资源"""
        resources = []
        
        # 通用资源
        resources.append("系统文档和API参考")
        resources.append("相关技术论文和文章")
        resources.append("代码示例和最佳实践")
        
        # 特定技能资源
        skill_resources = {
            "knowledge_extraction": [
                "命名实体识别算法",
                "关系抽取技术",
                "知识图谱构建方法"
            ],
            "pattern_recognition": [
                "机器学习模型",
                "特征工程方法",
                "模式匹配算法"
            ],
            "decision_making": [
                "决策理论",
                "风险评估方法",
                "优化算法"
            ]
        }
        
        skill = objective.target_skill
        if skill in skill_resources:
            resources.extend(skill_resources[skill])
        
        return resources
    
    def _generate_expected_outcomes(self, objective: LearningObjective, 
                                   task_type: LearningTaskType) -> List[str]:
        """生成预期成果"""
        outcomes = []
        
        # 通用成果
        outcomes.append(f"提升{objective.target_skill}的理解")
        outcomes.append("掌握相关技术和方法")
        outcomes.append("能够应用所学解决问题")
        
        # 特定成果
        if task_type == LearningTaskType.EXPLORATORY:
            outcomes.append("发现新的方法或技巧")
            outcomes.append("建立知识连接")
        
        elif task_type == LearningTaskType.TRANSFER:
            outcomes.append("成功迁移技能到新领域")
            outcomes.append("建立跨领域知识连接")
        
        return outcomes
    
    def _estimate_task_duration(self, objective: LearningObjective, 
                               task_type: LearningTaskType) -> int:
        """估计任务持续时间"""
        base_duration = 30  # 分钟
        
        # 根据目标精通度调整
        proficiency_factor = objective.target_proficiency * 100
        
        # 根据任务类型调整
        type_factors = {
            LearningTaskType.EXPLORATORY: 1.5,
            LearningTaskType.EXPLOITATIVE: 1.0,
            LearningTaskType.CONSOLIDATION: 0.8,
            LearningTaskType.TRANSFER: 2.0,
            LearningTaskType.META: 1.2,
            LearningTaskType.ADAPTIVE: 1.3
        }
        
        factor = type_factors.get(task_type, 1.0)
        duration = int(base_duration + proficiency_factor * factor)
        
        # 限制在配置范围内
        duration = max(self.config.min_task_duration, 
                      min(duration, self.config.max_task_duration))
        
        return duration
    
    def _schedule_tasks(self, tasks: List[LearningTask]) -> Dict[str, List[str]]:
        """安排任务"""
        schedule = defaultdict(list)
        
        # 按优先级排序任务
        task_priority = {}
        for task in tasks:
            # 找到对应的目标优先级
            for objective in (self.current_plan.objectives if self.current_plan else []):
                if objective.id == task.objective_id:
                    priority_value = {
                        LearningPriority.CRITICAL: 0,
                        LearningPriority.HIGH: 1,
                        LearningPriority.MEDIUM: 2,
                        LearningPriority.LOW: 3,
                        LearningPriority.OPTIONAL: 4
                    }.get(objective.priority, 2)
                    task_priority[task.id] = priority_value
                    break
        
        sorted_tasks = sorted(tasks, key=lambda t: task_priority.get(t.id, 2))
        
        # 分配时间槽
        current_time = datetime.now()
        time_slots = []
        
        # 生成未来几天的学习时间槽
        for day in range(self.config.planning_horizon):
            day_date = current_time + timedelta(days=day)
            
            # 每天2个学习时段
            for slot in [9, 14]:  # 上午9点和下午2点
                slot_time = day_date.replace(hour=slot, minute=0, second=0)
                time_slots.append(slot_time)
        
        # 分配任务到时间槽
        slot_index = 0
        tasks_assigned = 0
        concurrent_tasks = 0
        
        for task in sorted_tasks:
            if tasks_assigned >= len(time_slots) * self.config.max_concurrent_tasks:
                break
            
            if slot_index >= len(time_slots):
                break
            
            slot_time = time_slots[slot_index]
            slot_key = slot_time.strftime("%Y-%m-%d %H:%M")
            
            schedule[slot_key].append(task.id)
            concurrent_tasks += 1
            
            # 如果达到最大并发任务数，移动到下一个时间槽
            if concurrent_tasks >= self.config.max_concurrent_tasks:
                concurrent_tasks = 0
                slot_index += 1
            
            tasks_assigned += 1
        
        return dict(schedule)
    
    def _estimate_completion_time(self, schedule: Dict[str, List[str]]) -> str:
        """估计完成时间"""
        if not schedule:
            return datetime.now().isoformat()
        
        # 找到最后一个时间槽
        last_slot = max(schedule.keys())
        
        try:
            last_time = datetime.strptime(last_slot, "%Y-%m-%d %H:%M")
            # 加上任务执行时间
            estimated_completion = last_time + timedelta(hours=2)
            return estimated_completion.isoformat()
        except:
            return datetime.now().isoformat()
    
    async def execute_learning_task(self, task: LearningTask) -> Dict[str, Any]:
        """
        执行学习任务
        
        Args:
            task: 学习任务
            
        Returns:
            执行结果
        """
        self.logger.info(f"开始执行学习任务: {task.id}")
        
        task.stage = LearningStage.EXECUTION
        task.start_time = datetime.now().isoformat()
        task.progress = 0.0
        
        # 添加到活跃任务
        self.active_tasks[task.id] = task
        
        try:
            # 模拟任务执行
            result = await self._simulate_task_execution(task)
            
            task.end_time = datetime.now().isoformat()
            task.stage = LearningStage.COMPLETED
            task.progress = 1.0
            task.results = result
            
            # 从活跃任务移除，添加到完成列表
            self.active_tasks.pop(task.id, None)
            self.completed_tasks.append(task)
            
            # 更新技能精通度
            await self._update_skill_proficiency(task)
            
            # 记录学习历史
            learning_record = {
                "task_id": task.id,
                "objective_id": task.objective_id,
                "task_type": task.task_type.name,
                "start_time": task.start_time,
                "end_time": task.end_time,
                "results": result,
                "skill_gain": result.get("skill_gain", 0)
            }
            self.learning_history.append(learning_record)
            
            self.logger.info(f"学习任务完成: {task.id}")
            return result
            
        except Exception as e:
            self.logger.error(f"学习任务失败: {task.id} - {e}")
            
            task.stage = LearningStage.COMPLETED  # 即使是失败也标记为完成
            task.progress = 1.0
            task.results = {"error": str(e)}
            
            # 添加到失败列表
            self.failed_tasks.append(task)
            
            return {"error": str(e), "success": False}
    
    async def _simulate_task_execution(self, task: LearningTask) -> Dict[str, Any]:
        """模拟任务执行"""
        # 这里应该实际执行学习任务
        # 目前只是模拟
        
        import asyncio
        import random
        
        # 模拟任务执行时间
        execution_time = task.time_estimate * 0.8 + random.uniform(0, task.time_estimate * 0.4)
        await asyncio.sleep(min(execution_time / 100, 1))  # 实际使用时去掉这个
        
        # 模拟学习成果
        skill_gain = random.uniform(0.05, 0.2) * (1 - task.difficulty)
        
        # 生成详细结果
        results = {
            "skill_gain": skill_gain,
            "knowledge_acquired": [
                f"掌握了{task.description}的基本方法",
                "理解了相关概念和原理",
                "能够应用所学解决问题"
            ],
            "insights": [
                "发现了新的优化方向",
                "建立了知识连接",
                "改进了学习方法"
            ],
            "artifacts": [
                "学习笔记",
                "代码实现",
                "测试报告"
            ],
            "metrics": {
                "completion_rate": 1.0,
                "understanding_depth": random.uniform(0.6, 0.9),
                "application_ability": random.uniform(0.5, 0.8)
            },
            "success": True
        }
        
        # 根据任务类型添加特定结果
        if task.task_type == LearningTaskType.EXPLORATORY:
            results["exploratory_findings"] = [
                "发现了三种可行的方法",
                "比较了各种方法的优缺点",
                "选择了最适合当前情境的方法"
            ]
        
        elif task.task_type == LearningTaskType.TRANSFER:
            results["transfer_results"] = {
                "source_skill": task.description.split()[0],
                "target_domain": "新应用场景",
                "transfer_effectiveness": random.uniform(0.6, 0.9)
            }
        
        return results
    
    async def _update_skill_proficiency(self, task: LearningTask):
        """更新技能精通度"""
        # 找到对应的目标
        objective = None
        if self.current_plan:
            for obj in self.current_plan.objectives:
                if obj.id == task.objective_id:
                    objective = obj
                    break
        
        if objective:
            skill = objective.target_skill
            current_proficiency = self.skill_proficiency.get(skill, 0)
            
            # 根据任务结果更新精通度
            skill_gain = task.results.get("skill_gain", 0)
            new_proficiency = min(current_proficiency + skill_gain, 1.0)
            
            self.skill_proficiency[skill] = new_proficiency
            
            self.logger.debug(f"技能更新: {skill} {current_proficiency:.3f} -> {new_proficiency:.3f}")
    
    async def evaluate_learning_progress(self) -> Dict[str, Any]:
        """
        评估学习进展
        
        Returns:
            评估结果
        """
        self.logger.info("评估学习进展")
        
        evaluation = {
            "timestamp": datetime.now().isoformat(),
            "plan_progress": {},
            "skill_improvements": {},
            "task_completion": {},
            "overall_assessment": {},
            "recommendations": []
        }
        
        # 评估计划进度
        if self.current_plan:
            total_tasks = len(self.current_plan.tasks)
            completed_tasks = len(self.completed_tasks)
            failed_tasks = len(self.failed_tasks)
            active_tasks = len(self.active_tasks)
            
            completion_rate = completed_tasks / total_tasks if total_tasks > 0 else 0
            
            evaluation["plan_progress"] = {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "active_tasks": active_tasks,
                "completion_rate": completion_rate,
                "plan_id": self.current_plan.id
            }
        
        # 评估技能改进
        skill_improvements = {}
        for skill, proficiency in self.skill_proficiency.items():
            # 记录历史变化（如果有）
            skill_improvements[skill] = {
                "current_proficiency": proficiency,
                "trend": "improving" if proficiency > 0.5 else "needs_work"
            }
        
        evaluation["skill_improvements"] = skill_improvements
        
        # 评估任务完成情况
        task_stats = {
            "total_completed": len(self.completed_tasks),
            "total_failed": len(self.failed_tasks),
            "success_rate": len(self.completed_tasks) / 
                          (len(self.completed_tasks) + len(self.failed_tasks)) 
                          if (len(self.completed_tasks) + len(self.failed_tasks)) > 0 else 0,
            "average_task_duration": self._calculate_average_task_duration()
        }
        evaluation["task_completion"] = task_stats
        
        # 总体评估
        overall_score = self._calculate_overall_score(evaluation)
        evaluation["overall_assessment"] = {
            "score": overall_score,
            "level": self._get_learning_level(overall_score),
            "strengths": self._identify_learning_strengths(),
            "areas_for_improvement": self._identify_improvement_areas()
        }
        
        # 生成建议
        evaluation["recommendations"] = self._generate_recommendations(evaluation)
        
        self.logger.info(f"学习进展评估完成: 总体得分 {overall_score:.3f}")
        return evaluation
    
    def _calculate_average_task_duration(self) -> float:
        """计算平均任务持续时间"""
        if not self.completed_tasks:
            return 0.0
        
        total_duration = 0
        count = 0
        
        for task in self.completed_tasks:
            if task.start_time and task.end_time:
                try:
                    start = datetime.fromisoformat(task.start_time)
                    end = datetime.fromisoformat(task.end_time)
                    duration = (end - start).total_seconds() / 60  # 转换为分钟
                    total_duration += duration
                    count += 1
                except:
                    continue
        
        return total_duration / count if count > 0 else 0.0
    
    def _calculate_overall_score(self, evaluation: Dict[str, Any]) -> float:
        """计算总体得分"""
        plan_progress = evaluation.get("plan_progress", {})
        task_completion = evaluation.get("task_completion", {})
        
        completion_rate = plan_progress.get("completion_rate", 0)
        success_rate = task_completion.get("success_rate", 0)
        
        # 技能平均精通度
        skill_improvements = evaluation.get("skill_improvements", {})
        if skill_improvements:
            avg_proficiency = sum(
                s["current_proficiency"] for s in skill_improvements.values()
            ) / len(skill_improvements)
        else:
            avg_proficiency = 0.5
        
        # 综合得分
        overall_score = (
            completion_rate * 0.3 +
            success_rate * 0.3 +
            avg_proficiency * 0.4
        )
        
        return overall_score
    
    def _get_learning_level(self, score: float) -> str:
        """获取学习水平"""
        if score >= 0.8:
            return "高级"
        elif score >= 0.6:
            return "中级"
        elif score >= 0.4:
            return "初级"
        else:
            return "入门"
    
    def _identify_learning_strengths(self) -> List[str]:
        """识别学习优势"""
        strengths = []
        
        # 分析完成的任务类型
        task_types = defaultdict(int)
        for task in self.completed_tasks:
            task_types[task.task_type.name] += 1
        
        if task_types:
            most_common = max(task_types.items(), key=lambda x: x[1])
            strengths.append(f"擅长{most_common[0]}类型的学习任务")
        
        # 分析技能优势
        if self.skill_proficiency:
            strongest_skill = max(self.skill_proficiency.items(), key=lambda x: x[1])
            if strongest_skill[1] > 0.7:
                strengths.append(f"{strongest_skill[0]}能力突出")
        
        return strengths if strengths else ["学习态度积极，持续进步"]
    
    def _identify_improvement_areas(self) -> List[str]:
        """识别需要改进的领域"""
        areas = []
        
        # 分析失败的任务
        if self.failed_tasks:
            areas.append("需要提高任务执行的成功率")
        
        # 分析技能短板
        if self.skill_proficiency:
            weakest_skill = min(self.skill_proficiency.items(), key=lambda x: x[1])
            if weakest_skill[1] < 0.5:
                areas.append(f"{weakest_skill[0]}能力需要加强")
        
        # 分析任务类型偏好
        task_types = defaultdict(int)
        for task in self.completed_tasks + self.failed_tasks:
            task_types[task.task_type.name] += 1
        
        if task_types:
            least_common = min(task_types.items(), key=lambda x: x[1])
            areas.append(f"需要加强{least_common[0]}类型的学习")
        
        return areas if areas else ["当前学习表现良好，继续保持"]
    
    def _generate_recommendations(self, evaluation: Dict[str, Any]) -> List[str]:
        """生成学习建议"""
        recommendations = []
        
        overall_assessment = evaluation.get("overall_assessment", {})
        areas_for_improvement = overall_assessment.get("areas_for_improvement", [])
        
        # 基于需要改进的领域生成建议
        for area in areas_for_improvement:
            if "成功率" in area:
                recommendations.append("增加任务前的准备工作，确保充分理解任务要求")
                recommendations.append("建立错误分析和复盘机制")
            
            elif "能力需要加强" in area:
                skill = area.split("能力")[0]
                recommendations.append(f"增加{skill}相关的学习任务")
                recommendations.append(f"寻找{skill}的专家指导或学习资源")
            
            elif "需要加强" in area:
                task_type = area.split("需要加强")[1].replace("类型的学习", "")
                recommendations.append(f"安排更多{task_type}类型的学习任务")
                recommendations.append(f"学习{task_type}的最佳实践和方法")
        
        # 通用建议
        if not recommendations:
            recommendations.append("保持当前学习节奏，定期复习巩固")
            recommendations.append("尝试将所学知识应用到实际项目中")
            recommendations.append("与其他学习者交流，分享学习经验")
        
        return recommendations
    
    def get_learning_report(self) -> Dict[str, Any]:
        """
        获取学习报告
        
        Returns:
            学习报告
        """
        return {
            "system_name": self.system_name,
            "current_plan": self.current_plan.to_dict() if self.current_plan else None,
            "skill_proficiency": dict(self.skill_proficiency),
            "learning_statistics": {
                "total_completed_tasks": len(self.completed_tasks),
                "total_failed_tasks": len(self.failed_tasks),
                "active_tasks": len(self.active_tasks),
                "total_learning_hours": self._calculate_total_learning_hours(),
                "average_skill_gain": self._calculate_average_skill_gain(),
                "learning_history_count": len(self.learning_history)
            },
            "recent_achievements": self._get_recent_achievements(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _calculate_total_learning_hours(self) -> float:
        """计算总学习小时数"""
        total_minutes = 0
        
        for task in self.completed_tasks:
            total_minutes += task.time_estimate
        
        return total_minutes / 60
    
    def _calculate_average_skill_gain(self) -> float:
        """计算平均技能增益"""
        if not self.learning_history:
            return 0.0
        
        total_gain = sum(record.get("skill_gain", 0) for record in self.learning_history)
        return total_gain / len(self.learning_history)
    
    def _get_recent_achievements(self) -> List[str]:
        """获取最近成就"""
        achievements = []
        
        # 最近完成的任务
        recent_tasks = self.completed_tasks[-3:] if self.completed_tasks else []
        for task in recent_tasks:
            achievements.append(f"完成了学习任务: {task.description}")
        
        # 技能提升
        if self.skill_proficiency:
            improved_skills = [
                skill for skill, proficiency in self.skill_proficiency.items()
                if proficiency > 0.7
            ]
            if improved_skills:
                achievements.append(f"掌握了高熟练度技能: {', '.join(improved_skills[:3])}")
        
        return achievements if achievements else ["持续学习中..."]
    
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
                "skill_proficiency": dict(self.skill_proficiency),
                "current_plan": self.current_plan.to_dict() if self.current_plan else None,
                "completed_tasks": [task.to_dict() for task in self.completed_tasks],
                "failed_tasks": [task.to_dict() for task in self.failed_tasks],
                "learning_history": self.learning_history,
                "saved_at": datetime.now().isoformat()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"学习状态已保存到: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存学习状态失败: {e}")
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
            self.config = LearningConfig(**state_data["config"])
            
            # 恢复技能精通度
            self.skill_proficiency = defaultdict(float, state_data["skill_proficiency"])
            
            # 恢复当前计划
            plan_data = state_data.get("current_plan")
            if plan_data:
                objectives = []
                for obj_data in plan_data["objectives"]:
                    objective = LearningObjective(
                        id=obj_data["id"],
                        description=obj_data["description"],
                        target_skill=obj_data["target_skill"],
                        target_proficiency=obj_data["target_proficiency"],
                        prerequisites=obj_data["prerequisites"],
                        priority=LearningPriority[obj_data["priority"]],
                        estimated_duration=obj_data["estimated_duration"],
                        dependencies=obj_data.get("dependencies", []),
                        metrics=obj_data.get("metrics", {})
                    )
                    objectives.append(objective)
                
                tasks = []
                for task_data in plan_data["tasks"]:
                    task = LearningTask(
                        id=task_data["id"],
                        objective_id=task_data["objective_id"],
                        task_type=LearningTaskType[task_data["task_type"]],
                        description=task_data["description"],
                        instructions=task_data["instructions"],
                        resources=task_data["resources"],
                        expected_outcomes=task_data["expected_outcomes"],
                        difficulty=task_data["difficulty"],
                        time_estimate=task_data["time_estimate"],
                        stage=LearningStage[task_data["stage"]],
                        progress=task_data["progress"],
                        start_time=task_data.get("start_time"),
                        end_time=task_data.get("end_time"),
                        results=task_data.get("results", {}),
                        feedback=task_data.get("feedback", [])
                    )
                    tasks.append(task)
                
                self.current_plan = LearningPlan(
                    id=plan_data["id"],
                    version=plan_data["version"],
                    objectives=objectives,
                    tasks=tasks,
                    schedule=plan_data["schedule"],
                    constraints=plan_data["constraints"],
                    estimated_completion=plan_data["estimated_completion"],
                    created_at=plan_data["created_at"],
                    updated_at=plan_data["updated_at"]
                )
            
            # 恢复完成任务
            self.completed_tasks = []
            for task_data in state_data["completed_tasks"]:
                task = LearningTask(
                    id=task_data["id"],
                    objective_id=task_data["objective_id"],
                    task_type=LearningTaskType[task_data["task_type"]],
                    description=task_data["description"],
                    instructions=task_data["instructions"],
                    resources=task_data["resources"],
                    expected_outcomes=task_data["expected_outcomes"],
                    difficulty=task_data["difficulty"],
                    time_estimate=task_data["time_estimate"],
                    stage=LearningStage[task_data["stage"]],
                    progress=task_data["progress"],
                    start_time=task_data.get("start_time"),
                    end_time=task_data.get("end_time"),
                    results=task_data.get("results", {}),
                    feedback=task_data.get("feedback", [])
                )
                self.completed_tasks.append(task)
            
            # 恢复其他数据
            self.failed_tasks = []
            for task_data in state_data["failed_tasks"]:
                task = LearningTask(**task_data)
                self.failed_tasks.append(task)
            
            self.learning_history = state_data["learning_history"]
            
            self.logger.info(f"学习状态已从 {filepath} 加载")
            return True
            
        except Exception as e:
            self.logger.error(f"加载学习状态失败: {e}")
            return False