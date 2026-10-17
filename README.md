# AutoNewsAnalyzer

🚀 一个具备自主进化能力的 AI 驱动新闻分析系统

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

## 📖 概述

AutoNewsAnalyzer 是一个具备自主进化能力的 AI 系统，能够自动采集、评估、学习新闻信息，并持续优化自身能力。系统借鉴生命体"感知-学习-净化"的生命循环逻辑，实现从信息采集到知识代谢的全流程自动化。

### ✨ 核心特性

- **🧠 自主进化**: 基于反馈循环的持续学习与自我优化
- **📊 智能评估**: 多维度动态可信度评估模型
- **🔍 知识提取**: 从非结构化文本提取结构化知识
- **🔄 动态适应**: 实时响应信息环境变化
- **🏗️ 模块化架构**: 解耦设计，灵活可扩展
- **📈 可解释性**: 评估、提取、清理流程完全透明可追溯

## 🚀 快速开始

### 环境要求

- **Python**: 3.8 或更高版本
- **操作系统**: Windows / Linux / macOS

### ⚠️ 运行前必读：配置 API

本版本**必须配置大模型 API 才能运行**。代码中已删除所有真实密钥，仅保留占位符。
请务必先阅读：[如何重新接入大模型 API](如何加API.md)，按照说明在 `main.py` 中填入你的 API Key、Base URL 和模型名称。

### 安装步骤

1. **克隆项目**

```bash
git clone https://github.com/caoyilin3/auto-news-analyzer.git

cd auto-news-analyzer
```
安装依赖
```
bash
pip install -r requirements.txt
```
配置 API（必做）

请参阅 如何加API.md 完成配置。

运行系统

配置好 API 后，直接运行：

```bash
python main.py
```
或者，如果你想跑多轮分析：

```bash
python main.py --cycles 2
```
📚 文档
如何重新接入大模型 API

系统设计报告

可信度评估模块设计文档

知识提取模块设计文档

生命周期管理模块设计文档

📄 原创声明与 License
本系统（AutoNewsAnalyzer）由 曹依琳 独立设计并开发。
原始仓库：https://github.com/caoyilin3/auto-news-analyzer

本项目采用 Apache License 2.0 开源。
您可以自由使用、修改、分发本代码，但必须保留原始版权声明和 NOTICE 文件。
禁止删除声明后声称原创。详见 LICENSE 文件。
