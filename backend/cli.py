#!/usr/bin/env python3
"""多用户后端引擎 - 主入口

运行方式:
    python -m myAgent.server --host 0.0.0.0 --port 8000

环境变量:
    AGENT_DB_PATH          - 数据库路径 (默认: agent_engine.db)
    AGENT_MAX_WORKERS      - 最大工作线程数 (默认: 10)
    AGENT_LLM_BASE_URL     - LLM 地址
    AGENT_LLM_MODEL        - LLM 模型名
    JWT_SECRET_KEY         - JWT 密钥 (默认: 随机生成)
"""

import argparse
import asyncio
import os
import sys

# 自动加载 .env 文件
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv 未安装则跳过

# 确保可以找到模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(current_dir)
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)


def create_engine():
    """创建后端引擎"""
    from myAgent.llm.client import LLMConfig
    from backend.engine import MultiUserEngine

    db_path = os.getenv("AGENT_DB_PATH", "agent_engine.db")
    max_workers = int(os.getenv("AGENT_MAX_WORKERS", "10"))
    jwt_secret = os.getenv("JWT_SECRET_KEY", None)

    llm_config = LLMConfig.from_env()

    engine = MultiUserEngine(
        db_path=db_path,
        max_workers=max_workers,
        llm_config=llm_config,
        jwt_secret_key=jwt_secret,
    )

    return engine


def run_server(host: str = "0.0.0.0", port: int = 8000, debug: bool = False):
    """运行 API 服务器"""
    import uvicorn
    from backend.engine import MultiUserEngine
    from backend.server import create_app

    engine = create_engine()
    _global_engine = engine

    # 创建应用
    app = create_app(engine)

    # 启动后台引擎
    async def start_server():
        await engine.start()
        config = uvicorn.Config(app, host=host, port=port, log_level="info" if not debug else "debug")
        server = uvicorn.Server(config)
        await server.serve()

    print("\n🚀 Agent Runtime API Server")
    print(f"   地址: http://{host}:{port}")
    print(f"   文档: http://{host}:{port}/docs")
    print(f"   健康: http://{host}:{port}/api/v1/health")
    print(f"\n   数据库: {os.getenv('AGENT_DB_PATH', 'agent_engine.db')}")
    print(f"   工作线程: {os.getenv('AGENT_MAX_WORKERS', '10')}")
    print("   JWT 认证: 已启用")
    print(f"   LLM: {os.getenv('LLM_MODEL', 'Qwen/Qwen3-4B-GGUF:Q4_K_M')}")
    print("\n" + "=" * 60)

    asyncio.run(start_server())


