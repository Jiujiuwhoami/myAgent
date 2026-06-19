#!/bin/bash
cd /root/myAgent && source .venv/bin/activate

# 杀掉旧服务
ss -tlnp | grep ':8000 ' | awk -F'pid=' '{print $2}' | awk -F',' '{print $1}' | xargs -r kill -9
sleep 2

# 启动
AGENT_MAX_WORKERS=2 python -m backend.cli --mode server --host 0.0.0.0 --port 8000
