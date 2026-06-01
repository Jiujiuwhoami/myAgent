# Terraform 最佳实践

## 代码组织

### 目录结构
```
terraform/
├── modules/           # 可复用模块
│   ├── vpc/
│   ├── ec2/
│   └── rds/
├── environments/      # 环境配置
│   ├── dev/
│   ├── staging/
│   └── prod/
├── backend.tf         # 后端配置
└── variables.tf       # 全局变量
```

## 状态管理

### 远程状态（推荐）
```hcl
terraform {
  backend "s3" {
    bucket = "my-terraform-state"
    key    = "prod/terraform.tfstate"
    region = "us-east-1"
  }
}
```

### 状态锁定
```hcl
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}
```

## 安全实践

1. **不要将状态文件提交到 Git**
2. **使用加密存储状态文件**
3. **限制状态文件访问权限**
4. **使用工作区隔离环境**

## 代码规范

### 命名约定
- 资源命名：`{project}_{component}_{env}`
- 变量命名：使用 snake_case
- 输出命名：使用 snake_case

### 注释规范
```hcl
# 描述资源用途
resource "aws_instance" "web_server" {
  # 生产环境 Web 服务器
  ami           = var.ami_id
  instance_type = "t3.medium"
}
```

## 常用命令

```bash
# 格式化
terraform fmt -recursive

# 验证
terraform validate

# 初始化
terraform init

# 计划
terraform plan -out=tfplan

# 应用
terraform apply tfplan

# 销毁
terraform destroy
```
