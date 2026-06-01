"""
智能客服 SaaS - myAgent 集成示例
================================

快速启动：
    python examples/customer_service_demo.py
"""

import asyncio
from myAgent.backend.seller_engine import SellerEngine
from myAgent.customer_service.model_config import ModelConfig, ModelSource, ModelProvider
from myAgent.skills.customer_service.skill import OrderQuerySkill, FAQSkill
from myAgent.mcp.shopify_integration import ShopifyOrderTool


async def main():
    # 1. 初始化模型配置（用户自带 API）
    model_config = ModelConfig(
        source=ModelSource.USER_PROVIDED,
        provider=ModelProvider.OPENAI,
        model_name="gpt-4o",
        api_key="sk-xxx",  # 从环境变量读取更安全
        temperature=0.7,
        max_tokens=2048,
    )
    
    # 2. 创建 SellerEngine
    engine = SellerEngine(
        seller_id="seller_001",
        model_config=model_config
    )
    
    # 3. 注册业务 Skill
    engine.register_skill(OrderQuerySkill())
    engine.register_skill(FAQSkill())
    
    # 4. 注册 MCP 工具
    engine.register_mcp_tool(ShopifyOrderTool(api_key="shopify_xxx"))
    
    # 5. 处理客服查询
    query = "我的订单什么时候发货？订单号是 12345"
    response = await engine.handle_query(query)
    
    print(f"用户: {query}")
    print(f"客服: {response}")


if __name__ == "__main__":
    asyncio.run(main())