def run_demo():
    """运行本地演示（无服务器）"""
    import asyncio

    from backend.engine import UserRole

    async def demo():
        print("\n" + "=" * 60)
        print("🤖 多用户后端引擎 - 本地演示")
        print("   (JWT 认证 + 权限校验增强版)")
        print("=" * 60)

        # 创建引擎
        engine = create_engine()

        # 启动后台处理
        await engine.start()

        # 创建测试用户
        print("\n📝 创建测试用户...")
        user1 = engine.register_user("alice", "password123", UserRole.USER, max_concurrent=3)
        user2 = engine.register_user("bob", "password123", UserRole.USER, max_concurrent=2)
        admin = engine.register_user("admin", "admin123", UserRole.ADMIN, max_concurrent=10)

        print(f"   ✅ 用户: {user1.username} (ID: {user1.id[:8]}...)")
        print(f"   ✅ 用户: {user2.username} (ID: {user2.id[:8]}...)")
        print(f"   ✅ 用户: {admin.username} (ID: {admin.id[:8]}...)")

        # 用户登录（JWT Token）
        print("\n🔐 用户登录（JWT 认证）...")
        token1 = engine.login("alice", "password123")
        token2 = engine.login("bob", "password123")
        token_admin = engine.login("admin", "admin123")

        user1_obj = engine.get_current_user(token1)
        user2_obj = engine.get_current_user(token2)
        admin_obj = engine.get_current_user(token_admin)

        print(f"   ✅ Alice 登录: token={token1[:16]}...")
        print(f"   ✅ Bob 登录: token={token2[:16]}...")
        print(f"   ✅ Admin 登录: token={token_admin[:16]}...")

        # 验证 JWT Token
        print("\n🔍 验证 JWT Token...")
        decoded1 = engine.decode_jwt_token(token1)
        print(
            f"   Alice Token 解析: user_id={decoded1.user_id[:8]}..., username={decoded1.username}, role={decoded1.role}"
        )

        # 提交任务
        print("\n📋 提交任务...")

        task1 = await engine.submit_task(
            user_id=user1_obj.id,
            task_name="Alice 的任务",
            input_data={"message": "Hello Alice"},
            priority=engine.TaskPriority.NORMAL,
        )
        print(f"   ✅ 任务 1: {task1.id[:8]}... (用户: {task1.user_id[:8]}...)")

        task2 = await engine.submit_task(
            user_id=user2_obj.id,
            task_name="Bob 的任务",
            input_data={"message": "Hello Bob"},
            priority=engine.TaskPriority.HIGH,
        )
        print(f"   ✅ 任务 2: {task2.id[:8]}... (用户: {task2.user_id[:8]}...)")

        # 等待任务完成
        print("\n⏳ 等待任务完成...")
        await asyncio.sleep(2)

        # 查询任务状态（带权限校验）
        print("\n📊 任务状态查询（权限校验）:")

        # Alice 查询自己的任务 - 成功
        status1 = await engine.get_task_status(task1.id, user1_obj.id)
        print(
            f"   Alice 查询自己的任务: {'✅ 成功' if status1 else '❌ 失败'} - {status1.state.value if status1 else 'N/A'}"
        )

        # Alice 查询 Bob 的任务 - 失败（权限不足）
        status2_from_alice = await engine.get_task_status(task2.id, user1_obj.id)
        print(
            f"   Alice 查询 Bob 的任务: {'✅ 成功' if status2_from_alice else '❌ 失败（权限不足）'}"
        )

        # Admin 查询 Bob 的任务 - 成功（管理员权限）
        status2_from_admin = await engine.get_task_status(task2.id, admin_obj.id)
        print(
            f"   Admin 查询 Bob 的任务: {'✅ 成功' if status2_from_admin else '❌ 失败'} - {status2_from_admin.state.value if status2_from_admin else 'N/A'}"
        )

        # 跨用户取消任务（权限校验）
        print("\n🚫 跨用户操作权限测试:")

        # Alice 取消自己的任务 - 成功
        cancel1 = await engine.cancel_task(task1.id, user1_obj.id)
        print(f"   Alice 取消自己的任务: {'✅ 成功' if cancel1 else '❌ 失败'}")

        # Alice 取消 Bob 的任务 - 失败
        cancel2 = await engine.cancel_task(task2.id, user1_obj.id)
        print(f"   Alice 取消 Bob 的任务: {'✅ 成功' if cancel2 else '❌ 失败（权限不足）'}")

        # Admin 取消 Bob 的任务 - 成功
        cancel3 = await engine.cancel_task(task2.id, admin_obj.id)
        print(f"   Admin 取消 Bob 的任务: {'✅ 成功' if cancel3 else '❌ 失败'}")

        # 统计
        print("\n📈 系统统计:")
        stats = engine.get_stats()
        print(f"   活跃工作线程: {stats['active_workers']}")
        print(f"   队列大小: {stats['queue_size']}")
        print(f"   引擎运行: {stats['is_running']}")

        # 停止引擎
        await engine.stop()

        print("\n" + "=" * 60)
        print("✅ 演示完成!")
        print("=" * 60)

    asyncio.run(demo())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agent Runtime 多用户后端引擎")
    parser.add_argument(
        "--mode",
        choices=["server", "demo"],
        default="demo",
        help="运行模式: server(服务器) 或 demo(本地演示)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="服务器地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--debug", action="store_true", help="调试模式")

    args = parser.parse_args()

    if args.mode == "server":
        run_server(host=args.host, port=args.port, debug=args.debug)
    else:
        run_demo()
