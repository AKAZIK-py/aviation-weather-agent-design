#!/bin/bash
# 航空气象Agent - 启动脚本

echo "🚀 航空气象Agent后端服务启动中..."
echo ""

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
echo "📥 安装依赖..."
pip install -r requirements.txt

# 检查环境变量
if [ ! -f ".env" ]; then
    echo "⚠️  未找到.env文件，请复制.env.example并配置API密钥"
    echo "   cp .env.example .env"
    exit 1
fi

# 启动服务
echo ""
echo "✅ 启动FastAPI服务..."
echo "   API文档: http://localhost:8000/docs"
echo "   健康检查: http://localhost:8000/api/v1/health"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
