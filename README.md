# Free VPN 订阅聚合站

这个项目把公开的免费 V2Ray / Clash / Shadowsocks 订阅源聚合成一个仓库，并用
GitHub Actions 每天自动更新，生成可一键导入的分组订阅链接。

> 使用提示：免费节点会频繁失效或高速率波动，请自行选择可信的来源；本项目只做
> 聚合与整理，不托管任何加密流量。

## 一键订阅链接

把下面的 `raw.githubusercontent.com` 链接粘贴到 Clash / V2RayN / Shadowrocket /
Quantumult X 等客户端即可。

| 分类 | 链接 |
| --- | --- |
| 全部节点 | [sub/all.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/all.txt) |
| 解锁 ChatGPT | [sub/features/chatgpt.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/features/chatgpt.txt) |
| 解锁 Netflix | [sub/features/netflix.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/features/netflix.txt) |
| 解锁 Disney+ | [sub/features/disney.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/features/disney.txt) |
| 解锁 YouTube | [sub/features/youtube.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/features/youtube.txt) |
| 解锁 TikTok | [sub/features/tiktok.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/features/tiktok.txt) |
| 流媒体合集 | [sub/features/streaming.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/features/streaming.txt) |
| 美国节点 | [sub/by-country/US.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-country/US.txt) |
| 香港节点 | [sub/by-country/HK.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-country/HK.txt) |
| 日本节点 | [sub/by-country/JP.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-country/JP.txt) |
| 新加坡节点 | [sub/by-country/SG.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-country/SG.txt) |
| 韩国节点 | [sub/by-country/KR.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-country/KR.txt) |
| V2Ray (vmess/vless) | [sub/by-protocol/vmess.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-protocol/vmess.txt) |
| Trojan | [sub/by-protocol/trojan.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-protocol/trojan.txt) |
| Shadowsocks | [sub/by-protocol/ss.txt](https://raw.githubusercontent.com/jiuzihe36/free-vpn-sub/main/sub/by-protocol/ss.txt) |

把链接里的 `jiuzihe36/free-vpn-sub` 替换成自己的 GitHub 用户名和仓库名即可。
如果你不改仓库名，也可以通过仓库设置里的 Pages 或 GitHub raw 域名获得同样的链接。

## 本地生成

```bash
python3 scripts/aggregate.py
```

脚本会读取 `data/sources.json` 里的公开订阅源，自动去重、分类，并写入 `sub/`。

## 数据结构

```text
sub/
├── all.txt                      # 全部节点
├── meta.json                    # 更新时间、数量统计
├── by-protocol/                 # 按协议分
│   ├── vmess.txt
│   ├── vless.txt
│   ├── trojan.txt
│   ├── ss.txt
│   └── ...
├── by-country/                  # 按地区分
│   ├── US.txt
│   ├── JP.txt
│   └── ...
└── features/                    # 按功能标签分
    ├── chatgpt.txt              # 解锁 ChatGPT / OpenAI
    ├── netflix.txt
    ├── disney.txt
    ├── youtube.txt
    ├── tiktok.txt
    └── streaming.txt
```

## 标签是怎么判定的

脚本通过节点名里的关键词来打标签，比如：

- `chatgpt` / `openai` / `gpt` → ChatGPT 解锁
- `netflix` / `nf` → Netflix 解锁
- `disney` → Disney+ 解锁
- `youtube` / `yt` → YouTube 解锁
- `tiktok` → TikTok 解锁
- 上述任一 → `streaming`

地区标签则识别常见国家/地区代码和城市名。免费节点不一定写清楚解锁能力，这类
标签只代表节点名声明过，不代表 100% 可用，建议导入后自己测一下。

如果某个标签文件为空，说明当前聚合源里没有明确标注该标签的节点；可以往
`data/sources.json` 里补充带这个标签的订阅源，脚本会自动重新分类。

## 新增订阅源

编辑 `data/sources.json`，把包含免费订阅的 raw 链接加进去，然后重新运行聚合
脚本即可。

如果整个订阅源都被认为支持某个功能，也可以用对象形式给这个源统一打标签：

```json
{
  "url": "https://raw.githubusercontent.com/example/free-nodes/main/sub.txt",
  "tags": ["chatgpt", "streaming"]
}
```

## 免责声明

- 免费节点来自公开互联网项目，速度、可用性、安全性都不能保证。
- 请遵守所在地区和目标服务的法律法规。
- 不要用它传输敏感或违法内容。
- 所有节点的版权归原始发布者所有。
