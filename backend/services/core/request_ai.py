import asyncio
import base64
import threading
import time

import httpx
from openai import OpenAI
from openai.types.chat import ChatCompletionStreamOptionsParam

from src.config import *

# ========== 全局单例 OpenAI client + 并发限流 ==========

_QWEN35_LOCK = threading.Lock()
_QWEN35_CLIENT = None

# asyncio.Semaphore：在 async 层限流，不占线程池线程
# 单 worker 同时最多 2 个 AI 请求在飞
# 2 副本 × 4 workers = 8 workers，8 × 2 = 16 并发（AI 网关上限 20）
_AI_SEMAPHORE = asyncio.Semaphore(2)


def ai_semaphore():
    """返回全局 AI 并发信号量，供各 service 模块的 Phase 2 使用。

    用法：
        async with ai_semaphore():
            result = await asyncio.to_thread(sync_ai_function, ...)
    """
    return _AI_SEMAPHORE


def _get_qwen35_client() -> OpenAI:
    """全局共享的 Qwen3.5 client（线程安全懒初始化，复用 TCP 连接）"""
    global _QWEN35_CLIENT
    if _QWEN35_CLIENT is None:
        with _QWEN35_LOCK:
            if _QWEN35_CLIENT is None:
                _QWEN35_CLIENT = OpenAI(
                    api_key=QWEN35_KEY,
                    base_url=QWEN35_URL,
                    timeout=600.0,
                    max_retries=3,
                    http_client=httpx.Client(
                        limits=httpx.Limits(
                            max_connections=20,
                            max_keepalive_connections=10,
                        ),
                        timeout=httpx.Timeout(
                            connect=10.0,
                            read=600.0,
                            write=30.0,
                            pool=10.0,
                        ),
                    ),
                )
    return _QWEN35_CLIENT


def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


# def request_stream(question="", file_base="", model=MODEL_QWEN_VLMAX,
#                    multi_pic=None,
#                    video="",
#                    video_list="",
#                    system_content=None,
#                    show_filename=False,
#                    show_cost=False,
#                    is_stream=True,
#                    pic_tip=False,
#                    show_request=True, file_ary=None):
#     t1 = time.time()
#     api_key = OPENAI_KEY
#     base_url = OPENAI_URL
#     model = model
#     client = OpenAI(
#         api_key=api_key,
#         base_url=base_url,
#         timeout=300.0,  # 5分钟超时，处理大图片
#         max_retries=3,  # ← 新增：遇到 502/503/429 自动重试
#     )
#     message = []
#     if system_content is not None:
#         message.append({"role": "system",
#                         "content": system_content
#                         })
#     content = []
#     if multi_pic is not None:
#         content.extend(multi_pic)
#     if file_ary is not None and len(file_ary) > 0:
#         ## for循环带序标
#         for i, file in enumerate(file_ary):
#             if pic_tip:
#                 content.append({"type": "text", "text": f"下面是图片{i}"})
#             content.append({
#                 "type": "image_url",
#                 "image_url": file,
#             })
#     elif len(file_base) > 0:
#         content.append({"type": "image_url",
#                         "image_url": file_base,
#                         })
#     if video is not None and len(video) > 0:
#         content.append({"type": "video_url",
#                         "video_url": video,
#                         })
#     if video_list is not None and len(video_list) > 0:
#         content.append({"type": "video_url",
#                         "video_url": video_list,
#                         })
#     if question is not None and len(question) > 0:
#         content.append({"type": "text", "text": question})
#     # if show_request:
#     #     print(content)
#     encode_content(content)
#     message.append({
#         "role": "user",
#         "content": content,
#     })
#     # print(f"start {file_base}")
#     completion = client.chat.completions.create(
#         temperature=0.01,
#         model=model,
#         messages=message,
#         seed=3407,
#         stream=is_stream,
#         stream_options=ChatCompletionStreamOptionsParam(include_usage=show_cost),
#     )

#     resp = ""
#     t_arguments = []
#     t_name = []
#     first_cost = 0
#     flag = False
#     usage = None
#     if is_stream:
#         for chunk in completion:
#             try:
#                 c = chunk.choices[0].delta.content
#                 function = chunk.choices[0].delta.tool_calls[0].function if chunk.choices[0].delta.tool_calls else None
#             except Exception as e:
#                 c = None
#                 function = None

