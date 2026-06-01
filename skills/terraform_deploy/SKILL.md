# Terraform 部署技能

## 概述

自动化基础设施部署技能，支持 Terraform 代码验证、计划生成和实际部署。

## 使用场景

- 部署云基础设施（AWS、Azure、GCP）
- 管理 Kubernetes 集群
- 配置网络和安全组
- 部署微服务架构

## 工作流程

```
1. 验证 Terraform 代码格式
2. 运行 terraform init
3. 生成执行计划 (terraform plan)
4. 审查计划变更
5. 执行部署 (terraform apply)
6. 输出部署状态
```

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `working_dir` | string | 是 | Terraform 代码目录 |
| `auto_approve` | boolean | 否 | 自动批准部署（默认 false） |
| `target_resource` | string | 否 | 指定部署的资源 |
| `var_file` | string | 否 | 变量文件路径 |

## 安全注意事项

⚠️ **生产环境部署需要人工确认**

- 始终先运行 `terraform plan` 审查变更
- 使用 `auto_approve=false` 进行生产部署
- 确保有回滚方案
- 记录部署日志

## References

- [Terraform Best Practices](references/terraform_best_practices.md)
- [Security Checklist](references/security_checklist.md)

## Scripts

- `scripts/validate_tf.sh` - Terraform 代码验证
- `scripts/plan_summary.py` - 计划摘要生成
