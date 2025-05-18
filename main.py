"""
元宝AI绘画插件

使用混元大模型进行AI绘画，支持指定风格
"""

import aiohttp
import base64
import json
import re
from loguru import logger
import tomllib
import urllib.parse
from utils.decorators import *
from utils.plugin_base import PluginBase
from WechatAPI import WechatAPIClient


class YuanbaoPlugin(PluginBase):
    """元宝AI绘画插件类"""
    description = "元宝AI绘画插件：使用'元宝+内容+风格'或'元宝画+内容+风格'生成AI绘画"
    author = "AI Assistant"
    version = "1.0.0"

    # 支持的风格列表
    STYLES = [
        "人像摄影风格", "真实全景风格", "全息风格", "卡通插画风格", "城市风格", 
        "像素风格", "赛博朋克风格", "蒸汽朋克风格", "浪漫风格", "3D卡通风格", 
        "轻奢日漫风格", "轻手绘漫画风格", "3D风格", "彩色水墨风格", "工作室摄影风格", 
        "水彩风格", "古典风格", "剪纸风格", "毛边风格", "徐悲鸿风格", 
        "轻奢风格", "水墨画风格", "韩式风格", "现代风格", "复古风格", 
        "彩铅风格", "油画风格", "宫崎骏风格", "凡高风格"
    ]

    def __init__(self):
        super().__init__()
        try:
            with open("plugins/yuanbao/config.toml", "rb") as f:
                config = tomllib.load(f)
            plugin_config = config["yuanbao"]
            self.enable = plugin_config["enable"]
            
            # 加载API配置
            self.api_url = plugin_config["api_url"]
            self.qq = plugin_config["qq"]
            
            # 加载触发命令
            self.triggers = plugin_config["triggers"]
            
            # 加载默认风格
            self.default_style = plugin_config.get("default_style", "")
            
            logger.info(f"[YuanbaoPlugin] 插件初始化完成")
        except Exception as e:
            logger.error(f"[YuanbaoPlugin] 加载配置文件失败: {e}")
            # 设置默认值，确保插件可以运行
            self.enable = True
            self.api_url = "https://api.317ak.com/API/AI/hunyuan/hunyuanhh.php"
            self.qq = "67628042"
            self.triggers = ["元宝", "元宝画"]
            self.default_style = ""

    @on_text_message(priority=50)
    async def handle_text(self, bot: WechatAPIClient, message: dict):
        """处理文本消息"""
        if not self.enable:
            return True  # 插件未启用，允许后续插件处理

        content = message.get("Content", "").strip()
        from_wxid = message.get("FromWxid", "")
        
        if not content or not from_wxid:
            return True  # 消息内容或发送者ID为空，允许后续插件处理

        # 检查是否匹配触发命令
        prompt = None
        style = None
        
        for trigger in self.triggers:
            if content.startswith(trigger):
                # 提取提示词和风格
                remaining = content[len(trigger):].strip()
                
                # 尝试匹配风格
                for potential_style in self.STYLES:
                    if potential_style in remaining:
                        style = potential_style
                        # 移除风格部分，剩下的是提示词
                        prompt = remaining.replace(style, "").strip()
                        break
                
                # 如果没有匹配到风格，整个内容都是提示词
                if not style:
                    prompt = remaining
                    style = self.default_style
                
                break
                
        # 如果匹配到了触发词且有提示内容
        if prompt:
            logger.info(f"[YuanbaoPlugin] 收到绘画请求: 提示词='{prompt}', 风格='{style}'")
            
            # 发送等待消息
            style_text = f"，风格：{style}" if style else ""
            await bot.send_text_message(from_wxid, f"🎨 正在绘制'{prompt}'{style_text}，请稍候...")
            
            try:
                # 获取图片URL
                image_urls = await self.generate_image(prompt, style)
                    
                if image_urls and len(image_urls) > 0:
                    # 下载并发送每张图片
                    success_count = 0
                    for url in image_urls:
                        try:
                            # 下载图片
                            image_data = await self.download_image(url)
                            if image_data:
                                # 将图片转为Base64编码
                                image_base64 = base64.b64encode(image_data).decode('utf-8')
                                # 发送图片
                                await bot.send_image_message(from_wxid, image=image_base64)
                                success_count += 1
                                logger.info(f"[YuanbaoPlugin] 成功发送AI绘画图片: {url}")
                        except Exception as e:
                            logger.error(f"[YuanbaoPlugin] 发送图片失败: {e}")
                    
                    if success_count == 0:
                        await bot.send_text_message(from_wxid, "😔 绘画生成失败，请稍后再试。")
                else:
                    await bot.send_text_message(from_wxid, "😔 绘画生成失败，请稍后再试。")
            except Exception as e:
                logger.error(f"[YuanbaoPlugin] 处理绘画错误: {e}")
                await bot.send_text_message(from_wxid, "😔 绘画生成失败，请稍后再试。")
            return False  # 阻止其他插件处理
            
        return True  # 不是本插件处理的命令，允许后续插件处理

    async def generate_image(self, prompt, style=None):
        """获取AI绘画图片URL列表"""
        try:
            # URL编码参数
            encoded_prompt = urllib.parse.quote(prompt)
            
            # 构建完整URL
            full_url = f"{self.api_url}?msg={encoded_prompt}&qq={self.qq}"
            
            # 如果有风格，添加风格参数
            if style:
                encoded_style = urllib.parse.quote(style)
                full_url += f"&fg={encoded_style}"
            
            logger.info(f"[YuanbaoPlugin] 请求URL: {full_url}")
            
            # 创建SSL上下文，禁用证书验证
            conn = aiohttp.TCPConnector(ssl=False)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'application/json, text/plain, */*'
            }
            
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.get(full_url, headers=headers, timeout=60) as response:
                    if response.status == 200:
                        # 解析JSON响应
                        json_data = await response.json()
                        logger.info(f"[YuanbaoPlugin] API响应: {json_data}")
                        
                        # 检查响应状态
                        if json_data.get("code") == 200 and "data" in json_data:
                            # 提取所有图片URL
                            image_urls = []
                            for item in json_data["data"]:
                                if "url" in item and item["url"]:
                                    image_urls.append(item["url"])
                            
                            logger.info(f"[YuanbaoPlugin] 提取到 {len(image_urls)} 个图片URL")
                            return image_urls
                        else:
                            logger.error(f"[YuanbaoPlugin] API返回错误: {json_data}")
                    else:
                        logger.error(f"[YuanbaoPlugin] API请求失败，状态码: {response.status}")
            
            return []
        except Exception as e:
            logger.error(f"[YuanbaoPlugin] 获取图片URL异常: {e}")
            return []

    async def download_image(self, url):
        """下载图片"""
        try:
            # 创建SSL上下文，禁用证书验证
            conn = aiohttp.TCPConnector(ssl=False)
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
                'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8'
            }
            
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.get(url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        image_data = await response.read()
                        if len(image_data) > 1000:  # 简单验证是否为图片数据
                            return image_data
                        else:
                            logger.error(f"[YuanbaoPlugin] 下载的数据太小，可能不是图片: {len(image_data)} 字节")
                    else:
                        logger.error(f"[YuanbaoPlugin] 下载图片失败，状态码: {response.status}")
            
            return None
        except Exception as e:
            logger.error(f"[YuanbaoPlugin] 下载图片异常: {e}")
            return None

    async def get_help_text(self):
        """获取帮助文本"""
        help_text = "🎨 元宝AI绘画插件使用说明\n\n"
        help_text += "使用方法：\n"
        help_text += "1. 元宝画+内容：例如「元宝画一只猫」\n"
        help_text += "2. 元宝画+内容+风格：例如「元宝画美女人像摄影风格」\n\n"
        help_text += "支持的风格：\n"
        
        # 每行显示3个风格
        styles_per_line = 3
        for i in range(0, len(self.STYLES), styles_per_line):
            line_styles = self.STYLES[i:i+styles_per_line]
            help_text += "、".join(line_styles) + "\n"
            
        return help_text


def get_plugin_class():
    return YuanbaoPlugin