"""
safety_controller.py - 安全进化控制器
确保系统进化过程的安全性和可控性
"""

import logging
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from abc import ABC, abstractmethod
import re
import json
from collections import defaultdict
import hashlib


class SafetyLevel(Enum):
    """安全级别"""
    CRITICAL = auto()    # 关键级别
    HIGH = auto()        # 高级别
    MEDIUM = auto()      # 中级别
    LOW = auto()         # 低级别
    INFO = auto()        # 信息级别


class SafetyConstraintType(Enum):
    """安全约束类型"""
    ETHICAL = auto()     # 伦理约束
    LEGAL = auto()       # 法律约束
    TECHNICAL = auto()   # 技术约束
    OPERATIONAL = auto() # 操作约束
    SOCIAL = auto()      # 社会约束


class SafetyAction(Enum):
    """安全动作"""
    ALLOW = auto()       # 允许
    WARN = auto()        # 警告
    BLOCK = auto()       # 阻止
    MODIFY = auto()      # 修改
    AUDIT = auto()       # 审计
    ESCALATE = auto()    # 升级


@dataclass
class SafetyConstraint:
    """安全约束"""
    id: str
    name: str
    constraint_type: SafetyConstraintType
    description: str
    rule: str  # 规则表达式或函数
    severity: SafetyLevel
    action: SafetyAction
    enabled: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SafetyViolation:
    """安全违规"""
    constraint_id: str
    violation_type: str
    description: str
    severity: SafetyLevel
    evidence: Dict[str, Any]
    timestamp: str
    action_taken: SafetyAction
    resolved: bool = False
    resolution: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SafetyConfig:
    """安全配置"""
    safety_mode: str = "balanced"  # "strict", "balanced", "permissive"
    enable_real_time_checking: bool = True
    max_violations_per_hour: int = 10
    require_human_approval: bool = False
    approval_threshold: SafetyLevel = SafetyLevel.MEDIUM
    enable_audit_logging: bool = True
    audit_log_path: str = "./data/safety_audit"
    constraints: List[SafetyConstraint] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            **asdict(self),
            "constraints": [c.to_dict() for c in self.constraints]
        }


class SafetyController(ABC):
    """安全控制器基类"""
    
    @abstractmethod
    async def check_evolution(self, evolution_plan: Dict[str, Any]) -> Tuple[bool, List[SafetyViolation]]:
        """检查进化计划安全性"""
        pass
    
    @abstractmethod
    async def monitor_behavior(self, behavior_data: Dict[str, Any]) -> List[SafetyViolation]:
        """监控行为安全性"""
        pass
    
    @abstractmethod
    async def enforce_constraint(self, constraint: SafetyConstraint, context: Dict[str, Any]) -> SafetyAction:
        """强制执行约束"""
        pass


