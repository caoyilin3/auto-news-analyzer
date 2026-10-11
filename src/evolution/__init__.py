"""
进化层模块
实现系统的自主进化能力
"""

from .meta_cognitive import (
    MetaCognitiveController,
    AutoMetaCognitiveController,
    MetaCognitiveConfig,
    MetaCognitiveState,
    LearningGoal,
    SelfAssessment
)

from .safety_controller import (
    SafetyController,
    AutoSafetyController,
    SafetyConfig,
    SafetyConstraint,
    SafetyViolation,
    SafetyLevel,
    SafetyAction,
    SafetyConstraintType,
    SafetyRuleEngine
)

from .learning_planner import (
    LearningPlanner,
    AutoLearningPlanner,
    LearningConfig,
    LearningObjective,
    LearningTask,
    LearningPlan,
    LearningTaskType,
    LearningPriority,
    LearningStage
)

from .manager import EvolutionManager


__all__ = [
    # 元认知
    "MetaCognitiveController",
    "AutoMetaCognitiveController",
    "MetaCognitiveConfig",
    "MetaCognitiveState",
    "LearningGoal",
    "SelfAssessment",

    # 安全控制
    "SafetyController",
    "AutoSafetyController",
    "SafetyConfig",
    "SafetyConstraint",
    "SafetyViolation",
    "SafetyLevel",
    "SafetyAction",
    "SafetyConstraintType",
    "SafetyRuleEngine",

    # 学习规划
    "LearningPlanner",
    "AutoLearningPlanner",
    "LearningConfig",
    "LearningObjective",
    "LearningTask",
    "LearningPlan",
    "LearningTaskType",
    "LearningPriority",
    "LearningStage",

    # 管理器
    "EvolutionManager"
]
