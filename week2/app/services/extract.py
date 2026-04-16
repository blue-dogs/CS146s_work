from __future__ import annotations

import os
import re
from typing import List
import json
from typing import Any
from ollama import chat
from dotenv import load_dotenv

load_dotenv()

BULLET_PREFIX_PATTERN = re.compile(r"^\s*([-*•]|\d+\.)\s+")
KEYWORD_PREFIXES = (
    "todo:",
    "action:",
    "next:",
)


def _is_action_line(line: str) -> bool: #判断是否是操作项行
    stripped = line.strip().lower()
    if not stripped:
        return False
    if BULLET_PREFIX_PATTERN.match(stripped):
        return True
    if any(stripped.startswith(prefix) for prefix in KEYWORD_PREFIXES):
        return True
    if "[ ]" in stripped or "[todo]" in stripped:
        return True
    return False


# def extract_action_items(text: str) -> List[str]:
#     lines = text.splitlines()
#     extracted: List[str] = []
#     for raw_line in lines:
#         line = raw_line.strip() #strip用于去掉行首尾的空格
#         if not line:
#             continue
#         if _is_action_line(line): #判断是否是操作项行，是就清除格式
#             cleaned = BULLET_PREFIX_PATTERN.sub("", line)
#             cleaned = cleaned.strip()
#            #清除复选框标记
#             cleaned = cleaned.removeprefix("[ ]").strip()
#             cleaned = cleaned.removeprefix("[todo]").strip()
#             extracted.append(cleaned)
#      # 如果没有匹配到操作项行，就尝试将文本按句子分隔，提取祈使句
#     if not extracted:
#         sentences = re.split(r"(?<=[.!?])\s+", text.strip())
#         for sentence in sentences:
#             s = sentence.strip()
#             if not s:
#                 continue
#             if _looks_imperative(s):
#                 extracted.append(s)
#     # 去重并保留顺序
#     seen: set[str] = set()
#     unique: List[str] = []
#     for item in extracted:
#         lowered = item.lower()
#         if lowered in seen:
#             continue
#         seen.add(lowered)
#         unique.append(item)
#     return unique


def _looks_imperative(sentence: str) -> bool: # 判断是否是祈使句
    words = re.findall(r"[A-Za-z']+", sentence)
    if not words:
        return False
    first = words[0]
    # 粗略的判断：将这些单词视为祈使句的开头
    imperative_starters = {
        "add",
        "create",
        "implement",
        "fix",
        "update",
        "write",
        "check",
        "verify",
        "refactor",
        "document",
        "design",
        "investigate",
    }
    return first.lower() in imperative_starters


def extract_action_items_with_llm(text: str, model_name: str = "llama3.1:8b") -> str:
    """
    使用LLM智能提取行动项，返回JSON结构化数据
    
    Args:
        text: 输入文本
        model_name: Ollama模型名称，默认为llama3.1:8b
    
    Returns:
        JSON格式的行动项数据
    """
    # 输入验证和预处理
    if not text or not text.strip():
        return json.dumps({"action_items": []}, ensure_ascii=False, indent=2)
    
    # 预处理文本：清理多余空白和特殊字符
    cleaned_text = _preprocess_input_text(text)
    
    # 构建提示词，根据输入类型调整提示策略
    prompt = _build_adaptive_prompt(cleaned_text)
    
    try:
        # 调用Ollama API
        response = chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        
        # 解析并验证JSON响应
        llm_response = response["message"]["content"].strip()
        
        # 多层解析策略
        parsed_data = _parse_llm_response_with_fallback(llm_response)
        
        # 后处理：验证和清理结果
        validated_data = _validate_and_clean_action_items(parsed_data)
        
        return json.dumps(validated_data, ensure_ascii=False, indent=2)
            
    except Exception as e:
        # 如果LLM调用失败，回退到规则方法并转换为JSON格式
        print(f"LLM提取失败: {e}，使用规则方法回退")
        return _fallback_to_rule_based_json(text)


def _clean_llm_response(response: str) -> str:
    """清理LLM响应，提取JSON部分"""
    # 尝试提取JSON对象
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        return json_match.group()
    
    # 如果找不到JSON对象，尝试构建简单的JSON
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    action_items = []
    
    for line in lines:
        # 清理常见的格式标记
        cleaned = re.sub(r'^[\d\-•*\.]+\s*', '', line)
        if cleaned and len(cleaned) > 3:
            action_items.append({
                "description": cleaned,
                "priority": None,
                "assignee": None,
                "deadline": None,
                "category": None,
                "estimated_time": None
            })
    
    return json.dumps({"action_items": action_items})