class AutoSafetyController(SafetyController):
    """
    自动安全控制器
    实现多层次的安全控制和约束检查
    """
    
    def __init__(self, 
                 system_name: str = "AutoNewsAnalyzer",
                 config: Optional[SafetyConfig] = None):
        """
        初始化安全控制器
        
        Args:
            system_name: 系统名称
            config: 配置
        """
        self.system_name = system_name
        self.config = config or SafetyConfig()
        self.logger = logging.getLogger(f"Safety.{system_name}")
        
        # 约束管理
        self.constraints: Dict[str, SafetyConstraint] = {}
        self.violation_history: List[SafetyViolation] = []
        self.approval_history: List[Dict[str, Any]] = []
        
        # 状态统计
        self.stats = {
            "total_checks": 0,
            "violations_blocked": 0,
            "violations_allowed": 0,
            "violations_modified": 0,
            "human_approvals": 0,
            "last_check": None
        }
        
        # 规则引擎
        self.rule_engine = SafetyRuleEngine()
        
        # 初始化默认约束
        self._initialize_default_constraints()
        
        # 审计日志
        if self.config.enable_audit_logging:
            self._setup_audit_logging()
        
        self.logger.info(f"安全控制器初始化完成: {system_name} (模式: {self.config.safety_mode})")
    
    def _initialize_default_constraints(self):
        """初始化默认约束"""
        default_constraints = [
            SafetyConstraint(
                id="eth-001",
                name="伦理边界约束",
                constraint_type=SafetyConstraintType.ETHICAL,
                description="防止生成有害、歧视性或不当内容",
                rule="not contains_harmful_content",
                severity=SafetyLevel.CRITICAL,
                action=SafetyAction.BLOCK,
                parameters={
                    "harmful_patterns": [
                        "仇恨言论", "暴力内容", "歧视性语言",
                        "非法内容", "成人内容"
                    ]
                }
            ),
            SafetyConstraint(
                id="tech-001",
                name="资源使用约束",
                constraint_type=SafetyConstraintType.TECHNICAL,
                description="防止资源滥用和系统过载",
                rule="resource_usage < threshold",
                severity=SafetyLevel.HIGH,
                action=SafetyAction.WARN,
                parameters={
                    "cpu_threshold": 80,
                    "memory_threshold": 85,
                    "disk_threshold": 90
                }
            ),
            SafetyConstraint(
                id="op-001",
                name="操作安全约束",
                constraint_type=SafetyConstraintType.OPERATIONAL,
                description="确保操作在可控范围内",
                rule="is_operation_safe",
                severity=SafetyLevel.MEDIUM,
                action=SafetyAction.AUDIT,
                parameters={
                    "allowed_operations": [
                        "parameter_adjustment", "strategy_update",
                        "knowledge_expansion", "performance_optimization"
                    ]
                }
            ),
            SafetyConstraint(
                id="legal-001",
                name="法律合规约束",
                constraint_type=SafetyConstraintType.LEGAL,
                description="确保符合相关法律法规",
                rule="is_legally_compliant",
                severity=SafetyLevel.CRITICAL,
                action=SafetyAction.BLOCK,
                parameters={
                    "regulations": ["数据保护", "隐私安全", "知识产权"]
                }
            ),
            SafetyConstraint(
                id="social-001",
                name="社会责任约束",
                constraint_type=SafetyConstraintType.SOCIAL,
                description="考虑社会影响和公众利益",
                rule="has_positive_social_impact",
                severity=SafetyLevel.MEDIUM,
                action=SafetyAction.AUDIT,
                parameters={
                    "social_values": ["公平", "透明", "负责任"]
                }
            )
        ]
        
        for constraint in default_constraints:
            self.constraints[constraint.id] = constraint
        
        # 添加自定义约束
        for constraint in self.config.constraints:
            self.constraints[constraint.id] = constraint
        
        self.logger.info(f"加载了 {len(self.constraints)} 个安全约束")
    
    def _setup_audit_logging(self):
        """设置审计日志"""
        import os
        os.makedirs(self.config.audit_log_path, exist_ok=True)
        
        self.audit_logger = logging.getLogger(f"SafetyAudit.{self.system_name}")
        audit_handler = logging.FileHandler(
            f"{self.config.audit_log_path}/safety_audit.log"
        )
        audit_handler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )
        self.audit_logger.addHandler(audit_handler)
        self.audit_logger.setLevel(logging.INFO)
    
    def set_safety_mode(self, mode: str):
        """
        设置安全模式
        
        Args:
            mode: "strict", "balanced", "permissive"
        """
        valid_modes = ["strict", "balanced", "permissive"]
        if mode not in valid_modes:
            raise ValueError(f"无效的安全模式: {mode}")
        
        self.config.safety_mode = mode
        
        # 根据模式调整约束
        if mode == "strict":
            self._enable_all_constraints()
        elif mode == "balanced":
            self._enable_balanced_constraints()
        elif mode == "permissive":
            self._enable_permissive_constraints()
        
        self.logger.info(f"安全模式已设置为: {mode}")
    
    def _enable_all_constraints(self):
        """启用所有约束"""
        for constraint in self.constraints.values():
            constraint.enabled = True
    
    def _enable_balanced_constraints(self):
        """启用平衡约束"""
        for constraint in self.constraints.values():
            if constraint.severity in [SafetyLevel.CRITICAL, SafetyLevel.HIGH]:
                constraint.enabled = True
            elif constraint.severity == SafetyLevel.MEDIUM:
                constraint.enabled = True
            else:
                constraint.enabled = False
    
    def _enable_permissive_constraints(self):
        """启用宽松约束"""
        for constraint in self.constraints.values():
            if constraint.severity == SafetyLevel.CRITICAL:
                constraint.enabled = True
            else:
                constraint.enabled = False
    
    async def check_evolution(self, evolution_plan: Dict[str, Any]) -> Tuple[bool, List[SafetyViolation]]:
        """
        检查进化计划安全性
        
        Args:
            evolution_plan: 进化计划
            
        Returns:
            (是否安全, 违规列表)
        """
        self.stats["total_checks"] += 1
        self.stats["last_check"] = datetime.now().isoformat()
        
        violations = []
        is_safe = True
        
        # 应用所有启用约束的检查
        for constraint in self.constraints.values():
            if not constraint.enabled:
                continue
            
            try:
                # 检查约束
                violation = await self._check_constraint(constraint, evolution_plan)
                if violation:
                    violations.append(violation)
                    
                    # 根据约束动作决定安全性
                    if constraint.action in [SafetyAction.BLOCK, SafetyAction.MODIFY]:
                        is_safe = False
                    
                    # 记录违规
                    self._record_violation(violation)
            
            except Exception as e:
                self.logger.error(f"检查约束 {constraint.id} 时出错: {e}")
        
        # 检查是否需要人工审批
        if not is_safe and self.config.require_human_approval:
            needs_approval = any(
                v.severity.value >= self.config.approval_threshold.value 
                for v in violations
            )
            
            if needs_approval:
                is_safe = await self._request_human_approval(evolution_plan, violations)
        
        self.logger.info(f"进化计划检查: 安全={is_safe}, 违规={len(violations)}")
        return is_safe, violations
    
    async def _check_constraint(self, constraint: SafetyConstraint, 
                               evolution_plan: Dict[str, Any]) -> Optional[SafetyViolation]:
        """
        检查单个约束
        
        Args:
            constraint: 约束
            evolution_plan: 进化计划
            
        Returns:
            违规信息，如果没有违规则返回None
        """
        # 根据约束类型应用不同的检查逻辑
        if constraint.constraint_type == SafetyConstraintType.ETHICAL:
            return await self._check_ethical_constraint(constraint, evolution_plan)
        
        elif constraint.constraint_type == SafetyConstraintType.TECHNICAL:
            return await self._check_technical_constraint(constraint, evolution_plan)
        
        elif constraint.constraint_type == SafetyConstraintType.OPERATIONAL:
            return await self._check_operational_constraint(constraint, evolution_plan)
        
        elif constraint.constraint_type == SafetyConstraintType.LEGAL:
            return await self._check_legal_constraint(constraint, evolution_plan)
        
        elif constraint.constraint_type == SafetyConstraintType.SOCIAL:
            return await self._check_social_constraint(constraint, evolution_plan)
        
        else:
            self.logger.warning(f"未知的约束类型: {constraint.constraint_type}")
            return None
    
    async def _check_ethical_constraint(self, constraint: SafetyConstraint,
                                       evolution_plan: Dict[str, Any]) -> Optional[SafetyViolation]:
        """检查伦理约束"""
        plan_str = json.dumps(evolution_plan, ensure_ascii=False, default=str)
        
        # 检查是否包含有害内容
        harmful_patterns = constraint.parameters.get("harmful_patterns", [])
        for pattern in harmful_patterns:
            if pattern in plan_str:
                return SafetyViolation(
                    constraint_id=constraint.id,
                    violation_type="ethical_violation",
                    description=f"检测到有害内容: {pattern}",
                    severity=constraint.severity,
                    evidence={
                        "pattern": pattern,
                        "context": plan_str[:200] + "..." if len(plan_str) > 200 else plan_str
                    },
                    timestamp=datetime.now().isoformat(),
                    action_taken=constraint.action
                )
        
        # 检查偏见和歧视
        bias_keywords = ["歧视", "偏见", "不公平", "排他性"]
        for keyword in bias_keywords:
            if keyword in plan_str:
                return SafetyViolation(
                    constraint_id=constraint.id,
                    violation_type="bias_violation",
                    description=f"检测到可能的偏见: {keyword}",
                    severity=SafetyLevel.MEDIUM,
                    evidence={"keyword": keyword},
                    timestamp=datetime.now().isoformat(),
                    action_taken=SafetyAction.WARN
                )
        
        return None
    
    # 资源使用等级 → 百分比的经验映射
    _RESOURCE_LEVEL_PERCENT = {"low": 30.0, "medium": 60.0, "high": 85.0, "critical": 95.0}

    @classmethod
    def _as_percent(cls, value: Any) -> float:
        """把资源占用值归一化为百分比（兼容 30、"30%"、"low" 等写法）"""
        if isinstance(value, bool):
            return 0.0
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            key = value.strip().lower()
            try:
                return float(key.rstrip("%"))
            except ValueError:
                return cls._RESOURCE_LEVEL_PERCENT.get(key, 0.0)
        return 0.0

    async def _check_technical_constraint(self, constraint: SafetyConstraint,
                                        evolution_plan: Dict[str, Any]) -> Optional[SafetyViolation]:
        """检查技术约束"""
        # 检查资源使用
        resource_usage = evolution_plan.get("resource_requirements", {})
        
        # 计划里的资源占用可能是 "low"/"medium"/"high" 之类的等级描述，需先归一化为百分比
        cpu_usage = self._as_percent(resource_usage.get("cpu", 0))
        memory_usage = self._as_percent(resource_usage.get("memory", 0))
        disk_usage = self._as_percent(resource_usage.get("disk", 0))
        
        thresholds = constraint.parameters
        
        violations = []
        
        if cpu_usage > thresholds.get("cpu_threshold", 80):
            violations.append({
                "resource": "CPU",
                "usage": cpu_usage,
                "threshold": thresholds["cpu_threshold"]
            })
        
        if memory_usage > thresholds.get("memory_threshold", 85):
            violations.append({
                "resource": "内存",
                "usage": memory_usage,
                "threshold": thresholds["memory_threshold"]
            })
        
        if disk_usage > thresholds.get("disk_threshold", 90):
            violations.append({
                "resource": "磁盘",
                "usage": disk_usage,
                "threshold": thresholds["disk_threshold"]
            })
        
        if violations:
            return SafetyViolation(
                constraint_id=constraint.id,
                violation_type="resource_violation",
                description="资源使用超出阈值",
                severity=constraint.severity,
                evidence={"violations": violations},
                timestamp=datetime.now().isoformat(),
                action_taken=constraint.action
            )
        
        return None
    
    async def _check_operational_constraint(self, constraint: SafetyConstraint,
                                          evolution_plan: Dict[str, Any]) -> Optional[SafetyViolation]:
        """检查操作约束"""
        operation_type = evolution_plan.get("operation_type", "unknown")
        allowed_operations = constraint.parameters.get("allowed_operations", [])
        
        if operation_type not in allowed_operations:
            return SafetyViolation(
                constraint_id=constraint.id,
                violation_type="operation_violation",
                description=f"不允许的操作类型: {operation_type}",
                severity=constraint.severity,
                evidence={
                    "operation": operation_type,
                    "allowed": allowed_operations
                },
                timestamp=datetime.now().isoformat(),
                action_taken=constraint.action
            )
        
        return None
    
    async def _check_legal_constraint(self, constraint: SafetyConstraint,
                                     evolution_plan: Dict[str, Any]) -> Optional[SafetyViolation]:
        """检查法律约束"""
        # 检查数据保护
        data_handling = evolution_plan.get("data_handling", {})
        
        # 检查是否有明确的隐私保护措施
        if "privacy_protection" not in data_handling:
            return SafetyViolation(
                constraint_id=constraint.id,
                violation_type="legal_violation",
                description="缺少隐私保护措施",
                severity=SafetyLevel.MEDIUM,
                evidence=data_handling,
                timestamp=datetime.now().isoformat(),
                action_taken=SafetyAction.WARN
            )
        
        return None
    
    async def _check_social_constraint(self, constraint: SafetyConstraint,
                                      evolution_plan: Dict[str, Any]) -> Optional[SafetyViolation]:
        """检查社会约束"""
        social_impact = evolution_plan.get("social_impact", {})
        
        # 检查社会影响评估
        if not social_impact:
            return SafetyViolation(
                constraint_id=constraint.id,
                violation_type="social_violation",
                description="缺少社会影响评估",
                severity=SafetyLevel.LOW,
                evidence=evolution_plan,
                timestamp=datetime.now().isoformat(),
                action_taken=SafetyAction.AUDIT
            )
        
        # 检查是否考虑公共利益
        public_benefit = social_impact.get("public_benefit", False)
        if not public_benefit:
            return SafetyViolation(
                constraint_id=constraint.id,
                violation_type="social_violation",
                description="未充分考虑公共利益",
                severity=SafetyLevel.LOW,
                evidence=social_impact,
                timestamp=datetime.now().isoformat(),
                action_taken=SafetyAction.WARN
            )
        
        return None
    
    def _record_violation(self, violation: SafetyViolation):
        """记录违规"""
        self.violation_history.append(violation)
        
        # 更新统计
        if violation.action_taken == SafetyAction.BLOCK:
            self.stats["violations_blocked"] += 1
        elif violation.action_taken == SafetyAction.ALLOW:
            self.stats["violations_allowed"] += 1
        elif violation.action_taken == SafetyAction.MODIFY:
            self.stats["violations_modified"] += 1
        
        # 审计日志
        if self.config.enable_audit_logging:
            self.audit_logger.info(
                f"安全违规: {violation.violation_type} - {violation.description} - 动作: {violation.action_taken.name}"
            )
    
    async def _request_human_approval(self, evolution_plan: Dict[str, Any],
                                     violations: List[SafetyViolation]) -> bool:
        """
        请求人工审批
        
        Args:
            evolution_plan: 进化计划
            violations: 违规列表
            
        Returns:
            是否批准
        """
        approval_request = {
            "request_id": hashlib.md5(
                json.dumps(evolution_plan, sort_keys=True, default=str).encode()
            ).hexdigest()[:8],
            "timestamp": datetime.now().isoformat(),
            "evolution_plan": evolution_plan,
            "violations": [v.to_dict() for v in violations],
            "status": "pending",
            "approved": False,
            "reviewer": None,
            "comments": None
        }
        
        # 在实际系统中，这里应该调用人工审批接口
        # 这里模拟审批过程
        self.logger.warning(f"需要人工审批: 请求ID {approval_request['request_id']}")
        
        # 模拟审批结果（50%概率通过）
        import random
        approved = random.choice([True, False])
        
        approval_request["status"] = "reviewed"
        approval_request["approved"] = approved
        approval_request["reviewer"] = "system_admin"
        approval_request["comments"] = "模拟审批通过" if approved else "模拟审批拒绝"
        
        self.approval_history.append(approval_request)
        self.stats["human_approvals"] += 1
        
        if approved:
            self.logger.info(f"人工审批通过: {approval_request['request_id']}")
        else:
            self.logger.warning(f"人工审批拒绝: {approval_request['request_id']}")
        
        return approved
    
    async def monitor_behavior(self, behavior_data: Dict[str, Any]) -> List[SafetyViolation]:
        """
        监控行为安全性
        
        Args:
            behavior_data: 行为数据
            
        Returns:
            违规列表
        """
        violations = []
        
        # 实时行为监控
        for constraint in self.constraints.values():
            if not constraint.enabled:
                continue
            
            # 只监控关键和中等级别的约束
            if constraint.severity in [SafetyLevel.CRITICAL, SafetyLevel.HIGH, SafetyLevel.MEDIUM]:
                try:
                    violation = await self._monitor_behavior_constraint(constraint, behavior_data)
                    if violation:
                        violations.append(violation)
                        self._record_violation(violation)
                except Exception as e:
                    self.logger.error(f"行为监控约束 {constraint.id} 出错: {e}")
        
        return violations
    
    async def _monitor_behavior_constraint(self, constraint: SafetyConstraint,
                                          behavior_data: Dict[str, Any]) -> Optional[SafetyViolation]:
        """监控行为约束"""
        behavior_type = behavior_data.get("type", "unknown")
        behavior_content = behavior_data.get("content", "")
        
        # 检查有害行为模式
        if constraint.constraint_type == SafetyConstraintType.ETHICAL:
            harmful_patterns = constraint.parameters.get("harmful_patterns", [])
            
            for pattern in harmful_patterns:
                if pattern in behavior_content:
                    return SafetyViolation(
                        constraint_id=constraint.id,
                        violation_type="behavioral_ethical_violation",
                        description=f"检测到有害行为内容: {pattern}",
                        severity=constraint.severity,
                        evidence={
                            "behavior_type": behavior_type,
                            "pattern": pattern,
                            "content_preview": behavior_content[:100] + "..." if len(behavior_content) > 100 else behavior_content
                        },
                        timestamp=datetime.now().isoformat(),
                        action_taken=constraint.action
                    )
        
        return None
    
    async def enforce_constraint(self, constraint: SafetyConstraint, 
                                context: Dict[str, Any]) -> SafetyAction:
        """
        强制执行约束
        
        Args:
            constraint: 约束
            context: 执行上下文
            
        Returns:
            执行的动作
        """
        try:
            # 检查约束是否启用
            if not constraint.enabled:
                return SafetyAction.ALLOW
            
            # 执行约束规则
            rule_result = await self.rule_engine.execute(constraint.rule, context)
            
            if not rule_result:
                # 规则失败，执行约束动作
                self.logger.info(f"执行约束 {constraint.id}: {constraint.action.name}")
                
                # 记录执行
                if self.config.enable_audit_logging:
                    self.audit_logger.info(
                        f"约束执行: {constraint.id} - {constraint.name} - "
                        f"动作: {constraint.action.name} - 上下文: {context}"
                    )
                
                return constraint.action
            else:
                # 规则通过，允许
                return SafetyAction.ALLOW
                
        except Exception as e:
            self.logger.error(f"执行约束 {constraint.id} 时出错: {e}")
            # 出错时采取保守策略
            return SafetyAction.BLOCK
    
    async def mitigate_violation(self, violation: SafetyViolation) -> Dict[str, Any]:
        """
        缓解违规
        
        Args:
            violation: 违规信息
            
        Returns:
            缓解措施
        """
        mitigation = {
            "violation_id": violation.constraint_id,
            "timestamp": datetime.now().isoformat(),
            "actions": [],
            "effectiveness": "unknown",
            "status": "applied"
        }
        
        # 根据违规类型采取不同的缓解措施
        if "ethical" in violation.violation_type:
            mitigation["actions"].append("过滤有害内容")
            mitigation["actions"].append("添加内容审核")
            mitigation["effectiveness"] = "high"
        
        elif "resource" in violation.violation_type:
            mitigation["actions"].append("优化资源分配")
            mitigation["actions"].append("限制并发任务")
            mitigation["effectiveness"] = "medium"
        
        elif "legal" in violation.violation_type:
            mitigation["actions"].append("添加合规检查")
            mitigation["actions"].append("记录操作日志")
            mitigation["effectiveness"] = "high"
        
        # 标记违规为已解决
        violation.resolved = True
        violation.resolution = "通过缓解措施解决"
        
        self.logger.info(f"违规缓解完成: {violation.constraint_id}")
        return mitigation
    
    def add_constraint(self, constraint: SafetyConstraint) -> bool:
        """
        添加新约束
        
        Args:
            constraint: 约束
            
        Returns:
            是否成功
        """
        if constraint.id in self.constraints:
            self.logger.warning(f"约束ID已存在: {constraint.id}")
            return False
        
        self.constraints[constraint.id] = constraint
        self.logger.info(f"添加新约束: {constraint.id} - {constraint.name}")
        return True
    
    def remove_constraint(self, constraint_id: str) -> bool:
        """
        移除约束
        
        Args:
            constraint_id: 约束ID
            
        Returns:
            是否成功
        """
        if constraint_id not in self.constraints:
            self.logger.warning(f"约束ID不存在: {constraint_id}")
            return False
        
        removed = self.constraints.pop(constraint_id)
        self.logger.info(f"移除约束: {constraint_id} - {removed.name}")
        return True
    
    def update_constraint(self, constraint: SafetyConstraint) -> bool:
        """
        更新约束
        
        Args:
            constraint: 更新后的约束
            
        Returns:
            是否成功
        """
        if constraint.id not in self.constraints:
            self.logger.warning(f"约束ID不存在: {constraint.id}")
            return False
        
        self.constraints[constraint.id] = constraint
        self.logger.info(f"更新约束: {constraint.id}")
        return True
    
    def get_safety_report(self) -> Dict[str, Any]:
        """
        获取安全报告
        
        Returns:
            安全报告
        """
        # 统计违规
        recent_violations = [
            v for v in self.violation_history 
            if not v.resolved
        ]
        
        violation_by_type = defaultdict(int)
        for v in self.violation_history:
            violation_by_type[v.violation_type] += 1
        
        return {
            "system_name": self.system_name,
            "safety_mode": self.config.safety_mode,
            "constraint_count": len(self.constraints),
            "enabled_constraint_count": sum(1 for c in self.constraints.values() if c.enabled),
            "stats": self.stats,
            "recent_violations": len(recent_violations),
            "violation_by_type": dict(violation_by_type),
            "approval_count": len(self.approval_history),
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
                "constraints": {cid: c.to_dict() for cid, c in self.constraints.items()},
                "violation_history": [v.to_dict() for v in self.violation_history],
                "approval_history": self.approval_history,
                "stats": self.stats,
                "saved_at": datetime.now().isoformat()
            }
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"安全状态已保存到: {filepath}")
            return True
            
        except Exception as e:
            self.logger.error(f"保存安全状态失败: {e}")
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
            config_data = state_data["config"]
            self.config = SafetyConfig(
                safety_mode=config_data["safety_mode"],
                enable_real_time_checking=config_data["enable_real_time_checking"],
                max_violations_per_hour=config_data["max_violations_per_hour"],
                require_human_approval=config_data["require_human_approval"],
                enable_audit_logging=config_data["enable_audit_logging"],
                audit_log_path=config_data["audit_log_path"]
            )
            
            # 恢复约束
            self.constraints = {}
            for cid, c_data in state_data["constraints"].items():
                constraint = SafetyConstraint(
                    id=c_data["id"],
                    name=c_data["name"],
                    constraint_type=SafetyConstraintType[c_data["constraint_type"]],
                    description=c_data["description"],
                    rule=c_data["rule"],
                    severity=SafetyLevel[c_data["severity"]],
                    action=SafetyAction[c_data["action"]],
                    enabled=c_data["enabled"],
                    parameters=c_data["parameters"],
                    created_at=c_data["created_at"]
                )
                self.constraints[cid] = constraint
            
            # 恢复违规历史
            self.violation_history = []
            for v_data in state_data["violation_history"]:
                violation = SafetyViolation(
                    constraint_id=v_data["constraint_id"],
                    violation_type=v_data["violation_type"],
                    description=v_data["description"],
                    severity=SafetyLevel[v_data["severity"]],
                    evidence=v_data["evidence"],
                    timestamp=v_data["timestamp"],
                    action_taken=SafetyAction[v_data["action_taken"]],
                    resolved=v_data["resolved"],
                    resolution=v_data["resolution"]
                )
                self.violation_history.append(violation)
            
            # 恢复其他数据
            self.approval_history = state_data["approval_history"]
            self.stats = state_data["stats"]
            
            self.logger.info(f"安全状态已从 {filepath} 加载")
            return True
            
        except Exception as e:
            self.logger.error(f"加载安全状态失败: {e}")
            return False


