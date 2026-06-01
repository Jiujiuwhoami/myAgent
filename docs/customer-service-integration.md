# myAgent 智能客服 SaaS 集成指南

## 📋 集成概述

myAgent 作为**框架层**提供基础设施，智能客服 SaaS 作为**业务层**基于框架构建。

```
myAgent (框架) → SellerEngine (业务引擎) → 客服应用
```

---

## 🏗️ 集成架构

### 1. 核心依赖关系

| myAgent 模块 | 客服业务用途 | 集成方式 |
|-------------|-------------|---------|
| `MultiUserEngine` | 卖家数据隔离 | 继承扩展为 `SellerEngine` |
| `UserSkillManager` | 客服技能管理 | 扩展为 `CustomerServiceSkillManager` |
| `UserMCPManager` | 第三方工具集成 | 扩展为 `IntegrationMCPManager` |
| `MemoryOS` | 知识库管理 | 扩展为 `KnowledgeBaseManager` |
| `RAGAssembler` | FAQ 检索 | 直接使用 |
| `ConversationCompressor` | 对话上下文压缩 | 直接使用 |
| `DAG` | 客服工作流编排 | 扩展为 `CustomerServiceDAG` |

### 2. 目录结构

```
myAgent/
├── backend/
│   ├── seller_engine.py          # 业务引擎（继承 MultiUserEngine）
│   ├── model_config_manager.py   # 模型配置管理
│   ├── quota_manager.py          # 额度管理
│   └── subscription_manager.py   # 订阅管理
│
├── skills/
│   └── customer_service/
│       ├── __init__.py
│       ├── order_query.py        # 订单查询 Skill
│       ├── faq_answer.py         # FAQ 回答 Skill
│       └── logistics_track.py    # 物流跟踪 Skill
│
├── mcp/
│   ├── shopify_integration.py    # Shopify 工具
│   ├── woocommerce_integration.py # WooCommerce 工具
│   └── logistics_api.py          # 物流 API 工具
│
├── core/
│   └── customer_service_dag.py   # 客服工作流 DAG
│
├── rag/
│   └── knowledge_base.py         # 知识库 RAG
│
└── examples/
    └── customer_service_demo.py  # 快速启动示例
```

---

## 🔧 集成步骤

### 步骤 1：创建业务引擎

```python
# backend/seller_engine.py

from myAgent.backend.engine import MultiUserEngine
from myAgent.customer_service.model_config import ModelConfigManager
from myAgent.backend.quota_manager import PlatformQuotaManager
from myAgent.backend.subscription_manager import SubscriptionManager

class SellerEngine(MultiUserEngine):
    """智能客服业务引擎"""
    
    def __init__(self, seller_id: str, db_path: str = None):
        super().__init__(user_id=seller_id, db_path=db_path)
        self.model_config = ModelConfigManager(seller_id)
        self.quota_manager = PlatformQuotaManager(seller_id)
        self.subscription = SubscriptionManager(seller_id)
    
    async def handle_query(self, query: str, user_id: str = None) -> str:
        """处理客服查询"""
        # 1. 检查额度
        if not await self.quota_manager.check_quota(user_id):
            return "抱歉，您的额度已用完，请联系管理员。"
        
        # 2. 获取模型配置
        config = await self.model_config.get_active_config(user_id)
        
        # 3. 执行客服工作流
        response = await self._execute_customer_service_dag(query, config)
        
        # 4. 记录用量
        await self.quota_manager.record_usage(user_id, tokens_used)
        
        return response
```

### 步骤 2：创建客服 Skill

```python
# skills/customer_service/order_query.py

from myAgent.skills.base import Skill
from myAgent.rag.assembler import RAGAssembler

class OrderQuerySkill(Skill):
    """订单查询 Skill"""
    
    name = "order_query"
    description = "查询订单状态、物流信息"
    trigger_keywords = ["订单", "物流", "发货", "收货", "快递", "追踪"]
    
    async def execute(self, params: dict) -> dict:
        seller_id = self.context.get("seller_id")
        order_id = params.get("order_id")
        
        # 1. 查询订单系统
        order = await self._query_order_api(seller_id, order_id)
        
        # 2. 查询物流信息
        logistics = await self._query_logistics(order.shipping_id)
        
        return {
            "order_status": order.status,
            "logistics": logistics,
            "estimated_delivery": order.estimated_delivery
        }
```

