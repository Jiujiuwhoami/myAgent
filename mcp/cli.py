"""MCP 工具管理 CLI 命令

支持：list, register, unregister, create, server
"""

import argparse
import sys
from pathlib import Path
from typing import Optional


def get_mcp_manager() -> "MCPManager":
    """获取 MCP 管理器实例"""
    from myAgent.mcp import MCPManager

    return MCPManager()


def cmd_list(args):
    """列出所有 MCP 工具"""
    manager = get_mcp_manager()
    tools = manager.list_tools()

    if not tools:
        print("未注册任何 MCP 工具")
        print("使用: myagent mcp create <name> 创建新工具")
        return

    print(f"\n📦 MCP 工具 ({len(tools)} 个)\n")
    for tool in tools:
        status = "✅" if tool.get("enabled", True) else "⏸️"
        name = tool.get("name", "unknown")
        desc = tool.get("description", "")[:50]
        print(f"   {status} {name}")
        print(f"      {desc}...")
        print(f"      参数: {', '.join(tool.get('parameters', {}).keys())}")
        print()


def cmd_create(args):
    """创建 MCP 工具模板"""
    from myAgent.mcp import create_mcp_tool_template

    path = create_mcp_tool_template(
        tool_name=args.name,
        output_dir=args.output_dir or "mcp_tools",
        description=args.description or "自定义 MCP 工具",
    )
    print(f"\n✅ MCP 工具模板已创建: {path}")
    print("\n下一步:")
    print(f"  1. 编辑 {path} 实现工具逻辑")
    print("  2. 使用 @create_mcp_tool 装饰器注册")
    print("  3. 运行: myagent mcp list 查看工具")


def cmd_register(args):
    """注册 MCP 工具"""
    from myAgent.mcp import register_tool

    # 从文件导入工具
    tool_path = Path(args.tool_file)
    if not tool_path.exists():
        print(f"❌ 工具文件不存在: {tool_path}")
        return

    # 动态导入
    import importlib.util

    spec = importlib.util.spec_from_file_location("mcp_tool", tool_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # 查找工具函数
    tool = None
    if hasattr(module, "tool"):
        tool = module.tool
    elif hasattr(module, "get_tool"):
        tool = module.get_tool()

    if not tool:
        print("❌ 工具文件中未找到 'tool' 或 'get_tool()'")
        return

    register_tool(tool)
    print(f"✅ 工具已注册: {tool.name}")


def cmd_unregister(args):
    """注销 MCP 工具"""
    from myAgent.mcp import unregister_tool

    success = unregister_tool(args.name)
    if success:
        print(f"✅ 工具已注销: {args.name}")
    else:
        print(f"❌ 工具不存在: {args.name}")


def cmd_server(args):
    """启动 MCP 服务器"""
    from myAgent.mcp import MCPServer, get_registered_tools

    server = MCPServer(name=args.name or "MyAgent MCP Server")

    # 注册所有工具
    tools = get_registered_tools()
    for tool in tools:
        server.register(tool)

    print("\n🚀 MCP 服务器已启动")
    print(f"   名称: {server.name}")
    print(f"   工具数: {len(tools)}")
    print("\n   可用工具:")
    for tool in tools:
        print(f"     - {tool.name}: {tool.description[:40]}...")

    if args.listen:
        print(f"\n   监听: {args.listen}")
        # 这里可以添加 SSE 或 stdio 服务器实现
        server.start()


def cmd_export(args):
    """导出 MCP 工具 schema"""
    import json

    from myAgent.mcp import get_registered_tools

    tools = get_registered_tools()
    schemas = [
        {
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
        }
        for t in tools
    ]

    output_file = args.output or None
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(schemas, f, indent=2, ensure_ascii=False)
        print(f"✅ Schema 已导出到: {output_file}")
    else:
        print(json.dumps(schemas, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 解析器"""
    parser = argparse.ArgumentParser(prog="myagent mcp", description="myAgent MCP 工具管理系统")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    p_list = subparsers.add_parser("list", help="列出所有 MCP 工具")
    p_list.set_defaults(func=cmd_list)

    # create
    p_create = subparsers.add_parser("create", help="创建 MCP 工具模板")
    p_create.add_argument("name", help="工具名称")
    p_create.add_argument("--output-dir", default="mcp_tools", help="输出目录")
    p_create.add_argument("--description", help="工具描述")
    p_create.set_defaults(func=cmd_create)

    # register
    p_register = subparsers.add_parser("register", help="注册 MCP 工具")
    p_register.add_argument("tool_file", help="工具文件路径")
    p_register.set_defaults(func=cmd_register)

    # unregister
    p_unregister = subparsers.add_parser("unregister", help="注销 MCP 工具")
    p_unregister.add_argument("name", help="工具名称")
    p_unregister.set_defaults(func=cmd_unregister)

    # server
    p_server = subparsers.add_parser("server", help="启动 MCP 服务器")
    p_server.add_argument("--name", help="服务器名称")
    p_server.add_argument("--listen", help="监听地址")
    p_server.set_defaults(func=cmd_server)

    # export
    p_export = subparsers.add_parser("export", help="导出 MCP 工具 schema")
    p_export.add_argument("--output", "-o", help="输出文件路径")
    p_export.set_defaults(func=cmd_export)

    return parser


def main(args: Optional[list] = None):
    """CLI 入口"""
    parser = build_parser()
    parsed = parser.parse_args(args)

    if not parsed.command:
        parser.print_help()
        return 1

    try:
        parsed.func(parsed)
        return 0
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
