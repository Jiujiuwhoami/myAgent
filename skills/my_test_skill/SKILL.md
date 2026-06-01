# My Test Skill

## 描述

测试自定义技能

## 使用场景

当需要执行以下操作时，此技能将被自动触发：

- 示例任务 1
- 示例任务 2
- 示例任务 3

## 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| param1 | str | 否 | 参数 1 说明 |
| param2 | int | 否 | 参数 2 说明 |

## 示例

```python
# 在 skill.py 中实现
async def run(**kwargs):
    param1 = kwargs.get("param1", "默认值")
    param2 = kwargs.get("param2", 0)
    
    # 执行逻辑
    result = await execute_task(param1, param2)
    
    return {"success": True, "data": result}
```

## 参考资料

- [参考链接 1](./references/ref1.md)
- [参考链接 2](./references/ref2.md)

## 脚本

- `scripts/helper.sh` - 辅助脚本示例

## 注意事项

- 注意事项 1
- 注意事项 2
