"""对本包固定花叔快照的项目副本打 Windows 兼容补丁，不改包内原始快照。
补丁内容（均已在本机实测，见 references/PROVENANCE.md）：
  1. 读 spec/JSON 明确 encoding='utf-8'（Windows 默认 GBK，读中文 JSON 会 UnicodeDecodeError）。
  2. 本地渲染服务器改成多线程 + 连接队列 128（上游单线程 TCPServer 在 Chromium 并发请求下会 ERR_CONNECTION_REFUSED，缺 typo.js/ui.js 等）。
  3. render.py 额外打印 requestfailed（缺资源时直接给出具体地址）。
任何一处对不上就报错，不静默跳过——说明上游版本变了，需要人工复核补丁。"""
import sys
from pathlib import Path

SERVER_OLD = "srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(root)))"
SERVER_NEW = ("class LocalServer(http.server.ThreadingHTTPServer):\n"
              "    # Windows Chromium opens parallel resource connections; the default queue of five can reject required scripts before the scene boots.\n"
              "    request_queue_size = 128\n\n"
              "srv = LocalServer(('127.0.0.1', 0), functools.partial(Q, directory=str(root)))")


def _sub(text, old, new, what, count=1):
    if text.count(old) != count:
        raise SystemExit(f'补丁失败（{what}）：上游代码与预期不符（找到 {text.count(old)} 处，预期 {count} 处）。请人工复核 {what}。')
    return text.replace(old, new)


def patch_render(path):
    p = Path(path)
    t = p.read_text(encoding='utf-8')
    if 'class LocalServer' in t:
        return 'already'
    t = _sub(t, "spec = json.loads(sp.read_text())", "spec = json.loads(sp.read_text(encoding='utf-8'))", 'render.py 读 spec')
    t = _sub(t, SERVER_OLD, SERVER_NEW, 'render.py 服务器')
    t = _sub(t, "    pg.on('pageerror', lambda e: (print('[pageerror]', e), errors.append(str(e))))",
             "    pg.on('pageerror', lambda e: (print('[pageerror]', e), errors.append(str(e))))\n    pg.on('requestfailed', lambda r: (print('[requestfailed]', r.url, r.failure), errors.append(r.url + ': ' + str(r.failure))))", 'render.py requestfailed')
    p.write_text(t, encoding='utf-8')
    return 'patched'


def make_qa(src, dst):
    """由 Skill 的 qa.py 生成项目内可用的 qa（同样两处补丁），写到 dst。"""
    t = Path(src).read_text(encoding='utf-8')
    t = _sub(t, "spec = json.loads(sp.read_text())", "spec = json.loads(sp.read_text(encoding='utf-8'))", 'qa.py 读 spec')
    t = _sub(t, "srv = socketserver.TCPServer(('127.0.0.1', 0), functools.partial(Q, directory=str(root))); port = srv.server_address[1]",
             "class LocalServer(http.server.ThreadingHTTPServer):\n    request_queue_size = 128\nsrv = LocalServer(('127.0.0.1', 0), functools.partial(Q, directory=str(root))); port = srv.server_address[1]", 'qa.py 服务器')
    Path(dst).write_text(t, encoding='utf-8')
    return 'made'


if __name__ == '__main__':
    print(patch_render(sys.argv[1]))
