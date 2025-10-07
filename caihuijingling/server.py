from fastapi import FastAPI, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from tencentcloud.aiart.v20221229 import aiart_client, models
from tencentcloud.common import credential
import base64
import cv2
import numpy as np
import yaml
import os
from openai import OpenAI
import json
from io import BytesIO
from PIL import Image, ImageOps
import hashlib
import os
import os
import uuid
import shutil
import yaml
import subprocess
from io import BytesIO
from fastapi import FastAPI, UploadFile, Form, HTTPException
from PIL import Image, ImageOps
import numpy as np
import cv2
import base64
import uuid
import shutil
from io import BytesIO
from fastapi import FastAPI, UploadFile, Form, HTTPException
from PIL import Image, ImageOps
import numpy as np
import cv2
import base64
import uvicorn

# ------------------------- FastAPI 应用 -------------------------
app = FastAPI(title="彩绘精灵 API", description="AI 图片处理服务", version="1.0.0")

# 允许跨域（方便本地调试）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ------------------------- 线稿 -------------------------
DIFFUSION_BASE = r""
YAML_TEMPLATE = os.path.join(DIFFUSION_BASE, "configs", "")

# ------------------------- 腾讯云配置 -------------------------
SECRET_ID = ""
SECRET_KEY = ""
REGION = ""

# ------------------------- Kimi 配置 -------------------------
KIMI_API_KEY = os.getenv("")
client = OpenAI(api_key=KIMI_API_KEY, base_url="")

# ------------------------- 用户管理 -------------------------
USERS_FILE = "users.json"

def load_users():
    """加载用户数据"""
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"加载用户数据失败: {e}")
        return []

def save_users(users):
    """保存用户数据"""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"保存用户数据失败: {e}")
        return False

