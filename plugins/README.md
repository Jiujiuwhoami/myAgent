# 插件化工具系统

## 架构对比

### 之前：工具混乱

```
myAgent/
├── tools/my_tools.py      # 硬编码工具列表
├── mcp/__init__.py         # MCP 协议实现
└── core/types.py           # 基础 Tool 类

问题：
- 两套工具定义（Tool vs MCPTool）
- 工具硬编码，无法动态增减
- 没有统一管理机制
```

### 现在：插件化架构

```
myAgent/
├── plugins/                    # 插件目录（热插拔）
│   ├── __init__.py            # 插件系统核心
│   ├── weather/               # 天气插件
│   │   ├── plugin.json        # 插件配置
│   │   └── __init__.py        # 插件实现
│   ├── calculator/            # 计算器插件
│   └── search/                # 搜索插件
└── config/
    └── tools.yaml             # 工具配置

优势：
- 工具即插件，独立于核心
- 配置化管理，支持启用/禁用
- 热加载，运行时增减工具
- 自动生成 MCP 格式 Schema
```

---

## 快速开始

### 1. 创建新插件

```python
# 方式一：使用脚手架
from myAgent.plugins import create_plugin_scaffold
create_plugin_scaffold("my_tool", "plugins")

# 方式二：手动创建
# plugins/my_tool/plugin.json
{
    "id": "my_tool",
    "name": "我的工具",
    "version": "1.0.0",
    "enabled": true
}

# plugins/my_tool/__init__.py
from myAgent.plugins import ToolPlugin, ToolMeta

class MyToolPlugin(ToolPlugin):
    @property
    def meta(self) -> ToolMeta:
        return ToolMeta(
            name="my_tool",
            description="工具描述"
        )
    
    async def execute(self, **kwargs):
        return {"result": "success"}
```

### 2. 使用插件

```python
from myAgent.plugins import PluginManager

manager = PluginManager("plugins")

# 发现插件
manager.discover()

# 加载插件
manager.load("weather")

# 调用工具
result = await manager.call_tool("weather", city="北京")

# 热插拔
manager.unload("weather")  # 卸载
manager.load("weather")    # 重载

# 获取 MCP Schema
schemas = manager.get_tools_schema()
```

---

## 核心类说明

### ToolPlugin - 插件基类

```python
class ToolPlugin:
    @property
    def meta(self) -> ToolMeta:
        """工具元数据"""
        
    async def execute(self, **kwargs) -> Any:
        """执行工具"""
        
    def validate_params(self, **kwargs) -> List[str]:
        """验证参数"""
        
    def to_mcp_format(self) -> dict:
        """转换为 MCP 格式"""
```

### PluginManager - 插件管理器

```python
class PluginManager:
    def discover(self) -> List[str]:
        """发现所有插件"""
        
    def load(self, plugin_id: str) -> bool:
        """加载插件"""
        
    def unload(self, plugin_id: str) -> bool:
        """卸载插件"""
        
    async def call_tool(self, name: str, **kwargs) -> Any:
        """调用工具"""
        
    def get_tools_schema(self) -> List[dict]:
        """获取 MCP Schema"""
```

---

## 与 MCP 协议集成

插件系统自动生成 MCP 格式的工具定义：

```python
# 获取所有工具的 MCP Schema
schemas = manager.get_tools_schema()

# 输出示例
[
    {
        "name": "weather",
        "description": "获取天气信息",
        "input_schema": {"type": "object", "properties": {}},
        "annotations": {
            "version": "1.0.0",
            "category": "utility"
        }
    }
]
```

---

## 配置管理

`config/tools.yaml`:

```yaml
plugins:
  weather:
    enabled: true
    config:
      default_city: "北京"
  
  calculator:
    enabled: true

rate_limits:
  default: 60
  search: 30
```

---

## 与 Claude Code / Codex 对比

| 特性 | Claude Code | Codex | 本系统 |
|------|-------------|-------|--------|
| 插件化 | ✅ | ✅ | ✅ |
| 热插拔 | ✅ | ✅ | ✅ |
| 配置管理 | ✅ | ✅ | ✅ |
| MCP 协议 | ✅ | ❌ | ✅ |
| 工具发现 | 自动 | 手动 | 自动 |
| 参数验证 | 内置 | 手动 | 内置 |

---

## 最佳实践

1. **一个插件一个功能域**
   ```
   weather/      # 天气相关
   search/       # 搜索相关
   calculator/   # 计算相关
   ```

2. **使用 plugin.json 配置**
   ```json
   {
       "id": "weather",
       "name": "天气查询",
       "enabled": true,
       "dependencies": ["http_client"]
   }
   ```

3. **实现参数验证**
   ```python
   def validate_params(self, **kwargs):
       errors = []
       if not kwargs.get("city"):
           errors.append("城市不能为空")
       return errors
   ```

4. **支持 MCP 协议**
   ```python
   def to_mcp_format(self):
       return {
           "name": self.meta.name,
           "description": self.meta.description,
           "input_schema": {...}
       }
   ```
