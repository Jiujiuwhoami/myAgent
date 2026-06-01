"""Terraform 部署技能 - 自动化基础设施部署"""

import asyncio
from typing import Any, Dict


async def run(command: str, cwd: str = None) -> Dict[str, Any]:
    """执行命令"""
    result = await asyncio.create_subprocess_shell(
        command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=cwd
    )
    stdout, stderr = await result.communicate()
    return {"returncode": result.returncode, "stdout": stdout.decode(), "stderr": stderr.decode()}


async def validate_terraform(working_dir: str) -> Dict[str, Any]:
    """验证 Terraform 代码"""
    # 格式化检查
    fmt_result = await run("terraform fmt -check -recursive", cwd=working_dir)
    if fmt_result["returncode"] != 0:
        return {"valid": False, "error": "Terraform 代码格式不规范，请运行 terraform fmt"}

    # 初始化
    init_result = await run("terraform init", cwd=working_dir)
    if init_result["returncode"] != 0:
        return {"valid": False, "error": f"Terraform init 失败: {init_result['stderr']}"}

    # 验证配置
    validate_result = await run("terraform validate", cwd=working_dir)
    if validate_result["returncode"] != 0:
        return {"valid": False, "error": f"Terraform validate 失败: {validate_result['stderr']}"}

    return {"valid": True, "message": "Terraform 代码验证通过"}


async def generate_plan(working_dir: str, var_file: str = None) -> Dict[str, Any]:
    """生成执行计划"""
    cmd = "terraform plan"
    if var_file:
        cmd += f" -var-file={var_file}"

    result = await run(cmd, cwd=working_dir)
    if result["returncode"] != 0:
        return {"success": False, "error": result["stderr"]}

    return {"success": True, "plan": result["stdout"]}


async def apply_deployment(
    working_dir: str, auto_approve: bool = False, target_resource: str = None, var_file: str = None
) -> Dict[str, Any]:
    """执行部署"""
    cmd = "terraform apply"
    if auto_approve:
        cmd += " -auto-approve"
    if target_resource:
        cmd += f" -target={target_resource}"
    if var_file:
        cmd += f" -var-file={var_file}"

    result = await run(cmd, cwd=working_dir)
    if result["returncode"] != 0:
        return {"success": False, "error": result["stderr"]}

    return {"success": True, "output": result["stdout"]}


async def run(
    working_dir: str,
    auto_approve: bool = False,
    target_resource: str = None,
    var_file: str = None,
    **kwargs,
) -> Dict[str, Any]:
    """
    Terraform 部署技能主函数

    Args:
        working_dir: Terraform 代码目录
        auto_approve: 是否自动批准
        target_resource: 指定资源
        var_file: 变量文件

    Returns:
        部署结果
    """
    results = {"working_dir": working_dir, "steps": []}

    # 步骤 1: 验证
    print("📋 步骤 1: 验证 Terraform 代码...")
    validation = await validate_terraform(working_dir)
    results["steps"].append({"name": "validate", "result": validation})
    if not validation["valid"]:
        results["success"] = False
        results["error"] = validation["error"]
        return results

    # 步骤 2: 生成计划
    print("📋 步骤 2: 生成执行计划...")
    plan = await generate_plan(working_dir, var_file)
    results["steps"].append({"name": "plan", "result": plan})
    if not plan["success"]:
        results["success"] = False
        results["error"] = plan["error"]
        return results

    # 步骤 3: 执行部署
    print("📋 步骤 3: 执行部署...")
    if auto_approve:
        print("⚠️ 警告: 自动批准模式，生产环境请谨慎使用")

    apply_result = await apply_deployment(working_dir, auto_approve, target_resource, var_file)
    results["steps"].append({"name": "apply", "result": apply_result})

    if apply_result["success"]:
        results["success"] = True
        results["message"] = "部署成功"
    else:
        results["success"] = False
        results["error"] = apply_result["error"]

    return results
