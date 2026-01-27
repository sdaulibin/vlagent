#!/bin/bash
# ====================================================
# vl_flow 离线构建脚本
# 在联网机器上运行，生成离线部署包
# ====================================================

set -e

echo "🚀 开始构建 vl_flow Docker 镜像..."

# 1. 构建镜像
docker compose build

# 2. 创建输出目录
OUTPUT_DIR="./offline_deploy"
mkdir -p $OUTPUT_DIR

# 3. 导出镜像
echo "📦 导出 Docker 镜像..."
docker save vl_flow-backend:latest | gzip > $OUTPUT_DIR/vl_flow_backend.tar.gz
docker save vl_flow-frontend:latest | gzip > $OUTPUT_DIR/vl_flow_frontend.tar.gz

# 4. 复制配置文件
echo "📄 复制配置文件..."
cp docker-compose.yml $OUTPUT_DIR/
cp .env.example $OUTPUT_DIR/.env

# 5. 创建部署脚本
cat > $OUTPUT_DIR/deploy.sh << 'EOF'
#!/bin/bash
# 内网服务器部署脚本

set -e

echo "📦 加载 Docker 镜像..."
gunzip -c vl_flow_backend.tar.gz | docker load
gunzip -c vl_flow_frontend.tar.gz | docker load

echo "🔧 请编辑 .env 文件配置数据库和 AI 服务..."
echo "   vim .env"
echo ""
echo "✅ 镜像加载完成！启动服务请运行:"
echo "   docker compose up -d"
EOF
chmod +x $OUTPUT_DIR/deploy.sh

echo ""
echo "✅ 构建完成！离线部署包位于: $OUTPUT_DIR/"
echo ""
echo "📁 包含文件:"
ls -lh $OUTPUT_DIR/
echo ""
echo "📤 传输到内网服务器:"
echo "   scp -r $OUTPUT_DIR user@10.1.92.197:/root/vl_flow/"
