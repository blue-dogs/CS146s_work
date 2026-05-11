from fastmcp import FastMCP
import httpx

# 创建 MCP 服务器实例
mcp = FastMCP("天气查询服务")

# API 配置
API_URL = "https://cn.apihz.cn/api/tianqi/tqyb.php"
API_ID = "10015918"  # 请替换为你的 ID
API_KEY = "1283d569ba0a9846c4c1032793a225d8"  # 请替换为你的 KEY


@mcp.tool()
async def get_weather(place: str) -> str:
    """获取指定城市的天气信息

    Args:
        place: 城市名称，例如：北京、上海、广州、深圳

    Returns:
        返回格式化的天气信息
    """
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                API_URL,
                data={
                    'id': API_ID,
                    'key': API_KEY,
                    'place': place
                },
                timeout=30.0
            )

            data = response.json()

            if data.get('code') == 200:
                weather_data = data.get('data', {})

                # 格式化输出
                result = f"""
╔════════════════════════════════════╗
║         {place} 天气信息              ║
╠════════════════════════════════════╣
"""
                # 字段映射
                fields = {
                    'temp': '🌡️ 温度',
                    'weather': '☁️ 天气',
                    'humidity': '💧 湿度',
                    'wind': '💨 风向',
                    'windpower': '💪 风力',
                    'update_time': '🕐 更新时间'
                }

                for key, value in weather_data.items():
                    if value:
                        display_name = fields.get(key, key)
                        result += f"║ {display_name}: {value}\n"

                result += "╚════════════════════════════════════╝"
                return result
            else:
                return f"❌ 获取天气失败: {data.get('msg', '未知错误')}"

    except httpx.TimeoutException:
        return "❌ 请求超时，请稍后再试"
    except Exception as e:
        return f"❌ 请求失败: {str(e)}"


@mcp.tool()
async def get_current_temperature(place: str) -> str:
    """仅获取指定城市的当前温度

    Args:
        place: 城市名称，例如：北京、上海

    Returns:
        返回当前温度
    """
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                API_URL,
                data={
                    'id': API_ID,
                    'key': API_KEY,
                    'place': place
                },
                timeout=30.0
            )

            data = response.json()

            if data.get('code') == 200:
                weather_data = data.get('data', {})
                temp = weather_data.get('temp', '未知')
                weather = weather_data.get('weather', '未知')
                return f"{place}当前温度: {temp}°C，天气: {weather}"
            else:
                return f"❌ 获取温度失败: {data.get('msg', '未知错误')}"

    except Exception as e:
        return f"❌ 请求失败: {str(e)}"


if __name__ == "__main__":
    # 运行服务器
    mcp.run(transport="stdio")