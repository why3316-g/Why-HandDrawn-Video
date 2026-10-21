"""火山方舟（豆包 Seedream）生图后端：没有 Codex CLI / ChatGPT 会员时的第二选择。

只用标准库；密钥从环境变量 ARK_API_KEY 或视频工作区 .private/ark.env 读取，不写进任何文件、日志或提示词记录。
接口：POST https://ark.cn-beijing.volces.com/api/v3/images/generations，Authorization: Bearer <API Key>，
参考图用 image 数组（data:image/png;base64,...），返回 b64_json。模型、尺寸可用环境变量 ARK_IMAGE_MODEL / ARK_IMAGE_SIZE 覆盖。"""
import base64
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = 'https://ark.cn-beijing.volces.com/api/v3/images/generations'
DEFAULT_MODEL = 'doubao-seedream-4-5-251128'
DEFAULT_SIZE = '2496x1664'     # 3:2 横图（人物线稿默认画幅）；若控制台提示尺寸不合法，设 ARK_IMAGE_SIZE=2K


def load_key(workspace=None):
    key = os.environ.get('ARK_API_KEY')
    if key:
        return key.strip()
    f = Path(workspace) / '.private/ark.env' if workspace else None
    if f and f.is_file():
        for line in f.read_text(encoding='utf-8-sig').splitlines():
            if line.startswith('ARK_API_KEY='):
                try:
                    return json.loads(line.split('=', 1)[1]).strip()
                except ValueError:
                    return line.split('=', 1)[1].strip().strip('"')
    return None


def key_ready(workspace=None):
    key = load_key(workspace)
    return bool(key) and not any(w in key.lower() for w in ('填写', 'your-key', 'placeholder', 'example'))


def data_uri(path):
    p = Path(path)
    mime = {'.png': 'png', '.jpg': 'jpeg', '.jpeg': 'jpeg', '.webp': 'webp'}.get(p.suffix.lower(), 'png')
    return f'data:image/{mime};base64,' + base64.b64encode(p.read_bytes()).decode('ascii')


def build_payload(prompt, refs, model=None, size=None):
    payload = {'model': model or os.environ.get('ARK_IMAGE_MODEL') or DEFAULT_MODEL, 'prompt': prompt,
               'size': size or os.environ.get('ARK_IMAGE_SIZE') or DEFAULT_SIZE,
               'response_format': 'b64_json', 'watermark': False, 'sequential_image_generation': 'disabled'}
    refs = [r for r in refs if Path(r).is_file()]
    if refs:
        payload['image'] = [data_uri(r) for r in refs]
    return payload


def generate(prompt, refs, out_path, api_key, model=None, size=None, timeout=300, opener=urllib.request.urlopen):
    """生成一张图并保存；失败抛 RuntimeError（不带密钥与请求内容）。"""
    body = json.dumps(build_payload(prompt, refs, model, size)).encode('utf-8')
    req = urllib.request.Request(ENDPOINT, data=body, method='POST',
                                 headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + api_key})
    try:
        with opener(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = ''
        try:
            detail = json.loads(exc.read().decode('utf-8')).get('error', {}).get('message', '')[:200]
        except Exception:
            pass
        raise RuntimeError(f'火山方舟返回 HTTP {exc.code}：{detail}（401=密钥无效；404=模型未开通；400=尺寸/参数不合法）')
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f'连接火山方舟失败：{type(exc).__name__}')
    items = data.get('data') or []
    if not items or not items[0].get('b64_json'):
        raise RuntimeError('火山方舟没有返回图片：' + json.dumps(data.get('error') or {}, ensure_ascii=False)[:200])
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_bytes(base64.b64decode(items[0]['b64_json']))
    return Path(out_path)
