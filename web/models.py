from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, index=True)
    # 登录 Web 面板用的账号密码
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    
    # 云运动登录信息
    yun_username = Column(String)
    yun_password = Column(String)
    
    # 缓存下来的云运动 Token
    yun_token = Column(String, default="")
    
    # QQ机器人推送关联的QQ号（留空不推）
    qq_number = Column(String, default="")
    # 推送类型: 'private' 或 'group'
    qq_notify_type = Column(String, default="private")
    
    # 每个用户独立绑定的设备信息（防止风控）
    device_id = Column(String)
    device_name = Column(String)
    uuid = Column(String)
    sys_edition = Column(String, default="14")
    
    # 用户状态：是否激活了自动跑步
    is_active = Column(Boolean, default=True)
    
    # 外键关联
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")
    run_logs = relationship("RunLog", back_populates="user", cascade="all, delete-orphan")


class Schedule(Base):
    __tablename__ = 'schedules'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    # 定时运行时间段 例如 "06:30", "18:00"
    target_time = Column(String)
    
    # 使用哪条跑步路线 (tasks_fch / tasks_txl / tasks_xc 等)
    route_type = Column(String, default="tasks_else")
    
    # 最新一次执行状态记录
    last_run_status = Column(String, default="未运行")
    last_run_time = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="schedules")


class RunLog(Base):
    __tablename__ = 'run_logs'
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    
    run_time = Column(DateTime, default=datetime.now)
    status = Column(String) # "Success", "Failed"
    message = Column(String) # 包含距离、配速 或 错误日志详情
    
    user = relationship("User", back_populates="run_logs")
