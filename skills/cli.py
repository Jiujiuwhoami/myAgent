"""技能管理 CLI 命令
支持：list, install, run, enable, disable, search, create
"""

import argparse
import sys
from pathlib import Path
from typing import Optional


def get_skill_manager(skill_dir: str = "skills") -> "SkillManager":
    """获取技能管理器实例"""
    from myAgent.skills import SkillManager

    home = Path.home() / ".hermes"
    return SkillManager(skill_dir=skill_dir, home_dir=str(home))


def cmd_list(args):
    """列出所有技能"""
    manager = get_skill_manager(args.skill_dir)
    manager.discover()

    if not manager.list_skills():
        print("未安装任何技能")
        print(f"技能目录: {manager.skill_dir}")
        print("使用: myagent skill create <name> 创建新技能")
        return

    # 按分类展示
    categories = {}
    for info in manager._skills.values():
        cat = info.config.meta.category
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(info)

    for cat_name, skills in sorted(categories.items()):
        print(f"\n📂 {cat_name.value.upper()} ({len(skills)} 个)")
        for info in sorted(skills, key=lambda s: s.config.meta.name):
            status = "✅" if info.status.value == "enabled" else "⏸️"
            version = info.config.meta.version
            desc = info.config.meta.description[:50]
            print(f"   {status} {info.config.meta.name} v{version}")
            print(f"      {desc}...")
            if info.usage_count > 0:
                print(f"      使用 {info.usage_count} 次")


def cmd_create(args):
    """创建新技能"""
    from myAgent.skills import create_skill_scaffold

    category = args.category or "custom"
    path = create_skill_scaffold(
        skill_name=args.name, output_dir=args.output_dir or "skills", category=category
    )
    print("\n下一步:")
    print(f"  1. 编辑 {path}/skill.json 配置参数")
    print(f"  2. 编辑 {path}/skill.py 实现 run() 方法")
    print("  3. 运行: myagent skill list 查看技能")


def cmd_run(args):
    """运行技能"""
    import asyncio

    manager = get_skill_manager(args.skill_dir)
    manager.discover()

    if not manager.load(args.name):
        print(f"❌ 无法加载技能: {args.name}")
        print(f"可用技能: {', '.join(manager.list_skills())}")
        return

    # 解析参数
    kwargs = {}
    if args.params:
        for p in args.params:
            if "=" in p:
                key, value = p.split("=", 1)
                # 尝试类型转换
                if value.lower() == "true":
                    kwargs[key] = True
                elif value.lower() == "false":
                    kwargs[key] = False
                else:
                    try:
                        kwargs[key] = int(value)
                    except ValueError:
                        try:
                            kwargs[key] = float(value)
                        except ValueError:
                            kwargs[key] = value

    result = asyncio.run(manager.run_skill(args.name, **kwargs))

    if result.get("success"):
        print("✅ 技能执行成功")
        if "data" in result:
            import json

            print(json.dumps(result["data"], indent=2, ensure_ascii=False))
    else:
        print(f"❌ 技能执行失败: {result.get('error')}")
        if "details" in result:
            for detail in result["details"]:
                print(f"   - {detail}")


def cmd_enable(args):
    """启用技能"""
    manager = get_skill_manager(args.skill_dir)
    manager.discover()

    if manager.enable(args.name):
        print(f"✅ 已启用技能: {args.name}")
    else:
        print(f"❌ 无法启用技能: {args.name}")


def cmd_disable(args):
    """禁用技能"""
    manager = get_skill_manager(args.skill_dir)
    manager.discover()

    if manager.disable(args.name):
        print(f"⏸️ 已禁用技能: {args.name}")
    else:
        print(f"❌ 无法禁用技能: {args.name}")


def cmd_search(args):
    """搜索技能注册中心"""
    manager = get_skill_manager(args.skill_dir)
    results = manager.search_hub(args.query)

    if not results:
        print("未找到匹配的技能")
        return

    print(f"搜索 '{args.query}' 找到 {len(results)} 个技能:\n")
    for skill in results:
        print(f"📦 {skill.get('name', 'unknown')} v{skill.get('version', '?')}")
        print(f"   {skill.get('description', '')}")
        print(f"   分类: {skill.get('category', '?')} | 作者: {skill.get('author', '?')}")
        if skill.get("source_url"):
            print(f"   源码: {skill.get('source_url')}")
        print()


