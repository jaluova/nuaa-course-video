---
name: nuaa-course-video
description: >-
  Download course lecture videos (录像) from NUAA's 飞天云课堂 VOD platform
  (ft.nuaa.edu.cn, jy-application-vod-he-ui). Use whenever the user wants to
  download or save a course video/lecture recording from this platform — e.g.
  "下载 09-03 8:55 的课", "怎么下载这节课", or any ft.nuaa.edu.cn/jy-application-vod-he-ui/#/video-detail?id=... link.
  Interactive: requires the user to scan a QR code once per run (统一身份认证扫码登录,
  二维码默认不弹窗, 在对话内展示). Downloads the original MP4 (1080p H.264) from vodserver.nuaa.edu.cn.
---

# NUAA 飞天云课堂课程视频下载

从 ft.nuaa.edu.cn (飞天云课堂 / 科达 Kedacom) 下载课程录像原片(MP4, 非转码流)。

## 流程概览

1. **解析目标**——用户给课程链接时取其 `id=NNN` 作为 `teclId`(课堂 id);只给课名
   (如 "软工") 时先跑 `python3 scripts/nuaa_api.py courses 关键词` 找到 teclId
   (输出含课程名/教师/班级);只给日期时间(如 "09-03 8:55") 时,登录后列出课表
   再按 `courBeginTime` 匹配。
2. **扫码登录**——`python3 scripts/qr_login.py <页面URL>`(默认不弹窗,独立终端需要弹出可加
   `--open`)。会启动独立无头
   Chrome 并生成二维码到 `/tmp/nuaa-qr.png`。把二维码**直接展示在对话里**:
   先把图片复制进当前工作区(如 `cp /tmp/nuaa-qr.png <工作区>/nuaa-扫码登录.png`),
   再在回复中用 Markdown 图片语法引用(如 `![扫码登录二维码](<工作区>/nuaa-扫码登录.png)`),
   **请用户用手机(南航App/微信)扫码并在手机上确认**;不要依赖 Preview 弹窗。
   二维码约 5 分钟过期,过期脚本会自动刷新,此时要把新图重新展示给用户。
   登录成功后写入 `/tmp/nuaa-skill-state.json`(jwt + tenant),随后自动关闭无头 Chrome。
3. **列出录像**——`python3 scripts/nuaa_api.py list <teclId>` → 显示该课堂所有节课
   (id / 起止时间 / 教师)。一个课堂通常含多节课,注意用用户说的时间匹配。
4. **取播放地址**——`python3 scripts/nuaa_api.py url <courseId>` → 输出
   vodserver.nuaa.edu.cn 的 mp4 直链(带 auth_key, 有时效,拿到后尽快下载)。
5. **下载**——`python3 scripts/download_mp4.py "<mp4_url>" "~/Downloads/课程名_教师_日期_时间.mp4"`
   (4 路并行分段 + 合并 + ffprobe 校验)。
6. **AI 字幕(可选)**——`python3 scripts/nuaa_api.py subtitle <courseId> [out.srt]`。
   字幕接口用**明文 courseId**(不加密),返回 `{bg, ed, res}` 毫秒时间轴条目,
   脚本直接转成 SRT(带 BOM, Mac/Win 播放器都能识别)。注意:字幕是平台侧
   AI 转写按课生成的,**有的课没有**(返回 `data:[]`),过几天可能就有了。
7. **收尾**——核对 ffprobe 时长与平台显示一致,删除 `/tmp/nuaa-skill-state.json`
   与 `/tmp/nuaa-qr*.png`。向用户汇报文件路径与校验结果。

依赖: 系统的 python3 + venv(pip 可联网,首次运行自动装 websockets/pycryptodome
到 `~/.cache/nuaa-course-video/venv`)、curl、ffprobe(ffmpeg)。二维码在 ZCode
对话内直接展示(任意系统);脚本默认不弹窗,独立 CLI 场景如确需弹出可显式加
`--open`(仅 macOS 有效)。

## 已确认的关键事实(2026-09 实测,勿随意绕过)

- 视频是**直链 MP4**(vodserver.nuaa.edu.cn, H.264 1080p + AAC),下载只需
  `Referer: https://ft.nuaa.edu.cn/` + 浏览器 UA,**不需要 cookie**。
- 平台 `vodDownloadEnable=1`,本身开放下载,不存在 DRM。
- API 鉴权头是 `jwt-token` + `tenantid`(值来自登录后的 sessionStorage,固定流程见下),
  不是 cookie。`/v1/**` 接口无 JWT 一律 401。
- courseId 参数加密: `course_vod_urls?courseId=` 的值是
  CryptoJS `AES.encrypt(id, "ivs3.0")`(OpenSSL salted base64)再**双重 URL 编码**——
  服务端会解码两次,单重编码时 base64 里的 "+" 会变空格导致解密失败(表现为
  `data:null`)。用 `scripts/nuaa_aes.py` 处理;它内置了站点已知样本自检(`self-test`),
  若站点改密钥会检测失败,不要硬编码绕过。
- 扫码确认后**必须刷新登录页再提交**:登录页开太久后 CAS execution 会话过期,
  直接提交会被弹回登录页。qr_login.py 已内置(确认→reload→立即提交,失败自动重试一次)。
- 课程发现接口是 `/v1/group_subject_vod_list?page.pageIndex=1&page.pageSize=1000`
  (返回本学期全部课程, 含 teclId/subjName/teacNames/teclName)。
  `/v1/myself/curriculum` 是教师侧接口,学生账号调用返回 500;
  `/v1/apps` 是应用列表,不是课程。都不要用。

## 排障

- **二维码弹出来是乱码/不是方块图**——qr_login.py 已校验 PNG 魔数;若仍异常,
  看 `/tmp/nuaa-qr-login.log`。二维码约 5 分钟过期,过期会自动刷新重弹。
- **下载中途 403 / auth_key 过期**——重跑 `nuaa_api.py url <courseId>` 换新地址,
  再跑 `download_mp4.py`(已下载部分会跳过;分段下载会覆盖,直接重下最快)。
- **接口返回 401**——登录态失效,重新执行第 2 步扫码登录。
- **找不到课程**——`list` 输出为空时,检查 `teclId` 是否来自页面 URL 的 `id=` 参数;
  或换用 `teclIds` 精确值重试。用户报的时间要和 `courBeginTime` 精确匹配
  页面上显示为 "MM-DD HH:MM"(如 09-03 08:55)。
- **文件时长对不上**——以页面显示的 "xx:xx / xx:xx" 总时长为准对比 ffprobe 输出。

## 备注

- 每轮都要扫码(平台是会话 cookie,无头浏览器每次全新会话),这是设计使然,
  提前告诉用户二维码会展示在对话里, 需要用手机扫码。
- 敏感信息(jwt/token)只存在于 `/tmp/nuaa-skill-state.json`,用后必删。
- 用户的无头流程与用户正在使用的 Chrome 完全隔离,互不影响。