# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate a dependency-free, bilingual GitHub Pages project introduction."""
from html import escape
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import __version__

BASE = 'https://songmanual.github.io/MijiaDeck/'
REPO = 'https://github.com/Songmanual/MijiaDeck'
CONTENT = {
 'zh': {
  'lang':'zh-Hans', 'title':'MijiaDeck 米家电脑版 · 小米智能设备 Windows 桌面控制',
  'description':'MijiaDeck 是开源免费的第三方米家 Windows 客户端。电脑控制米家设备、远程查看兼容小米摄像头、托盘控制小爱音箱，支持灯光亮度与色温调节。',
  'switch':'English', 'switch_url':'en/', 'nav':['功能','兼容与边界','常见问题'],
  'eyebrow':'米家电脑版 · Windows 10 / 11',
  'heading':'米家设备，<br>回到你的电脑桌面。',
  'intro':'开关灯、查看温湿度、远程看摄像头，或者给小爱音箱发一条文字指令。MijiaDeck 把常用米家操作放到 Windows 桌面和系统托盘里。',
  'download':'下载 Windows 版', 'source':'GitHub 源码',
  'requirements':'免费开源 · x64 免安装 ZIP · 第三方客户端',
  'caption':'实际界面，虚构示例数据；不包含真实账号、家庭或摄像头画面。截图为界面示意，具体功能以版本和设备能力为准。',
  'features_title':'常用操作，不必再拿起手机。',
  'features':[
   ('设备卡片直接控制','按家庭和房间查看设备。支持的灯、分路开关和插座可以直接开关，多路面板展示各路状态。'),
   ('摄像头远程查看','兼容米家摄像头可打开独立预览窗口，支持画质切换、静音、全屏和拖动云台；无需处于同一局域网。实验性功能。'),
   ('小爱音箱就在托盘','选择要控制的小爱音箱，播放、暂停、切歌和调音量；输入“打开客厅灯”等文字指令，由所选音箱执行。'),
   ('灯光小控制窗','按设备能力显示亮度、色温、颜色控件。普通灯直接开关，复杂设置仍在米家 APP 中完成。'),
   ('已有场景，一键执行','读取账号中通过米家 APP 创建的手动场景，在电脑上执行。这里不创建、编辑或删除自动化。'),
   ('只留下有用的快捷卡片','温湿度等已支持读数可直接展示。托盘清单按可用控制与读数筛选，支持排序、单列或双列和浮窗位置记忆。'),
  ],
  'steps_title':'完整解压，就可以开始。',
  'steps':[('下载','从 GitHub 最新发布页下载 Windows x64 ZIP，选择程序包而不是 Source code。'),('运行','完整解压，打开 MijiaDeck.exe。保留 _internal 文件夹，不需要另装 Python 或 Java。'),('登录与控制','用米家 APP 扫码登录，按家庭和房间查看设备；单击托盘图标打开快捷浮窗，右键打开菜单。')],
  'compat_title':'支持什么，边界也说清楚。',
  'compat':[
   ('系统','Windows 10 1903+ / Windows 11 x64。Win7、Win8 不支持；Win11 完整实机验证仍待补充。'),
   ('多路开关、温湿度','已有本地实机使用反馈。按设备规格识别分路与读数，不保证同品牌全部型号兼容。'),
   ('摄像头','已有兼容型号实机预览反馈；传输为实验实现，型号、固件和网络都会影响可用性。'),
   ('调光、色温、调色','已实现小控制窗并通过模拟设备交互测试；仍需要更多对应型号的实机验证。'),
   ('其他设备','只显示已支持的操作或读数。部分存在感应、门窗等设备目前仅在主界面展示名称与在线状态。'),
   ('语言与平台','程序界面目前主要为中文；此网站有中英文介绍。macOS 版在计划中，尚无可下载版本。'),
  ],
  'compat_link':'查看兼容性记录与反馈方法',
  'faq_title':'你可能正想问这些。',
  'faq':[
   ('Windows 怎么控制米家设备？需要安卓模拟器吗？','MijiaDeck 是 Windows 桌面程序，无需安卓模拟器。下载免安装包并用米家 APP 扫码登录后，可查看设备并操作已适配的功能。'),
   ('电脑怎么看小米摄像头？能在外网查看吗？','对兼容型号，点击摄像头卡片或播放按钮打开实时预览。支持通过远程中继查看，不要求电脑与摄像头处于同一局域网；摄像头需在线，网络须允许传输。并非所有型号都已验证。'),
   ('电脑可以给小爱同学发文字指令吗？','可以。选择账号下在线的小爱音箱后输入指令，由该音箱执行。托盘也可控制所选音箱的播放与音量；这不改变电脑的音频输出设备。'),
   ('这是小米官方的米家电脑版吗？','不是。MijiaDeck 是免费开源的第三方项目，与小米、米家官方没有隶属关系。它聚焦桌面快捷查看和控制，不能替代官方 APP 的全部功能。'),
   ('所有米家设备都能用吗？','不能保证。可用控制取决于设备型号、MIoT 规格、固件和账号权限。没有已适配快捷控制或读数的设备，不会出现在托盘添加清单中。'),
   ('更新怎么安装？设置会丢吗？','先从托盘菜单退出，再完整解压新版 ZIP 覆盖旧程序目录。个人配置与登录信息存放在 Windows 用户目录中；不要仅替换 EXE。'),
  ],
  'footer':'基于 MiHome-Windows 改进，采用 GPL-3.0-or-later。与小米、米家官方没有隶属关系。',
  'issues':'反馈问题', 'privacy':'登录与配置说明',
 },
 'en': {
  'lang':'en', 'title':'MijiaDeck · Xiaomi Mi Home desktop client for Windows',
  'description':'A free, open-source third-party Xiaomi Mi Home (Mijia) desktop client for Windows. Control devices, preview compatible cameras remotely and manage XiaoAI speakers from the system tray.',
  'switch':'简体中文', 'switch_url':'../', 'nav':['Features','Compatibility','FAQ'],
  'eyebrow':'Xiaomi Mi Home on Windows 10 / 11',
  'heading':'Your Mi Home devices.<br>Right on your desktop.',
  'intro':'Switch a light, check the temperature, preview a compatible camera or send a text command to a XiaoAI speaker. MijiaDeck brings everyday Mi Home controls to Windows and its system tray.',
  'download':'Download for Windows', 'source':'Source on GitHub',
  'requirements':'Free & open source · x64 portable ZIP · Unofficial client',
  'caption':'Real UI with fictional sample data; no private account, home or camera footage. Screenshots illustrate the interface; available features depend on the release and device.',
  'features_title':'Everyday controls, without reaching for your phone.',
  'features':[
   ('Device-specific cards','Browse devices by home and room. Toggle supported lights, switch channels and outlets; view channel states on parent panels.'),
   ('Remote camera previews','Compatible cameras have a separate preview window with quality selection, mute, fullscreen and drag-to-pan/tilt. Remote relay access does not require the same LAN. Experimental.'),
   ('XiaoAI speakers in your tray','Select a speaker, adjust volume, play, pause or skip tracks. Send text commands to that speaker without speaking aloud.'),
   ('Compact light controls','Brightness, color temperature and RGB controls appear only where supported. Use the Mi Home mobile app for advanced configuration.'),
   ('Run existing scenes','Execute manual scenes already created in the Mi Home app. MijiaDeck does not create, edit or delete automations.'),
   ('Useful quick-access cards','View supported temperature and humidity readings. Choose and reorder tray cards, select one or two columns and remember the popup position.'),
  ],
  'steps_title':'Download. Extract. Open.',
  'steps':[('Download','Get the Windows x64 ZIP from the latest GitHub release. Choose the application archive, not Source code.'),('Open','Extract the complete archive and run MijiaDeck.exe. Keep the _internal folder. No separate Python or Java installation is needed.'),('Sign in','Scan the QR code with the Mi Home app. Click the tray icon for quick controls, or right-click it to open the menu.')],
  'compat_title':'Capabilities, with clear boundaries.',
  'compat':[
   ('Windows','Windows 10 1903+ / Windows 11 x64. Windows 7/8 are unsupported. Full Windows 11 hardware testing is still pending.'),
   ('Switches & readings','Local hardware feedback exists for multi-channel switches and temperature/humidity readings. Compatibility is not guaranteed across every model in a brand.'),
   ('Cameras','Local preview feedback exists for a compatible model. Camera transport is experimental and depends on model, firmware and network conditions.'),
   ('Dimming & colors','The compact control UI has passed simulated-device interaction tests. More physical-device validation is needed.'),
   ('Other devices','Only implemented controls and readouts are offered. Some presence/contact sensors currently show only their name and online state in the main window.'),
   ('Language & platforms','The application UI is currently primarily Chinese; this website is bilingual. A macOS edition is planned, but is not available yet.'),
  ],
  'compat_link':'Compatibility records and feedback guide',
  'faq_title':'A few things to know.',
  'faq':[
   ('Can I control Xiaomi Mi Home devices on Windows without an emulator?','Yes. MijiaDeck is a Windows desktop application. Download the portable ZIP, sign in with the Mi Home app and use the controls supported for your devices.'),
   ('Can I view a Xiaomi camera remotely from my PC?','Compatible models can open a live preview through a remote relay, without sharing the same LAN. The camera must be online and your network must allow the connection. Not all camera models have been verified.'),
   ('Can I control XiaoAI speakers with text commands?','Select an online speaker associated with your account, then enter a command. Playback and volume controls target that speaker; they do not change your PC audio output device.'),
   ('Is this an official Xiaomi Mi Home PC app?','No. MijiaDeck is a free, open-source third-party project with no affiliation to Xiaomi or Mi Home. It focuses on everyday desktop controls, not full mobile-app feature parity.'),
   ('Does every Mi Home device work?','No. Controls depend on the model, MIoT specification, firmware and account permissions. Devices without implemented quick controls or readouts are omitted from the tray selection list.'),
   ('How do I upgrade?','Exit the app from its tray menu, then extract the complete new ZIP over the old application directory. Settings and login data are stored in your Windows user profile. Do not replace only the EXE.'),
  ],
  'footer':'Based on MiHome-Windows. GPL-3.0-or-later. Not affiliated with Xiaomi or Mi Home.',
  'issues':'Report an issue', 'privacy':'Login & configuration',
 },
}