### 步骤 3：创建 MCP 工具

```python
# mcp/shopify_integration.py

from myAgent.mcp.base import MCPTool
import httpx

class ShopifyOrderTool(MCPTool):
    """Shopify 订单查询工具"""
    
    name = "shopify_order_query"
    description = "查询 Shopify 订单详情"
    
    async def execute(self, order_id: str) -> dict:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://api.shopify.com/admin/api/2024-01/orders/{order_id}",
                headers={
                    "X-Shopify-Access-Token": self.api_key,
                    "Content-Type": "application/json"
                }
            )
            return response.json()
```

### 步骤 4：创建客服工作流 DAG

```python
# core/customer_service_dag.py

from myAgent.core.dag import DAG, Node

async def classify_intent(query: str) -> str:
    """意图识别"""
    if any(kw in query for kw in ["订单", "物流"]):
        return "order_query"
    elif any(kw in query for kw in ["怎么", "如何", "什么"]):
        return "faq"
    else:
        return "general"

async def check_faq_database(query: str, seller_id: str) -> str:
    """FAQ 检索"""
    rag = RAGAssembler(seller_id=seller_id)
    docs = await rag.search(query, top_k=3)
    if docs:
        return docs[0].content
    return None

def create_customer_service_dag() -> DAG:
    """创建客服处理工作流"""
    dag = DAG()
    
    dag.add_node(Node(
        id="intent_recognition",
        handler=classify_intent,
        next_nodes=["faq_check", "skill_dispatch", "general_answer"]
    ))
    
    dag.add_node(Node(
        id="faq_check",
        handler=check_faq_database,
        next_nodes=["answer_user", "skill_dispatch"]
    ))
    
    dag.add_node(Node(
        id="skill_dispatch",
        handler=dispatch_skill,
        next_nodes=["answer_user", "human_handoff"]
    ))
    
    dag.add_node(Node(
        id="answer_user",
        handler=format_response
    ))
    
    dag.add_node(Node(
        id="human_handoff",
        handler=transfer_to_human
    ))
    
    return dag
```

---

## 🚀 快速启动

### 1. 安装依赖

```bash
cd myAgent
pip install -e .
```

### 2. 运行示例

```bash
python examples/customer_service_demo.py
```

### 3. 启动 API 服务器

```bash
python -m myAgent.backend.server --host 0.0.0.0 --port 8000
```

---

## 📊 测试清单

| 测试项 | 状态 | 说明 |
|--------|------|------|
| 多租户隔离 | ✅ | SellerEngine 继承 MultiUserEngine |
| 模型配置切换 | ✅ | ModelConfigManager 支持 BYOK/Platform |
| Skill 注册 | ✅ | UserSkillManager 扩展 |
| MCP 工具集成 | ✅ | UserMCPManager 扩展 |
| RAG 知识库 | ✅ | RAGAssembler 直接使用 |
| 客服工作流 DAG | 🔄 | 待实现 |
| 额度管理 | ✅ | PlatformQuotaManager |
| 订阅管理 | ✅ | SubscriptionManager |

---

## 🎯 下一步

1. **实现 `SellerEngine`** - 在 `backend/seller_engine.py` 中创建业务引擎
2. **创建客服 Skill** - 在 `skills/customer_service/` 中添加业务 Skill
3. **集成 MCP 工具** - 在 `mcp/` 中添加第三方 API 工具
4. **构建客服 DAG** - 在 `core/customer_service_dag.py` 中定义工作流
5. **开发网站插件** - JavaScript Widget 嵌入客户网站

---

## 📚 参考文档

- [智能客服 SaaS 业务设计](../../docs/ai-customer-service-saas.md)
- [myAgent 框架文档](../README.md)
- [RAG 使用指南](../../docs/RAG_USAGE.md)
