# Security Checklist

## 常见安全漏洞检查清单

### 🔐 注入攻击

- [ ] **SQL 注入** — 检查字符串拼接的 SQL 查询
  - 使用参数化查询或 ORM
  - 避免 `execute(f"SELECT * FROM users WHERE id = {user_id}")`
  
- [ ] **XSS (跨站脚本)** — 检查未转义的用户输入
  - 输出时进行 HTML 转义
  - 使用 Content Security Policy
  
- [ ] **命令注入** — 检查 `subprocess` 调用
  - 避免 `shell=True`
  - 使用参数列表而非字符串拼接

### 🔑 认证与授权

- [ ] **硬编码密钥** — 搜索硬编码的 API 密钥、密码
  - 使用环境变量或密钥管理服务
  - 检查 `.env` 文件是否被提交
  
- [ ] **弱密码策略** — 检查密码强度要求
  - 最小长度、复杂度要求
  - 密码哈希使用 bcrypt/argon2
  
- [ ] **会话管理** — 检查会话安全
  - 会话超时设置
  - 会话 ID 随机性

### 📁 文件安全

- [ ] **路径遍历** — 检查文件路径验证
  - 验证文件路径在预期目录内
  - 避免直接使用用户输入作为路径
  
- [ ] **文件上传** — 检查上传验证
  - 验证文件类型（MIME + 内容）
  - 限制文件大小
  - 存储在非 Web 可访问目录

### 🔒 数据安全

- [ ] **敏感数据泄露** — 检查日志中的敏感信息
  - 不记录密码、令牌、PII
  - 日志脱敏处理
  
- [ ] **加密传输** — 检查数据传输
  - 使用 HTTPS
  - 敏感数据加密存储

### 🛡️ 依赖安全

- [ ] **已知漏洞依赖** — 检查依赖漏洞
  - 运行 `npm audit` / `pip audit`
  - 更新有漏洞的依赖
  
- [ ] **依赖完整性** — 检查依赖锁定
  - 使用 package-lock.json / requirements.txt
  - 验证依赖哈希

## 快速扫描命令

```bash
# 使用 Semgrep 扫描安全漏洞
semgrep --config=auto .

# 使用 Bandit 扫描 Python 安全
bandit -r .

# 使用 Snyk 扫描依赖
snyk test
```

## 参考资源

- [OWASP Top 10](https://owasp.org/Top10/)
- [CWE/SANS Top 25](https://cwe.mitre.org/top25/)
- [Semgrep Rules](https://semgrep.dev/docs/)