def cmd_install(args):
    """从注册中心安装技能"""
    manager = get_skill_manager(args.skill_dir)

    if manager.install_from_hub(args.name):
        print(f"✅ 技能已安装: {args.name}")
        print(f"使用: myagent skill run {args.name} 运行技能")
    else:
        print(f"❌ 安装失败: {args.name}")


def cmd_status(args):
    """显示技能系统状态"""
    manager = get_skill_manager(args.skill_dir)
    manager.print_status()


def cmd_export(args):
    """导出技能 schema（用于 LLM 工具调用）"""
    import json

    manager = get_skill_manager(args.skill_dir)
    manager.discover()

    # 加载所有启用的技能
    for name in manager.list_skills():
        info = manager.get_skill_info(name)
        if info and info.config.enabled:
            manager.load(name)

    schemas = manager.get_tools_schema()

    output_file = args.output or None
    if output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(schemas, f, indent=2, ensure_ascii=False)
        print(f"✅ Schema 已导出到: {output_file}")
    else:
        print(json.dumps(schemas, indent=2, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 解析器"""
    parser = argparse.ArgumentParser(prog="myagent skill", description="myAgent 技能管理系统")

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # list
    p_list = subparsers.add_parser("list", help="列出所有技能")
    p_list.add_argument("--skill-dir", default="skills", help="技能目录")
    p_list.set_defaults(func=cmd_list)

    # create
    p_create = subparsers.add_parser("create", help="创建新技能")
    p_create.add_argument("name", help="技能名称")
    p_create.add_argument(
        "--category",
        choices=["devops", "development", "data", "research", "automation", "security", "custom"],
        help="技能分类",
    )
    p_create.add_argument("--output-dir", default="skills", help="输出目录")
    p_create.set_defaults(func=cmd_create)

    # run
    p_run = subparsers.add_parser("run", help="运行技能")
    p_run.add_argument("name", help="技能名称")
    p_run.add_argument("--skill-dir", default="skills", help="技能目录")
    p_run.add_argument("--params", nargs="*", help="参数 key=value 对")
    p_run.set_defaults(func=cmd_run)

    # enable
    p_enable = subparsers.add_parser("enable", help="启用技能")
    p_enable.add_argument("name", help="技能名称")
    p_enable.add_argument("--skill-dir", default="skills", help="技能目录")
    p_enable.set_defaults(func=cmd_enable)

    # disable
    p_disable = subparsers.add_parser("disable", help="禁用技能")
    p_disable.add_argument("name", help="技能名称")
    p_disable.add_argument("--skill-dir", default="skills", help="技能目录")
    p_disable.set_defaults(func=cmd_disable)

    # search
    p_search = subparsers.add_parser("search", help="搜索技能注册中心")
    p_search.add_argument("query", help="搜索关键词")
    p_search.add_argument(
        "--hub-url", default="https://skills.hermes-agent.io", help="注册中心 URL"
    )
    p_search.set_defaults(func=cmd_search)

    # install
    p_install = subparsers.add_parser("install", help="从注册中心安装技能")
    p_install.add_argument("name", help="技能名称或 ID")
    p_install.add_argument("--skill-dir", default="skills", help="技能目录")
    p_install.add_argument(
        "--hub-url", default="https://skills.hermes-agent.io", help="注册中心 URL"
    )
    p_install.set_defaults(func=cmd_install)

    # status
    p_status = subparsers.add_parser("status", help="显示技能系统状态")
    p_status.add_argument("--skill-dir", default="skills", help="技能目录")
    p_status.set_defaults(func=cmd_status)

    # export
    p_export = subparsers.add_parser("export", help="导出技能 schema")
    p_export.add_argument("--output", "-o", help="输出文件路径")
    p_export.add_argument("--skill-dir", default="skills", help="技能目录")
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
