#!/bin/bash
# Terraform 代码验证脚本

set -e

WORK_DIR="${1:-.}"

echo "🔍 验证 Terraform 代码: $WORK_DIR"

# 检查 terraform 是否安装
if ! command -v terraform &> /dev/null; then
    echo "❌ Terraform 未安装"
    exit 1
fi

cd "$WORK_DIR"

# 1. 格式化检查
echo "📝 检查代码格式..."
if terraform fmt -check -recursive; then
    echo "  ✅ 代码格式正确"
else
    echo "  ⚠️ 代码格式不规范，建议运行: terraform fmt -recursive"
fi

# 2. 初始化
echo "📦 初始化 Terraform..."
terraform init -backend=false -input=false

# 3. 验证配置
echo "✅ 验证配置..."
if terraform validate; then
    echo "  ✅ 配置验证通过"
else
    echo "  ❌ 配置验证失败"
    exit 1
fi

echo ""
echo "✅ Terraform 代码验证完成"