#             if function:
#                 if function.name:
#                     t_name.append(function.name)
#                 if function.arguments:
#                     t_arguments.append(function.arguments)
#             if c:
#                 if show_cost:
#                     if not flag:
#                         flag = True
#                         first_cost = time.time() - t1
#                 resp += c
#             if chunk.usage:
#                 if show_cost:
#                     usage = chunk.usage
#     else:
#         resp = completion.choices[0].message.content
#     # print(f"end {file_base}")
#     if show_cost:
#         total_cost = time.time() - t1
#         print(f"first cost: {first_cost}")
#         print(f"total cost: {total_cost}")
#         ## token
#         if not is_stream:
#             usage = completion.usage
#         if usage.prompt_tokens_details.cached_tokens:
#             print(f"cached_tokens:{usage.prompt_tokens_details.cached_tokens}")
#         print(
#             f"request:prompt_tokens={usage.prompt_tokens} image_token={usage.prompt_tokens_details.image_tokens} text_tokens={usage.prompt_tokens_details.text_tokens} ")
#         print(f"response:total_tokens={usage.total_tokens} completion_tokens={usage.completion_tokens}")
#         print(
#             f"token per:total_per={usage.total_tokens / total_cost} output_per={usage.completion_tokens / total_cost}")

#     if show_filename:
#         return (resp, file_base)
#     else:
#         return resp


# def request_ocr(file_base, show_filename=False, show_request=False):
#     ocr = request_stream(question="", file_base=file_base, model=MODEL_QWEN_OCR_LATEST,
#                          show_request=show_request,
#                          show_filename=show_filename)
#     return ocr


def create_video_content(str, fps=0):
    # keyframes/keyframe_0000.jpg (时间: 00:00:00.000)
    # keyframes/keyframe_0001.jpg (时间: 00:00:00.033)
    # keyframes/keyframe_0002.jpg (时间: 00:00:00.067)
    # 对这类样式进行转换
    lines = str.split("\n")
    count = 0
    result = []
    for line in lines:
        if len(line) < 1:
            continue
        if count != 0:
            count += 1
            if count >= fps:
                count = 0
            continue
        count += 1
        if count >= fps:
            count = 0
        line_ary = line.split(" (")
        path = line_ary[0].strip()
        time = line_ary[1].split(")")[0]
        result.append(
            {"type": "text", "text": f"以下帧{time}"})
        result.append({
            "type": "image_url",
            "image_url": path,
        })
    return result


def encode_content(content):
    for c in content:
        if c.get("image_url", None) is not None:
            file_base = c["image_url"]
            base_64 = encode_image(file_base)
            t = file_base.split(".")[-1]
            c["image_url"] = {"url": f"data:image/{t};base64,{base_64}"}
        if c.get("video_url", None) is not None:
            file_base = c["video_url"]
            if type(file_base) == str:
                base_64 = encode_image(file_base)
                t = file_base.split(".")[-1]
                c["video_url"] = {"url": f"data:video/{t};base64,{base_64}"}
            if type(file_base) == list:
                for i, f in enumerate(file_base):
                    base_64 = encode_image(f)
                    t = f.split(".")[-1]
                    file_base[i] = f"data:image/{t};base64,{base_64}"
                c["video_url"] = file_base


def build_fewshot(file_base, explanation):
    # 将xxxx/test.png替换为你本地图像的绝对路径
    return [
        {
            "type": "image_url",
            "image_url": file_base,
        },
        {"type": "text", "text": explanation},
    ]


