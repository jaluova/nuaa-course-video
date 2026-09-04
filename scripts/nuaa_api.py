#!/usr/bin/env python3
"""飞天云课堂 API 封装 (使用 qr_login.py 产出的 state 文件里的 jwt)。

用法:
  python3 nuaa_api.py list <teclId>            # 列出该课堂下的全部录像(id/时间/教师)
  python3 nuaa_api.py url <courseId>           # 取某节课的 mp4 播放地址(带 auth_key)
  python3 nuaa_api.py refresh <courseId>       # 同上(播放地址过期时重新签发)
  python3 nuaa_api.py subtitle <courseId> [out.srt]  # 拉 AI 字幕并转 SRT(无字幕则报错)

state 文件(默认 /tmp/nuaa-skill-state.json): {"jwt": ..., "tenant": ...}
"""
import json, os, subprocess, sys, urllib.request

BASE = "https://ft.nuaa.edu.cn/jy-application-vod-he"
STATE_DEFAULT = "/tmp/nuaa-skill-state.json"
VENV_DIR = os.path.expanduser("~/.cache/nuaa-course-video/venv")
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
HERE = os.path.dirname(os.path.abspath(__file__))


def bootstrap_venv():
    try:
        from Crypto.Cipher import AES  # noqa: F401
        return
    except ImportError:
        pass
    if not os.path.exists(VENV_DIR + "/bin/python3"):
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], check=True)
    subprocess.run([VENV_DIR + "/bin/pip", "install", "-q", "pycryptodome"], check=True)
    os.execv(VENV_DIR + "/bin/python3", [VENV_DIR + "/bin/python3"] + sys.argv)


bootstrap_venv()
sys.path.insert(0, HERE)
from nuaa_aes import encrypt_quoted  # noqa: E402


def load_state(state_path):
    with open(state_path) as f:
        return json.load(f)


def call(path_qs, state):
    req = urllib.request.Request(BASE + path_qs, headers={
        "jwt-token": state["jwt"],
        "tenantid": state.get("tenant", "RBAC"),
        "User-Agent": UA,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def cmd_list(tecl_id, state):
    qs = (f"/v1/subject_vod_list?page.pageIndex=1&page.pageSize=1000"
          f"&teclIds={tecl_id}%20%20%20%20%20%20"
          f"&page.orders%5B0%5D.asc=true&page.orders%5B0%5D.field=courBeginTime")
    data = call(qs, state)
    for r in data.get("data", {}).get("records", []):
        print(f"id={r['id']} | {r.get('courBeginTime')} ~ {r.get('courEndTime')} | "
              f"{', '.join(r.get('teacNames') or [])} | "
              f"teclId={r.get('teclId')} | vodStatus={r.get('vodStatus')}")


def cmd_url(course_id, state):
    qs = f"/v1/course_vod_urls?courseId={encrypt_quoted(str(course_id))}"
    data = call(qs, state)
    info = data.get("data") or {}
    views = info.get("courseVodViewList") or []
    if not views:
        print("no playable url; response:", json.dumps(data, ensure_ascii=False)[:300])
        return
    print(f"course: {info.get('courName')} | {info.get('tecName')} | "
          f"{info.get('classRoomName')} | vodDownloadEnable={info.get('vodDownloadEnable')}")
    for v in views:
        print(v["url"])


def _ms_to_srt_ts(ms):
    h, rem = divmod(int(ms), 3600000)
    m, rem = divmod(rem, 60000)
    s, ms2 = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms2:03d}"


def cmd_subtitle(course_id, state, out_path=None):
    """拉取 AI 字幕(条目: bg/ed 毫秒时间轴 + res 文本)并转成 SRT。

    平台未生成字幕时接口返回 data:[](空), 此时打印提示并以退出码 1 结束。"""
    data = call(f"/v1/course_vod_subtitle?courseId={course_id}", state)
    entries = data.get("data") or []
    if not entries:
        print(f"courseId {course_id}: 平台上还没有字幕数据 (AI 转写可能未生成), "
              f"可过几天重试")
        sys.exit(1)
    entries.sort(key=lambda e: e.get("bg", 0))
    if not out_path:
        out_path = f"{course_id}.srt"
    with open(out_path, "w", encoding="utf-8-sig") as f:
        for i, e in enumerate(entries, 1):
            f.write(f"{i}\n{_ms_to_srt_ts(e['bg'])} --> {_ms_to_srt_ts(e['ed'])}\n"
                    f"{e.get('res', '').strip()}\n\n")
    span = (entries[-1]["ed"] - entries[0]["bg"]) / 60000
    print(f"courseId {course_id}: {len(entries)} 条字幕 -> {out_path} "
          f"(覆盖约 {span:.0f} 分钟)")


if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in ("list", "url", "refresh", "subtitle"):
        print(__doc__)
        sys.exit(2)
    state_path = STATE_DEFAULT
    if "--state" in sys.argv:
        state_path = sys.argv[sys.argv.index("--state") + 1]
    state = load_state(state_path)
    cmd = sys.argv[1]
    arg = sys.argv[2]
    if cmd == "list":
        cmd_list(arg, state)
    elif cmd == "subtitle":
        cmd_subtitle(arg, state, sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        cmd_url(arg, state)