def render(language):
    c = CONTENT[language]
    prefix = '../' if language == 'en' else ''
    url = BASE + ('en/' if language == 'en' else '')
    features = ''.join(f'<article><span class="number">{i:02d}</span><h3>{escape(title)}</h3><p>{escape(body)}</p></article>' for i,(title,body) in enumerate(c['features'],1))
    steps = ''.join(f'<li><h3>{escape(title)}</h3><p>{escape(body)}</p></li>' for title,body in c['steps'])
    compat = ''.join(f'<tr><th scope="row">{escape(title)}</th><td>{escape(body)}</td></tr>' for title,body in c['compat'])
    faq = ''.join(f'<div><dt>{escape(q)}</dt><dd>{escape(a)}</dd></div>' for q,a in c['faq'])
    nav = ''.join(f'<a href="#{target}">{escape(label)}</a>' for target,label in zip(('features','compatibility','faq'),c['nav']))
    schema = {'@context':'https://schema.org','@type':'SoftwareApplication','name':'MijiaDeck',
        'url':BASE,'description':c['description'],'applicationCategory':'LifestyleApplication',
        'operatingSystem':'Windows 10 1903+; Windows 11 x64','softwareVersion':__version__,
        'license':REPO+'/blob/main/LICENSE','offers':{'@type':'Offer','price':'0','priceCurrency':'USD'}}
    return f'''<!doctype html>
<html lang="{c['lang']}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(c['title'])}</title><meta name="description" content="{escape(c['description'])}">
<link rel="canonical" href="{url}"><link rel="alternate" hreflang="zh-Hans" href="{BASE}"><link rel="alternate" hreflang="en" href="{BASE}en/"><link rel="alternate" hreflang="x-default" href="{BASE}">
<meta property="og:type" content="website"><meta property="og:title" content="{escape(c['title'])}"><meta property="og:description" content="{escape(c['description'])}"><meta property="og:url" content="{url}"><meta property="og:image" content="{BASE}images/main-light.png">
<meta name="twitter:card" content="summary_large_image"><link rel="icon" href="{prefix}assets/logo.png"><link rel="stylesheet" href="{prefix}assets/site.css">
<script type="application/ld+json">{json.dumps(schema,ensure_ascii=False)}</script></head>
<body><a class="skip" href="#main">{'跳到正文' if language=='zh' else 'Skip to content'}</a>
<header class="wrap"><a class="brand" href="{prefix or './'}"><img src="{prefix}assets/logo.png" width="32" height="32" alt="">MijiaDeck</a><nav aria-label="{'主导航' if language=='zh' else 'Main navigation'}">{nav}<a href="{c['switch_url']}" lang="{'en' if language=='zh' else 'zh-Hans'}">{c['switch']}</a></nav></header>
<main id="main"><section class="hero wrap"><p class="eyebrow">{c['eyebrow']}</p><h1>{c['heading']}</h1><p class="intro">{c['intro']}</p><div class="actions"><a class="button" href="{REPO}/releases/latest">{c['download']} <span aria-hidden="true">↗</span></a><a class="text-link" href="{REPO}">{c['source']} <span aria-hidden="true">↗</span></a></div><p class="meta">{c['requirements']} <span>v{__version__}</span></p>
<figure class="app-shot"><img src="{prefix}images/main-light.png" width="1740" height="1110" alt="{'MijiaDeck 米家 Windows 桌面设备卡片与房间分类界面示意' if language=='zh' else 'MijiaDeck Windows device cards and room navigation, with fictional sample data'}" fetchpriority="high"><figcaption>{c['caption']}</figcaption></figure></section>
<section id="features" class="wrap section"><p class="eyebrow">{'桌面控制 / DESKTOP CONTROLS' if language=='zh' else 'DESKTOP CONTROLS'}</p><h2>{c['features_title']}</h2><div class="features">{features}</div></section>
<section class="setup"><div class="wrap section"><h2>{c['steps_title']}</h2><ol class="steps">{steps}</ol><a class="text-link" href="{REPO}/releases/latest">{c['download']} ↗</a></div></section>
<section id="compatibility" class="wrap section"><h2>{c['compat_title']}</h2><div class="table-scroll"><table><tbody>{compat}</tbody></table></div><a class="text-link" href="{REPO}/blob/main/docs/COMPATIBILITY.md">{c['compat_link']} ↗</a></section>
<section id="faq" class="wrap section faq"><h2>{c['faq_title']}</h2><dl>{faq}</dl></section></main>
<footer class="wrap"><div class="brand">MijiaDeck</div><p>{c['footer']}</p><div><a href="{REPO}/issues">{c['issues']}</a><a href="{REPO}#下载和使用--download--use">{c['privacy']}</a><a href="{REPO}/blob/main/LICENSE">GPL-3.0-or-later</a></div></footer></body></html>'''


def main():
    docs = ROOT / 'docs'
    (docs/'en').mkdir(exist_ok=True)
    (docs/'assets').mkdir(exist_ok=True)
    (docs/'index.html').write_text(render('zh'),encoding='utf-8')
    (docs/'en/index.html').write_text(render('en'),encoding='utf-8')
    (docs/'assets/logo.png').write_bytes((ROOT/'app/ui/icon.png').read_bytes())
    (docs/'.nojekyll').write_text('',encoding='utf-8')
    (docs/'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>{BASE}</loc></url><url><loc>{BASE}en/</loc></url></urlset>\n',encoding='utf-8')
    (docs/'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {BASE}sitemap.xml\n',encoding='utf-8')


if __name__ == '__main__':
    main()
