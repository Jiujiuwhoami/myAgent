"""插件系统使用示例

演示如何：
1. 发现和加载插件
2. 调用工具
3. 热插拔管理
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from myAgent.plugins import PluginManager, create_plugin_scaffold


async def main():
    print("=" * 60)
    print("插件系统演示")
    print("=" * 60)

    plugin_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins"
    )
    manager = PluginManager(plugin_dir)

    print("\n1. 发现插件...")
    discovered = manager.discover()
    print(f"   发现 {len(discovered)} 个插件: {discovered}")

    print("\n2. 加载所有插件...")
    for plugin_id in discovered:
        manager.load(plugin_id)

    print("\n3. 列出所有工具...")
    tools = manager.list_tools()
    print(f"   可用工具: {tools}")

    print("\n4. 调用工具...")

    result = await manager.call_tool("weather", city="上海")
    print(f"   天气查询: {result}")

    result = await manager.call_tool("calculate", expression="2**10 + 100")
    print(f"   计算: {result}")

    result = await manager.call_tool("web_search", query="Python 教程", limit=3)
    print(f"   搜索: {result}")

    print("\n5. 获取工具 Schema (MCP 格式)...")
    schemas = manager.get_tools_schema()
    for schema in schemas[:2]:
        print(f"   - {schema['name']}: {schema['description']}")

    print("\n6. 热插拔演示...")
    print("   卸载 weather 插件...")
    manager.unload("weather")
    print(f"   剩余工具: {manager.list_tools()}")

    print("   重新加载 weather 插件...")
    manager.load("weather")
    print(f"   当前工具: {manager.list_tools()}")

    print("\n7. 插件状态...")
    status = manager.to_dict()
    print(f"   总插件数: {status['total_plugins']}")
    print(f"   总工具数: {status['total_tools']}")

    print("\n8. 创建新插件脚手架...")
    create_plugin_scaffold("my_custom_tool", plugin_dir)

    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