def hash_password(password: str) -> str:
    """简单的密码哈希（生产环境建议使用 bcrypt）"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    """验证密码"""
    return hash_password(password) == hashed

# ------------------------- 用户认证接口 -------------------------
@app.post("/register")
async def register(username: str = Form(...), password: str = Form(...)):
    """用户注册接口"""
    # 输入验证
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    
    if len(username) < 3:
        raise HTTPException(status_code=400, detail="用户名至少需要3个字符")
    
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码至少需要6个字符")
    
    users = load_users()
    
    # 检查用户名是否已存在
    if any(u["username"] == username for u in users):
        raise HTTPException(status_code=400, detail="用户名已存在")

    # 添加用户（密码加密存储）
    new_user = {
        "username": username, 
        "password": hash_password(password),
        "created_at": json.dumps(None, default=str)  # 可以添加创建时间
    }
    users.append(new_user)
    
    if not save_users(users):
        raise HTTPException(status_code=500, detail="注册失败，请稍后重试")
    
    return {"message": "注册成功", "username": username}

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    """用户登录接口"""
    if not username or not password:
        raise HTTPException(status_code=400, detail="用户名和密码不能为空")
    
    users = load_users()
    
    # 查找用户并验证密码
    for user in users:
        if user["username"] == username:
            if verify_password(password, user["password"]):
                return {
                    "success": True, 
                    "message": "登录成功",
                    "username": username
                }
            else:
                raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    raise HTTPException(status_code=401, detail="用户名或密码错误")

# ------------------------- 线稿上色 -------------------------
@app.post("/colorize")
async def colorize(prompt: str = Form(...), image: UploadFile = None):
    """线稿上色接口"""
    if not image:
        raise HTTPException(status_code=400, detail="请上传线稿图片")
    
    # 验证文件类型
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传有效的图片文件")
    
    try:
        img_bytes = await image.read()
        if len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="上传的图片文件为空")
            
        img_base64 = base64.b64encode(img_bytes).decode()
        
        cred = credential.Credential(SECRET_ID, SECRET_KEY)
        tencent_client = aiart_client.AiartClient(cred, REGION)
        
        req = models.SketchToImageRequest()
        req.Prompt = prompt
        req.InputImage = img_base64
        req.RspImgType = "url"
        
        resp = tencent_client.SketchToImage(req)
        return {"image_url": resp.ResultImage, "prompt": prompt}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"线稿上色失败: {str(e)}")

# ------------------------- 彩色图转线稿 -------------------------
@app.post("/to_sketch")
async def to_sketch(
    image: UploadFile = None,
    method: str = Form("canny")
):
    if not image:
        raise HTTPException(status_code=400, detail="请上传彩色图片")
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传有效的图片文件")

    # ----------------- 创建临时文件夹 -----------------
    temp_dir = os.path.join(DIFFUSION_BASE, "temp", str(uuid.uuid4()))
    input_dir = os.path.join(temp_dir, "input")
    output_dir = os.path.join(temp_dir, "output")
    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    try:
        # ----------------- 读取并处理上传图片 -----------------
        img_bytes = await image.read()
        if len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="上传的图片文件为空")

        pil_img = Image.open(BytesIO(img_bytes))
        pil_img = ImageOps.exif_transpose(pil_img)
        pil_img = pil_img.resize((320, 320), Image.Resampling.LANCZOS)
        if pil_img.mode != 'RGB':
            pil_img = pil_img.convert('RGB')

        # 保存到临时 input 文件夹
        input_path = os.path.join(input_dir, "user_image.png")
        pil_img.save(input_path)

        # ----------------- 根据方式处理 -----------------
        if method == "canny":
            img_array = np.array(pil_img)
            gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
            blur = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blur, 50, 150)
            sketch = cv2.bitwise_not(edges)

        elif method == "diffusion":
            # ----------------- 动态生成 YAML -----------------
            with open(YAML_TEMPLATE, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f)

            cfg['data']['img_folder'] = input_dir.replace("\\", "/")
            cfg['sampler']['save_folder'] = output_dir.replace("\\", "/")

            temp_yaml_path = os.path.join(temp_dir, "BSDS_temp.yaml")
            with open(temp_yaml_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(cfg, f, allow_unicode=True)

            # ----------------- 调用模型脚本（带超时保护） -----------------
            cmd = [
                "python", os.path.join(DIFFUSION_BASE, "sample_cond_ldm.py"),
                "--cfg", temp_yaml_path
            ]
            try:
                subprocess.run(cmd, check=True, timeout=180)  # 最多等待180秒
            except subprocess.TimeoutExpired:
                raise HTTPException(status_code=504, detail="模型生成超时，请稍后重试")
            except subprocess.CalledProcessError as e:
                raise HTTPException(status_code=500, detail=f"模型生成失败: {e}")

            # 模型输出文件
            output_path = os.path.join(output_dir, "user_image.png")
            if not os.path.exists(output_path):
                raise HTTPException(status_code=500, detail="模型未生成线稿")

            sketch = cv2.imread(output_path, cv2.IMREAD_UNCHANGED)

        else:
            raise HTTPException(status_code=400, detail=f"未知的提取方式: {method}")

        # ----------------- 编码为 base64 返回 -----------------
        _, buffer = cv2.imencode('.png', sketch)
        sketch_base64 = base64.b64encode(buffer).decode()
        sketch_url = f"data:image/png;base64,{sketch_base64}"

        return {"image_url": sketch_url, "message": f"{method} 方式线稿转换成功"}

    finally:
        # ----------------- 清理临时文件夹 -----------------
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

# ------------------------- Kimi 描述角色 -------------------------
@app.post("/kimi_describe")
async def kimi_describe(image: UploadFile = None):
    """Kimi AI 图片描述接口"""
    if not image:
        raise HTTPException(status_code=400, detail="请上传图片")
    
    # 验证文件类型
    if not image.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="请上传有效的图片文件")
    
    try:
        # 读取并转为 base64
        img_bytes = await image.read()
        if len(img_bytes) == 0:
            raise HTTPException(status_code=400, detail="上传的图片文件为空")
            
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')
        
        # 获取文件扩展名
        file_extension = 'png'
        if image.filename:
            ext = image.filename.split('.')[-1].lower()
            if ext in ['png', 'jpg', 'jpeg', 'gif', 'webp']:
                file_extension = ext
        # 构造 base64 图片 URL
        img_url = f"data:image/{file_extension};base64,{img_base64}"
        
        # 构造用户提示
        user_prompt = (
            "请根据这张图片，用不超过100字，不少于30字的一段话介绍图中角色，"
            "建议格式: 画风 + 主体对象 + 场景 + 配色/材质/元素/风格等。"
        )
        
        # 调用 Kimi API
        resp = client.chat.completions.create(
            model="moonshot-v1-8k-vision-preview",
            messages=[
                {
                    "role": "system", 
                    "content": "你是 Kimi，由 Moonshot AI 提供的人工智能助手，你更擅长中文和英文的对话。你会为用户提供安全，有帮助，准确的回答。"
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": img_url},
                        },
                        {
                            "type": "text",
                            "text": user_prompt,
                        },
                    ],
                },
            ],
            temperature=0.3,
        )
        
        result = resp.choices[0].message.content.strip()
        return {"description": result, "message": "描述生成成功"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"图片描述失败: {str(e)}")

# ------------------------- 健康检查和系统信息 -------------------------
@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "service": "彩绘精灵 API",
        "version": "1.0.0"
    }

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用彩绘精灵 API",
        "docs": "/docs",
        "health": "/health"
    }

@app.get("/users/count")
async def get_user_count():
    """获取用户总数（可选接口）"""
    users = load_users()
    return {"total_users": len(users)}

# ------------------------- 启动服务 -------------------------
if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True,  # 开发模式
        access_log=True
    )