class SafetyRuleEngine:
    """安全规则引擎"""
    
    def __init__(self):
        self.rules = {}
        self._register_default_rules()
    
    def _register_default_rules(self):
        """注册默认规则"""
        self.rules["contains_harmful_content"] = self._rule_contains_harmful_content
        self.rules["resource_usage"] = self._rule_resource_usage
        self.rules["is_operation_safe"] = self._rule_is_operation_safe
        self.rules["is_legally_compliant"] = self._rule_is_legally_compliant
        self.rules["has_positive_social_impact"] = self._rule_has_positive_social_impact
    
    async def execute(self, rule_name: str, context: Dict[str, Any]) -> bool:
        """
        执行规则
        
        Args:
            rule_name: 规则名称
            context: 执行上下文
            
        Returns:
            规则结果 (True: 通过, False: 失败)
        """
        if rule_name not in self.rules:
            raise ValueError(f"未知的规则: {rule_name}")
        
        rule_func = self.rules[rule_name]
        return await rule_func(context)
    
    async def _rule_contains_harmful_content(self, context: Dict[str, Any]) -> bool:
        """检查是否包含有害内容"""
        content = context.get("content", "")
        harmful_keywords = [
            "仇恨", "暴力", "歧视", "非法", "成人",
            "hate", "violence", "discrimination", "illegal", "adult"
        ]
        
        for keyword in harmful_keywords:
            if keyword in content:
                return False
        
        return True
    
    async def _rule_resource_usage(self, context: Dict[str, Any]) -> bool:
        """检查资源使用"""
        usage = context.get("resource_usage", {})
        threshold = context.get("threshold", 80)
        
        current_usage = usage.get("current", 0)
        return current_usage <= threshold
    
    async def _rule_is_operation_safe(self, context: Dict[str, Any]) -> bool:
        """检查操作是否安全"""
        operation = context.get("operation", "")
        safe_operations = context.get("safe_operations", [])
        
        return operation in safe_operations
    
    async def _rule_is_legally_compliant(self, context: Dict[str, Any]) -> bool:
        """检查是否合法合规"""
        # 简化的合规检查
        return context.get("is_compliant", True)
    
    async def _rule_has_positive_social_impact(self, context: Dict[str, Any]) -> bool:
        """检查是否有积极社会影响"""
        impact_analysis = context.get("social_impact_analysis", {})
        positive_score = impact_analysis.get("positive_score", 0)
        
        return positive_score > 0.5
    
    def register_rule(self, rule_name: str, rule_func: Callable) -> bool:
        """
        注册新规则
        
        Args:
            rule_name: 规则名称
            rule_func: 规则函数
            
        Returns:
            是否成功
        """
        if rule_name in self.rules:
            return False
        
        self.rules[rule_name] = rule_func
        return True