def _fallback_to_rule_based_json(text: str) -> str:
    """回退到基于规则的提取方法并转换为JSON格式"""
    # 使用原有的规则方法提取
    lines = text.splitlines()
    extracted: List[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
        if _is_action_line(line):
            cleaned = BULLET_PREFIX_PATTERN.sub("", line)
            cleaned = cleaned.strip()
            cleaned = cleaned.removeprefix("[ ]").strip()
            cleaned = cleaned.removeprefix("[todo]").strip()
            extracted.append(cleaned)
    
    # 如果没有匹配到操作项行，尝试提取祈使句
    if not extracted:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        for sentence in sentences:
            s = sentence.strip()
            if not s:
                continue
            if _looks_imperative(s):
                extracted.append(s)
    
    # 去重并转换为JSON格式
    seen: set[str] = set()
    unique_items: List[str] = []
    for item in extracted:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_items.append(item)
    
    # 构建JSON结构
    action_items = []
    for item in unique_items:
        action_items.append({
            "description": item,
            "priority": None,
            "assignee": None,
            "deadline": None,
            "category": None,
            "estimated_time": None
        })
    
    return json.dumps({"action_items": action_items}, ensure_ascii=False, indent=2)


def _preprocess_input_text(text: str) -> str:
    """预处理输入文本，处理各种输入格式"""
    if not text:
        return ""
    
    # 清理多余空白字符
    cleaned = re.sub(r'\s+', ' ', text.strip())
    
    # 处理常见的编码问题
    cleaned = cleaned.replace('\ufeff', '').replace('\u200b', '')
    
    # 标准化换行符
    cleaned = cleaned.replace('\r\n', '\n').replace('\r', '\n')
    
    return cleaned


def _detect_input_type(text: str) -> str:
    """检测输入文本的类型"""
    lines = text.split('\n')
    
    # 检测项目符号列表
    bullet_count = sum(1 for line in lines if BULLET_PREFIX_PATTERN.match(line.strip()))
    if bullet_count >= len(lines) * 0.5:  # 超过50%的行是项目符号
        return "bullet_list"
    
    # 检测关键词前缀
    keyword_count = sum(1 for line in lines if any(
        line.strip().lower().startswith(prefix) for prefix in KEYWORD_PREFIXES
    ))
    if keyword_count > 0:
        return "keyword_list"
    
    # 检测段落文本
    if len(lines) <= 3 and all(len(line) > 50 for line in lines if line.strip()):
        return "paragraph"
    
    # 检测会议记录格式
    if any(keyword in text.lower() for keyword in ["会议", "讨论", "决定", "任务"]):
        return "meeting_notes"
    
    # 默认类型
    return "general"


def _build_adaptive_prompt(text: str) -> str:
    """根据输入类型构建自适应提示词"""
    input_type = _detect_input_type(text)
    
    base_prompt = """
请从以下文本中提取所有行动项（action items/todo items），并以JSON格式返回。

提取要求：
1. 识别每个行动项的核心描述
2. 推断优先级（高/中/低，如可推断）
3. 识别负责人或部门（如提及）
4. 识别截止时间或时间要求
5. 分类任务类型（开发、测试、文档、会议等）
6. 估计所需时间（如可推断）

输出格式要求：
{
    "action_items": [
        {
            "description": "任务描述",
            "priority": "优先级",
            "assignee": "负责人",
            "deadline": "截止时间",
            "category": "任务类型",
            "estimated_time": "预估时间"
        }
    ]
}

对于无法推断的字段，请使用null值。
"""
    
    # 根据输入类型添加特定指导
    type_specific_guidance = {
        "bullet_list": "注意：输入是项目符号列表，请直接提取每个项目符号项作为行动项。",
        "keyword_list": "注意：输入包含关键词前缀（如todo:、action:），请重点关注这些行。",
        "paragraph": "注意：输入是段落文本，请仔细分析句子结构，识别隐含的行动项。",
        "meeting_notes": "注意：输入是会议记录，请提取会议决定和分配的任务。",
        "general": "请全面分析文本内容，识别所有需要执行的具体任务。"
    }
    
    guidance = type_specific_guidance.get(input_type, type_specific_guidance["general"])
    
    return f"""{base_prompt}

{guidance}

文本内容：
{text}

请直接返回JSON格式的数据，不要添加任何解释性文字。
"""


def _parse_llm_response_with_fallback(response: str) -> dict:
    """多层解析LLM响应，包含多种回退策略"""
    if not response:
        return {"action_items": []}
    
    # 策略1：直接JSON解析
    try:
        data = json.loads(response.strip())
        if _validate_json_structure(data):
            return data
    except json.JSONDecodeError:
        pass
    
    # 策略2：提取JSON对象
    json_match = re.search(r'\{[\s\S]*\}', response)
    if json_match:
        try:
            data = json.loads(json_match.group())
            if _validate_json_structure(data):
                return data
        except json.JSONDecodeError:
            pass
    
    # 策略3：按行解析构建JSON
    return _parse_lines_to_json(response)


def _validate_json_structure(data: dict) -> bool:
    """验证JSON数据结构是否正确"""
    if not isinstance(data, dict):
        return False
    
    if "action_items" not in data:
        return False
    
    if not isinstance(data["action_items"], list):
        return False
    
    # 验证每个行动项的结构
    for item in data["action_items"]:
        if not isinstance(item, dict):
            return False
        if "description" not in item:
            return False
    
    return True


def _parse_lines_to_json(response: str) -> dict:
    """将文本行解析为JSON结构"""
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    action_items = []
    
    for line in lines:
        # 跳过明显的非行动项行
        if any(skip_word in line.lower() for skip_word in ["json", "格式", "输出", "提取"]):
            continue
        
        # 清理格式标记
        cleaned = re.sub(r'^[\d\-•*\.]+\s*', '', line)
        cleaned = cleaned.strip()
        
        if cleaned and len(cleaned) > 3:
            # 尝试提取结构化信息
            item_data = _extract_structured_info(cleaned)
            action_items.append(item_data)
    
    return {"action_items": action_items}


def _extract_structured_info(text: str) -> dict:
    """从单行文本中提取结构化信息"""
    item = {
        "description": text,
        "priority": None,
        "assignee": None,
        "deadline": None,
        "category": None,
        "estimated_time": None
    }
    
    # 优先级提取
    priority_patterns = [
        (r"(高优先级|紧急|urgent|high priority)", "高"),
        (r"(中优先级|中等|medium priority)", "中"),
        (r"(低优先级|不紧急|low priority)", "低")
    ]
    
    for pattern, priority in priority_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            item["priority"] = priority
            break
    
    # 负责人提取（简单模式）
    assignee_match = re.search(r"([张李王赵刘陈杨黄周吴徐孙马朱胡林郭]\S+)\s+(负责|需要|完成)", text)
    if assignee_match:
        item["assignee"] = assignee_match.group(1)
    
    # 截止时间提取
    deadline_patterns = [
        r"(\d+月\d+日[前后]?)",
        r"(本周[一二三四五六日])",
        r"(下周[一二三四五六日])",
        r"(\d+号[前后]?)",
        r"(\d+天内?)"
    ]
    
    for pattern in deadline_patterns:
        match = re.search(pattern, text)
        if match:
            item["deadline"] = match.group(1)
            break
    
    # 任务类型分类
    category_keywords = {
        "开发": ["开发", "编码", "编程", "实现", "编写"],
        "测试": ["测试", "验证", "检查", "调试"],
        "文档": ["文档", "说明", "记录", "撰写"],
        "会议": ["会议", "讨论", "沟通", "汇报"],
        "设计": ["设计", "规划", "架构", "方案"]
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in text for keyword in keywords):
            item["category"] = category
            break
    
    return item


def _validate_and_clean_action_items(data: dict) -> dict:
    """验证和清理行动项数据"""
    if not _validate_json_structure(data):
        return {"action_items": []}
    
    cleaned_items = []
    for item in data["action_items"]:
        # 验证必需字段
        if not item.get("description") or len(item["description"].strip()) < 3:
            continue
        
        # 清理描述字段
        item["description"] = item["description"].strip()
        
        # 验证和清理可选字段
        for field in ["priority", "assignee", "deadline", "category", "estimated_time"]:
            if field in item and item[field] is not None:
                # 特殊处理estimated_time字段：将整数转换为字符串
                if field == "estimated_time":
                    if isinstance(item[field], (int, float)):
                        item[field] = str(item[field])
                    elif isinstance(item[field], str):
                        item[field] = item[field].strip()
                        if not item[field]:
                            item[field] = None
                elif isinstance(item[field], str):
                    item[field] = item[field].strip()
                    if not item[field]:
                        item[field] = None
        
        # 特殊处理category字段：映射到有效的枚举值
        if "category" in item and item["category"]:
            item["category"] = _map_category_to_valid_value(item["category"])
        
        # 确保所有必需字段都有默认值
        item.setdefault("priority", None)
        item.setdefault("assignee", None)
        item.setdefault("deadline", None)
        item.setdefault("category", None)
        item.setdefault("estimated_time", None)
        
        cleaned_items.append(item)
    
    # 去重（基于描述）
    seen_descriptions = set()
    unique_items = []
    for item in cleaned_items:
        desc_lower = item["description"].lower()
        if desc_lower not in seen_descriptions:
            seen_descriptions.add(desc_lower)
            unique_items.append(item)
    
    return {"action_items": unique_items}


def _map_category_to_valid_value(category: str) -> str:
    """将任意分类值映射到有效的枚举值"""
    category_mapping = {
        "下载": "下载",
        "安装": "安装", 
        "配置": "配置",
        "设置": "配置",
        "部署": "开发",
        "调试": "测试",
        "验证": "测试",
        "编写": "文档",
        "记录": "文档",
        "讨论": "会议",
        "沟通": "会议",
        "规划": "设计",
        "架构": "设计"
    }
    
    # 直接匹配
    if category in category_mapping:
        return category_mapping[category]
    
    # 部分匹配
    for key, value in category_mapping.items():
        if key in category:
            return value
    
    # 默认值
    return "通用"


def extract_action_items_advanced(
    text: str, 
    use_llm: bool = True, 
    model: str = "llama3.1:8b"
) -> str:
    """
    高级行动项提取API，支持LLM和规则方法切换
    
    Args:
        text: 输入文本
        use_llm: 是否使用LLM，默认为True
        model: Ollama模型名称
    
    Returns:
        JSON格式的行动项数据
    """
    if use_llm:
        return extract_action_items_with_llm(text, model)
    else:
        return _fallback_to_rule_based_json(text)
