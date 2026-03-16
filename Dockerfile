FROM python:3.12-slim-bookworm

# 设置工作目录
WORKDIR /app

# 设置时区为上海，保证定时运行正确
ENV TZ=Asia/Shanghai
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 复制依赖文件并安装 (使用清华源加速)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制项目所有文件
COPY . .

# 暴露 FastAPI 端口
EXPOSE 8000

# 启动 uvicorn 服务
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
