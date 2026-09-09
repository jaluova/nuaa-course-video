# nuaa-course-video

NUAA（南京航空航天大学）「飞天云课堂」课程录像与 AI 字幕下载工具，封装为 [ZCode](https://zcode.ai) 技能（skill），也完全可以脱离 ZCode 当普通命令行工具使用。

> A downloader for course lecture videos and AI subtitles from NUAA's Flipped-Classroom VOD platform (`ft.nuaa.edu.cn`), packaged as a ZCode skill — usable standalone as CLI scripts too.

## 免责声明 / 使用须知

- 本工具仅供本校学生**个人学习复习**使用，请勿用于商业用途。
- 课程录像与课件的著作权归学校和授课教师所有，**请勿将下载内容传播或上传至公开网络**。
- 请控制请求频率（默认配置已足够克制），不要给学校服务器制造压力。
- 如学校或教师明确规定禁止下载，请遵守规定并停止使用。
- 使用本工具产生的任何后果由使用者自行承担。
- 本工具不收集、不存储、不外传任何凭据：登录态只存在于本机临时文件，用后即删。

## 功能特性

- 🔐 **扫码登录**：走学校统一身份认证的二维码流程，全程不需要提供账号密码
- 📋 **课表列出**：一个课堂（教学班）下的所有课次录像，含上课时间与授课教师
- 🎬 **原片下载**：1080p H.264 MP4 直链，4 路并行分段下载 + 合并 + ffprobe 时长校验
- 💬 **AI 字幕**：拉取平台 AI 转写字幕并转换为通用 SRT 格式（UTF-8 BOM）
- 🧹 **凭据卫生**：jwt 登录态只写在 `/tmp` 临时文件，流程结束即清理

## 环境要求

| 依赖 | 用途 | 必需 |
|---|---|---|
| Google Chrome | 无头模式跑登录流程 | 是 |
| python3 (3.9+) | 主逻辑；首次运行自动创建 venv 并安装 `websockets`/`pycryptodome` | 是 |
| curl | 接口调用与分段下载 | 是 |
| ffmpeg/ffprobe | 下载后校验时长 | 可选 |
| macOS + Preview | 仅显式加 `--open` 时：二维码经 Preview 弹出 | 否* |

\* 在 ZCode 中使用时，二维码以图片形式**直接内嵌到对话里**（任意系统都可以）；
脚本**默认不弹任何窗口**（只输出二维码图片路径），仅当显式加 `--open` 时
macOS 才会经 Preview 弹码。

## 安装（作为 ZCode 技能）

本仓库根目录即技能目录，直接 clone 进技能路径即可被 ZCode 自动发现：

```bash
git clone https://github.com/jaluova/nuaa-course-video.git ~/.agents/skills/nuaa-course-video
```

之后在 ZCode 里用自然语言触发即可，例如：

> 帮我下载 ft.nuaa.edu.cn 上 09-03 8:55 那节课的录像和字幕

## 命令行直接使用（不需要 ZCode）

```bash
# 0. 只知道课名时: 列出本学期全部课程, 找到 teclId(支持关键词过滤)
python3 scripts/nuaa_api.py courses 软件工程

# 1. 扫码登录（生成二维码并等待手机确认；默认不弹窗，只打印图片路径；登录态写入 /tmp/nuaa-skill-state.json）
python3 scripts/qr_login.py \
  "https://ft.nuaa.edu.cn/jy-application-vod-he-ui/#/video-detail?id=<teclId>"

# 2. 列出该课堂的全部课次录像（teclId = 页面 URL 里的 id 参数）
python3 scripts/nuaa_api.py list <teclId>
# → id=1234567 | 2025-09-01 14:00:00 ~ 14:50:00 | 某某老师 | ...

# 3. 取某节课的 MP4 播放直链（带 auth_key 签名，有时效，拿到尽快下）
python3 scripts/nuaa_api.py url <courseId>

# 4. 并行分段下载 + 合并 + 校验
python3 scripts/download_mp4.py "<mp4_url>" ~/Downloads/课程名_教师_日期_时间.mp4

# 5. AI 字幕转 SRT（平台还没生成字幕时会明确提示，稍后再试）
python3 scripts/nuaa_api.py subtitle <courseId> ~/Downloads/课程名.srt
```

> 播放地址过期（下载中途 403）时，重新执行第 3 步换新地址，再跑第 4 步即可。

## 工作原理

```
无头 Chrome (全新临时配置, 随机调试端口)
   │  打开视频页 → 302 到统一身份认证 (authserver.nuaa.edu.cn)
   ▼
二维码登录:  GET /authserver/qrCode/getToken   → 令牌
             GET /authserver/qrCode/getCode?uuid=  → 二维码 PNG
             GET /authserver/qrCode/getStatus.htl  → 0 等待 / 2 已扫 / 1 已确认 / 3 过期
   │  手机确认后: 页面 location.reload() 拿新 CAS 会话 → 页面内提交 #qrLoginForm
   ▼
登录态: sessionStorage 里的 jwt-token + tenantid → 存入临时 state 文件
   │  (此后无头 Chrome 即可关闭, 全程不再需要浏览器)
   ▼
课程数据:  GET /v1/subject_vod_list?...&teclIds=<teclId>…   → 课次列表
           GET /v1/course_vod_urls?courseId=<双重URL编码的 AES(id,"ivs3.0")> → MP4 直链
           GET /v1/course_vod_subtitle?courseId=<明文id> → AI 字幕
   ▼
下载: vodserver.nuaa.edu.cn 的签名 MP4, 只需 Referer + 浏览器 UA, 无需 cookie
```

要点（均经实测验证，细节见 `SKILL.md`）：

- 接口鉴权是 **`jwt-token` + `tenantid` 请求头**，不是 cookie；
- `course_vod_urls` 的 `courseId` 参数是 CryptoJS `AES.encrypt(id, "ivs3.0")`（OpenSSL salted base64）且**必须双重 URL 编码**（服务端解码两次，单重编码时 base64 的 `+` 会变空格导致解密失败）；
- 字幕接口用**明文** courseId，返回 `{bg, ed, res}` 毫秒时间轴；
- 视频是直链 MP4（平台本身 `vodDownloadEnable=1`），无 DRM。

### 平台接口速查

| 端点 | 用途 | 鉴权 |
|---|---|---|
| `GET /authserver/qrCode/getToken?ts=` | 二维码令牌 | 无 |
| `GET /authserver/qrCode/getCode?uuid=` | 二维码图片 | 无 |
| `GET /authserver/qrCode/getStatus.htl?uuid=` | 扫码状态轮询 | 无 |
| `POST /authserver/login?display=qrLogin&service=…` | 页面表单提交换票据 | 页面会话 |
| `GET /v1/group_subject_vod_list?page…` | 本学期课程列表（找 teclId） | `jwt-token` + `tenantid` |
| `GET /v1/subject_vod_list?teclIds=…` | 课次列表 | `jwt-token` + `tenantid` |
| `GET /v1/course_vod_urls?courseId=…` | 播放直链 | 同上 |
| `GET /v1/course_vod_subtitle?courseId=…` | AI 字幕 | 同上 |

## 项目结构

```
nuaa-course-video/          ← 仓库根 = 技能根
├── SKILL.md                # 技能定义（触发条件/流程/实测要点/排障）
├── README.md
├── LICENSE
└── scripts/
    ├── qr_login.py         # 无头 Chrome + 二维码登录 → state 文件
    ├── nuaa_aes.py         # courseId AES 加密（含站点样本自检）
    ├── nuaa_api.py         # list / url / subtitle
    └── download_mp4.py     # 并行分段下载 + 合并 + 校验
```

## 已知限制

- 平台登录态是会话 cookie，**每次运行都需要扫一次码**（这是平台设计，无法安全绕过）。
- AI 字幕由平台侧按课生成，部分课次可能缺失或延迟若干天。
- 播放地址的 `auth_key` 有时效；过期重取即可，不支持离线缓存地址。
- 学校接口或页面改版可能导致流程失效（脚本内的自检会尽量给出明确报错）。

## 安全与信任说明

- 全流程**不接触账号密码**：登录走学校统一身份认证的官方二维码接口，确认动作在你手机上完成。
- 脚本持有的唯一凭据是飞天云课堂单个应用的 `jwt-token` 会话：仅能访问本平台的课表/播放/字幕接口，不是统一身份认证密码，动不了教务、邮箱等其他系统；写入本机临时文件时权限为 `0600`（仅文件主可读），流程结束即删除，服务端也会在数小时后过期。
- 凭据只发往 `ft.nuaa.edu.cn`（https），脚本不与任何第三方服务器通信。
- 请只从本仓库获取脚本。**恶意改版的二维码工具可以把你的扫码确认会话转发给攻击者**（扫码钓鱼）——如果得到的二维码来源不明，不要扫。

## 致谢

- 南京航空航天大学「飞天云课堂」（苏州科达 Kedacom 智慧课堂产品线）。
- 接口结构与 AES 口令均来自平台前端公开 JS 的分析，未对平台做任何破解或攻击。

## License

[MIT](LICENSE)
