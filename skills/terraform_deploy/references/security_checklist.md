# Terraform 安全审查清单

## 前置检查

- [ ] 已配置远程状态后端（S3/GCS/Azure Blob）
- [ ] 状态文件已启用加密
- [ ] 已设置状态访问权限限制
- [ ] 已配置 Provider 版本约束

## 代码安全

- [ ] 无硬编码的敏感信息（密码、密钥、Token）
- [ ] 使用 `sensitive = true` 标记敏感输出
- [ ] 使用 `terraform.tfvars` 存储敏感变量（不提交到 Git）
- [ ] 使用 `aws_secretsmanager_secret_version` 引用密钥

## 网络安全

- [ ] 安全组规则最小化（仅开放必要端口）
- [ ] 使用私有子网部署敏感资源
- [ ] 配置 VPC Flow Logs
- [ ] 启用加密传输（HTTPS/TLS）

## 访问控制

- [ ] 使用 IAM Role 而非 Access Key
- [ ] 遵循最小权限原则
- [ ] 启用 MFA 删除保护
- [ ] 配置 CloudTrail 审计日志

## 部署安全

- [ ] 生产环境禁用 `auto_approve`
- [ ] 部署前审查 `terraform plan` 输出
- [ ] 使用 `terraform plan -out=tfplan` 保存计划
- [ ] 部署后验证资源状态

## 回滚准备

- [ ] 已创建备份/快照
- [ ] 已记录当前资源状态
- [ ] 已准备回滚脚本
- [ ] 已通知相关团队
