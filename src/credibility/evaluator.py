# src/credibility/evaluator.py
"""
可信度评估器 - 多维度动态可信度评估

对应论文《面向自动化信息处理系统的多维度可信度动态评估方法研究》：
- 五维评分：来源权威性、信息新鲜度、作者可靠性、内容完备性、URL 规范性
- 可配置加权融合：Stotal = Σ(wi * Si)，Σwi = 1
- 双阈值决策：学习(learn) / 审查(review) / 拒绝(reject)
"""
import re
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class CredibilityEvaluator:
    """多维度可信度评估器"""

    # 权威域名基准分映射
    DEFAULT_SOURCE_REPUTATION = {
        "arxiv.org": 0.95,
        "techcrunch.com": 0.80,
        "nature.com": 0.92,
        "github.com": 0.75,
        "medium.com": 0.60,
        "mock": 0.55,
        "unknown": 0.30,
    }

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)

        # 权重配置（默认科技新闻场景）
        self.weights = self.config.get("weights", {
            "source": 0.35,
            "freshness": 0.20,
            "author": 0.15,
            "content": 0.20,
            "url": 0.10,
        })
        # 归一化权重
        total = sum(self.weights.values()) or 1.0
        self.weights = {k: v / total for k, v in self.weights.items()}

        # 双阈值
        self.theta_high = self.config.get("theta_high", 0.8)
        self.theta_low = self.config.get("theta_low", 0.5)

        self.source_reputation = dict(self.DEFAULT_SOURCE_REPUTATION)
        self.source_reputation.update(self.config.get("source_reputation", {}))

        self.suspicious_url_pattern = re.compile(
            r"(sponsored|advertisement|clickbait|/ad/|/promo/)", re.I
        )

        self.stats = {
            "total_assessed": 0,
            "learn": 0,
            "review": 0,
            "reject": 0,
            "start_time": datetime.now(),
        }

    # ---------- 单维度评分 ----------
    def _score_source(self, article: Dict[str, Any]) -> float:
        """来源评分：调用权威域名-基准分映射表"""
        source = str(article.get("source", "unknown")).lower()
        # 尝试匹配域名
        url = str(article.get("url", ""))
        best = self.source_reputation.get("unknown", 0.3)
        for domain, score in self.source_reputation.items():
            if domain in source or domain in url:
                if score > best:
                    best = score
        return best

    def _score_freshness(self, article: Dict[str, Any]) -> float:
        """新鲜度评分：基于发布时长的分段衰减函数"""
        published_at = article.get("published_at")
        if not published_at:
            return 0.2
        try:
            if isinstance(published_at, str):
                if "T" in published_at:
                    publish_time = datetime.fromisoformat(
                        published_at.replace("Z", "+00:00")
                    )
                else:
                    publish_time = datetime.strptime(published_at, "%Y-%m-%d")
            else:
                publish_time = published_at
            days = (datetime.now() - publish_time).days
            if days <= 0:
                return 1.0
            elif days <= 7:
                return 0.8
            elif days <= 30:
                return 0.6
            elif days <= 365:
                return 0.4
            else:
                return 0.2
        except Exception:
            return 0.2

    def _score_author(self, article: Dict[str, Any]) -> float:
        """作者评分：白名单/署名完整性/机构后缀"""
        author = str(article.get("author", "")).strip()
        if not author or author.lower() in ("unknown", "anonymous", "未知"):
            return 0.5
        white_list = self.config.get("author_whitelist", [])
        for w in white_list:
            if w.lower() in author.lower():
                return 0.9
        # 机构后缀启发式
        if any(edu in author.lower() for edu in (".edu", "dr.", "prof.", "博士", "教授")):
            return 0.8
        # 署名完整（姓+名）
        if len(author.split()) >= 2:
            return 0.7
        return 0.5

    def _score_content(self, article: Dict[str, Any]) -> float:
        """内容质量评分：文本词数与段落结构"""
        content = str(article.get("content", ""))
        words = len(content)
        paragraphs = max(1, content.count("\n\n") + content.count("<p>") + 1)
        length_score = min(1.0, words / 1000)
        structure_score = min(1.0, paragraphs / 5)
        return (length_score + structure_score) / 2

    def _score_url(self, article: Dict[str, Any]) -> float:
        """URL 评分：可疑模式检测"""
        url = str(article.get("url", ""))
        if not url:
            return 0.2
        if self.suspicious_url_pattern.search(url):
            return 0.2
        return 0.8

    # ---------- 融合与决策 ----------
    def evaluate_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """评估单篇文章，返回五维分数与决策"""
        scores = {
            "source": self._score_source(article),
            "freshness": self._score_freshness(article),
            "author": self._score_author(article),
            "content": self._score_content(article),
            "url": self._score_url(article),
        }
        total = sum(self.weights[k] * scores[k] for k in scores)

        if total >= self.theta_high:
            decision = "learn"
        elif total >= self.theta_low:
            decision = "review"
        else:
            decision = "reject"

        article_id = article.get("id", "unknown")
        self.stats["total_assessed"] += 1
        self.stats[decision] += 1

        return {
            "article_id": article_id,
            "decision": decision,
            "score": round(total, 4),
            "dimensions": scores,
            "weights": self.weights,
            "thresholds": {"high": self.theta_high, "low": self.theta_low},
        }

    async def assess_credibility(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        批量评估并执行自动化决策，过滤低质信息

        Args:
            context: 执行上下文，包含待评估的 articles

        Returns:
            {status, articles(通过), rejected_count, decisions}
        """
        context = context or {}
        articles = context.get("articles", [])
        self.logger.info(f"开始可信度评估，共 {len(articles)} 篇")

        passed = []
        decisions = []
        rejected_count = 0

        for article in articles:
            result = self.evaluate_article(article)
            decisions.append(result)
            if result["decision"] != "reject":
                article["credibility"] = result
                passed.append(article)
            else:
                rejected_count += 1

        self.logger.info(
            f"评估完成：学习/审查 {len(passed)} 篇，拒绝 {rejected_count} 篇 "
            f"(拦截率 {rejected_count / max(1, len(articles)) * 100:.1f}%)"
        )
        return {
            "status": "completed",
            "articles": passed,
            "decisions": decisions,
            "rejected_count": rejected_count,
            "total_assessed": len(articles),
            "stats": self.stats,
        }

    def get_status(self) -> Dict[str, Any]:
        """获取状态信息"""
        assessed = max(1, self.stats["total_assessed"])
        return {
            "module": "credibility",
            "weights": self.weights,
            "thresholds": {"high": self.theta_high, "low": self.theta_low},
            "stats": self.stats,
            "reject_rate": self.stats["reject"] / assessed * 100,
            "learn_rate": self.stats["learn"] / assessed * 100,
        }

    def shutdown(self):
        """关闭评估器"""
        self.logger.info("可信度评估器已关闭")