def request_qwen35(question="", file_base="", model=QWEN35_MODEL,
                    multi_pic=None,
                    video="",
                    video_list="",
                    system_content=None,
                    show_filename=False,
                    show_cost=False,
                    is_stream=True,
                    pic_tip=False,
                    show_request=True, file_ary=None,
                    temperature=0.7, top_p=0.8):
    """
    调用 Qwen3.5-35B 模型（非思考模式）

    参数与 request_stream 完全一致，但使用 Qwen3.5 的 API 地址和密钥。
    注意：并发限流已移至 async 层（ai_semaphore），调用方应在 Phase 2 使用
    async with ai_semaphore() 包裹 asyncio.to_thread。
    """
    return _request_qwen35_impl(
        question=question, file_base=file_base, model=model,
        multi_pic=multi_pic, video=video, video_list=video_list,
        system_content=system_content, show_filename=show_filename,
        show_cost=show_cost, is_stream=is_stream, pic_tip=pic_tip,
        show_request=show_request, file_ary=file_ary,
        temperature=temperature, top_p=top_p,
    )


def _request_qwen35_impl(question="", file_base="", model=QWEN35_MODEL,
                         multi_pic=None, video="", video_list="",
                         system_content=None, show_filename=False,
                         show_cost=False, is_stream=True, pic_tip=False,
                         show_request=True, file_ary=None,
                         temperature=0.7, top_p=0.8):
    """实际 AI 调用逻辑"""
    t1 = time.time()
    client = _get_qwen35_client()
    message = []
    if system_content is not None:
        message.append({"role": "system",
                        "content": system_content
                        })
    content = []
    if multi_pic is not None:
        content.extend(multi_pic)
    if file_ary is not None and len(file_ary) > 0:
        for i, file in enumerate(file_ary):
            if pic_tip:
                content.append({"type": "text", "text": f"下面是图片{i}"})
            content.append({
                "type": "image_url",
                "image_url": file,
            })
    elif len(file_base) > 0:
        content.append({"type": "image_url",
                        "image_url": file_base,
                        })
    if video is not None and len(video) > 0:
        content.append({"type": "video_url",
                        "video_url": video,
                        })
    if video_list is not None and len(video_list) > 0:
        content.append({"type": "video_url",
                        "video_url": video_list,
                        })
    if question is not None and len(question) > 0:
        content.append({"type": "text", "text": question})
    encode_content(content)
    message.append({
        "role": "user",
        "content": content,
    })

    extra_body = {"chat_template_kwargs": {"enable_thinking": False}}

    completion = client.chat.completions.create(
        temperature=temperature,
        top_p=top_p,
        model=model,
        messages=message,
        max_tokens=8192,
        seed=3407,
        stream=is_stream,
        extra_body=extra_body,
        stream_options=ChatCompletionStreamOptionsParam(include_usage=show_cost),
    )

    resp = ""
    t_arguments = []
    t_name = []
    first_cost = 0
    flag = False
    usage = None
    if is_stream:
        for chunk in completion:
            try:
                c = chunk.choices[0].delta.content
                function = chunk.choices[0].delta.tool_calls[0].function if chunk.choices[0].delta.tool_calls else None
            except Exception as e:
                c = None
                function = None

            if function:
                if function.name:
                    t_name.append(function.name)
                if function.arguments:
                    t_arguments.append(function.arguments)
            if c:
                if show_cost:
                    if not flag:
                        flag = True
                        first_cost = time.time() - t1
                resp += c
            if chunk.usage:
                if show_cost:
                    usage = chunk.usage
    else:
        resp = completion.choices[0].message.content
    if show_cost:
        total_cost = time.time() - t1
        print(f"[Qwen3.5] first cost: {first_cost}")
        print(f"[Qwen3.5] total cost: {total_cost}")
        if not is_stream:
            usage = completion.usage
        if usage.prompt_tokens_details.cached_tokens:
            print(f"cached_tokens:{usage.prompt_tokens_details.cached_tokens}")
        print(
            f"request:prompt_tokens={usage.prompt_tokens} image_token={usage.prompt_tokens_details.image_tokens} text_tokens={usage.prompt_tokens_details.text_tokens} ")
        print(f"response:total_tokens={usage.total_tokens} completion_tokens={usage.completion_tokens}")
        print(
            f"token per:total_per={usage.total_tokens / total_cost} output_per={usage.completion_tokens / total_cost}")

    if show_filename:
        return (resp, file_base)
    else:
        return resp


if __name__ == '__main__':
    prompt = """
    
    """
    rest = request_qwen35(question=prompt,
                          show_request=False,
                          model=QWEN35_MODEL)
    # print(rest)
