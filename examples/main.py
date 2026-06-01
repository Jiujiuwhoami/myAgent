"""myAgent 运行入口 - 手动运行演示

用法:
    python -m myAgent.examples.main --mode simple    # 简单验证
    python -m myAgent.examples.main --mode llm       # LLM 智能代理
    python -m myAgent.examples.main --mode llm_full  # LLM + 技能 + 记忆（增强版）
    python -m myAgent.examples.main --mode runtime   # 完整 Agent Runtime
"""

import os
import sys

# 确保项目根目录在路径中
project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

import asyncio

from myAgent.core.dag import DAG, DAGNode
from myAgent.core.memory import MemoryOS
from myAgent.llm.agent import create_agent
from myAgent.llm.client import LLMClient, LLMConfig, Message
from myAgent.runtime.agent_runtime import AgentRuntime, RuntimeConfig
from myAgent.skills import SkillManager


async def run_simple_demo():
    """运行简单演示 - 验证核心组件"""
    print("=" * 60)
    print("🚀 myAgent 简单演示")
    print("=" * 60)

    # 1. 测试 LLM 连接
    print("\n1️⃣ 测试本地 LLM...")
    config = LLMConfig(
        base_url="http://192.168.3.191:8080/v1", model="Qwen/Qwen3-4B-GGUF:Q4_K_M", timeout=120.0
    )
    llm = LLMClient(config)

    if llm.health_check():
        print("   ✅ LLM 服务正常")
    else:
        print("   ❌ LLM 服务不可用")
        return

    # 2. 测试技能系统
    print("\n2️⃣ 测试技能系统...")
    skill_mgr = SkillManager(skill_dir="myAgent/skills")
    skills = skill_mgr.discover()
    print(f"   ✅ 发现 {len(skills)} 个技能: {skills}")

    # 3. 测试 DAG
    print("\n3️⃣ 测试 DAG 调度器...")
    dag = DAG(name="test")
    dag.add_node(DAGNode(id="a", name="任务 A"))
    dag.add_node(DAGNode(id="b", name="任务 B"))
    dag.add_edge("a", "b")
    print(f"   ✅ DAG 节点：{dag.node_count}, 执行顺序：{dag.topological_sort()}")

    # 4. 简单对话
    print("\n4️⃣ 简单对话测试...")
    response = llm.chat(
        messages=[Message(role="user", content="你好，简短介绍你自己")], timeout=120
    )
    print(f"   🤖 {response.content[:100]}...")

    print("\n✅ 演示完成!")


async def run_llm_agent_demo():
    """运行 LLM 智能代理演示 - 轻量级"""
    print("=" * 60)
    print("🤖 myAgent - LLM 智能代理（轻量版）")
    print("=" * 60)

    config = LLMConfig(
        base_url="http://192.168.3.191:8080/v1", model="Qwen/Qwen3-4B-GGUF:Q4_K_M", timeout=120.0
    )

    print(f"\n📡 LLM: {config.model}")
    print(f"   地址: {config.base_url}")

    llm = LLMClient(config)
    if not llm.health_check():
        print("   ❌ LLM 服务不可用")
        return

    print("   ✅ LLM 服务正常")

    # 创建 Agent（轻量版，无技能/记忆）
    print("\n🤖 创建智能代理...")
    agent = await create_agent(
        name="本地智能代理",
        llm_config=config,
        max_steps=3,
    )

    # 演示对话
    print("\n📝 对话演示:")
    result = await agent.run("你好，用一句话介绍你自己")
    print(f"   🤖 {result[:200]}...")

    await agent.close()
    print("\n✅ 演示完成!")


async def run_llm_full_demo():
    """运行 LLM 智能代理演示 - 完整版（含技能 + 记忆）"""
    print("=" * 60)
    print("🤖 myAgent - LLM 智能代理（完整版）")
    print("=" * 60)

    config = LLMConfig(
        base_url="http://192.168.3.191:8080/v1", model="Qwen/Qwen3-4B-GGUF:Q4_K_M", timeout=120.0
    )

    print(f"\n📡 LLM: {config.model}")
    print(f"   地址: {config.base_url}")

    llm = LLMClient(config)
    if not llm.health_check():
        print("   ❌ LLM 服务不可用")
        return

    print("   ✅ LLM 服务正常")

    # 创建完整记忆系统
    print("\n🧠 初始化记忆系统...")
    memory = MemoryOS()
    memory.semantic.add_knowledge("agent", "name", "本地智能代理")
    memory.semantic.add_knowledge("agent", "version", "2.1.0")
    print("   ✅ 记忆系统已初始化")

    # 创建技能管理器
    print("\n🔧 加载技能系统...")
    skill_mgr = SkillManager(skill_dir="myAgent/skills")
    skills = skill_mgr.discover()
    print(f"   ✅ 加载 {len(skills)} 个技能: {skills}")

    # 创建 Agent
    print("\n🤖 创建智能代理...")
    agent = await create_agent(
        name="本地智能代理",
        llm_config=config,
        max_steps=5,
    )

    # 演示带记忆的对话
    print("\n📝 对话演示（带记忆）:")

    # 写入工作记忆
    memory.working.write("current_task", "代码审查")
    memory.working.write("user_name", "测试用户")

    # 执行对话
    result = await agent.run("你好，我正在进行代码审查任务")
    print(f"   🤖 {result[:200]}...")

    # 读取记忆
    print("\n📚 记忆查询:")
    print(f"   当前任务: {memory.working.read('current_task')}")
    print(f"   用户名称: {memory.working.read('user_name')}")

    await agent.close()
    print("\n✅ 演示完成!")


async def run_runtime_demo():
    """运行传统 Runtime 演示"""
    print("=" * 60)
    print("🤖 myAgent - Agent Runtime")
    print("=" * 60)

    config = RuntimeConfig(name="myAgent Runtime")
    runtime = AgentRuntime(config)
    print(f"\n✅ Runtime 创建成功: {config.name}")

    # 添加记忆
    runtime.memory.semantic.add_knowledge(
        "myAgent", "这是一个从零构建的 Agent 运行时系统", category="architecture"
    )
    print("   ✅ 知识库已初始化")

    # 执行简单任务
    print("\n📝 执行任务...")
    task = runtime.create_task("测试任务", input_data={"name": "测试"})
    print(f"   任务 ID: {task.id}")
    print(f"   状态: {task.status}")

    print("\n✅ Runtime 演示完成!")
    runtime.print_status()


async def run_all():
    """运行所有演示"""
    await run_simple_demo()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="myAgent 运行入口")
    parser.add_argument(
        "--mode", choices=["simple", "llm", "llm_full", "runtime", "all"], default="simple"
    )
    args = parser.parse_args()

    if args.mode == "llm":
        asyncio.run(run_llm_agent_demo())
    elif args.mode == "llm_full":
        asyncio.run(run_llm_full_demo())
    elif args.mode == "runtime":
        asyncio.run(run_runtime_demo())
    else:
        asyncio.run(run_all())
