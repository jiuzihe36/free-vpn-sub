# edgetunnel2 傻瓜式部署（Cloudflare Pages 上传法）

> 这是 cmliu/edgetunnel 官方推荐最简单的方法，不用命令行、不用 Fork、不用服务器，
> 只需要一个 Cloudflare 免费账号。部署完成会得到自己的 VLESS/Trojan 订阅地址，
> 可以直接填进 NekoBox、v2rayNG、Clash 等客户端。

## 你要准备什么

- 一个 Cloudflare 账号：https://dash.cloudflare.com/
- 登录密码
- 可选：一个域名，并且 DNS 已经迁到 Cloudflare 下

本仓库已经内置了官方 `main.zip`，方便下载：

```text
deploy/edgetunnel2-main.zip
```

也可以直接下载官方最新版：

```text
https://github.com/cmliu/edgetunnel/archive/refs/heads/main.zip
```

下载完不要解压，后面直接上传 zip。

## 一键 API 自动部署（推荐给小白）

仓库里已经放好了一键部署脚本，只要有两个东西就能自动创建 Cloudflare Pages 项目、
创建 KV、设置 `ADMIN` / `KEY` / `UUID` / `PROXYIP`、上传 `main.zip`、返回订阅地址：

```bash
export CLOUDFLARE_API_TOKEN=你的CloudflareAPI令牌
export CLOUDFLARE_ACCOUNT_ID=你的账号ID
export EDGETUNNEL_ADMIN=你自己想的后台密码
export EDGETUNNEL_KEY=mykey
python3 scripts/deploy_edgetunnel2.py
```

不设置 `EDGETUNNEL_ADMIN` 时会自动生成一个随机密码并打印出来。

### 怎么拿到 API 令牌

1. 打开 https://dash.cloudflare.com/profile/api-tokens
2. 点 **创建令牌**
3. 选 **自定义令牌** → **开始**
4. 权限选择：
   - 账号 → Cloudflare Pages → 编辑
   - 账号 → Workers KV Storage → 编辑
5. 账号资源选你的主账号
6. 创建后复制令牌

账号 ID 在 Cloudflare 仪表盘右侧 **API** 一栏能看到，通常是一串 32 位十六进制。

### GitHub Actions 自动部署（可选）

仓库里已经加了 `.github/workflows/deploy-edgetunnel2.yml`。往 GitHub 仓库的
`Settings -> Secrets and variables -> Actions` 里添加：

- `CLOUDFLARE_API_TOKEN`
- `CLOUDFLARE_ACCOUNT_ID`

然后去 Actions 里手动运行 **Deploy edgetunnel2**，输入后台密码和 `KEY` 即可。
这样以后你只要重新运行这个 Action，就能自动重新部署。

## 第一步：创建 Cloudflare Pages 项目

1. 打开 Cloudflare 控制台
2. 左侧菜单选择 **Workers 和 Pages**
3. 点 **创建** > **Pages** > **上传资产**
4. 项目名称随便填，例如 `edgetunnel`
5. 点 **创建项目**
6. 把 `edgetunnel2-main.zip` 拖进去上传
7. 点 **部署站点**
8. 部署完点 **继续处理站点**

到这一步，你的项目已经先跑起来了，但还没有后台密码，所以要继续设置环境变量。

## 第二步：设置后台密码和订阅地址

1. 进入 Pages 项目
2. 打开 **设置** > **环境变量**
3. 点 **制作**，为生产环境定义变量
4. 添加以下变量（推荐至少设置前两个）：

| 变量名 | 必填 | 示例 | 作用 |
| --- | --- | --- | --- |
| `ADMIN` | 是 | `123456` | 后台管理面板登录密码 |
| `KEY` | 否 | `mykey` | 订阅路径密钥，填了就能用 `/mykey` 快速获取订阅 |
| `UUID` | 否 | `90cd4a77-141a-43c9-991b-08263cfe9c10` | 固定节点 UUID，必须是 UUIDv4 格式 |
| `PROXYIP` | 否 | `proxyip.cmliussss.net:443` | 自定义反代 IP，速度慢时可以换 |
| `URL` | 否 | `1101` | 主页伪装，填 `1101` 或一个网页 URL |

5. 点 **保存**
6. 回到 **部署** 页面
7. 右上角点 **创建新部署**
8. 重新上传 `edgetunnel2-main.zip`
9. 点 **保存并部署**

> 改完环境变量后一定要重新上传一次 zip 部署，否则不生效。

如果你不知道怎么生成 UUIDv4，可以开一个在线工具，例如：

```text
https://www.uuidgenerator.net/
```

也可以本机跑：

```bash
uuidgen | tr 'A-Z' 'a-z'
```

## 第三步：绑定 KV 命名空间

edgetunnel2 需要用 KV 记录后台状态和日志。

1. 进入 **设置** > **绑定**
2. 点 **添加绑定** > **KV 命名空间**
3. 如果还没有 KV，点 **创建新命名空间**，例如叫 `edgetunnel_kv`
4. 变量名称必须填：`KV`
5. 点 **保存**
6. 回到 **部署** 页面，再重新创建一次部署

## 第四步：拿到你的订阅地址

部署成功后，你会得到一个默认域名：

```text
https://edgetunnel.pages.dev
```

注意：实际域名可能是 `https://edgetunnel.pages.dev` 的变体，例如项目名重复时会变成
`https://edgetunnel-35x.pages.dev`。**以脚本输出或 Cloudflare 控制台里的真实域名
为准**，不要只看项目名拼地址。

如果你设置了 `KEY=mykey`，那订阅地址就是：

```text
https://edgetunnel.pages.dev/mykey
```

后台地址是：

```text
https://edgetunnel.pages.dev/admin
```

输入你设置的 `ADMIN` 密码即可进入管理面板，里面可以直接改节点、复制更多协议。

## 第五步：NekoBox 导入

1. 打开 NekoBox
2. 点右上角 **+**
3. 选择 **从 URL 导入**
4. 粘贴你的订阅地址，例如：

```text
https://edgetunnel.pages.dev/mykey
```

5. 保存后连接即可

如果你的 NekoBox 1.42 报错，优先检查订阅地址是不是填错了，以及 `KEY`/`UUID`
变量有没有重新部署生效。

## 第六步（推荐）：绑定自定义域名

默认 `*.pages.dev` 能用，但被封/不稳定概率更高。绑定自定义域名会更稳。

1. 在 Pages 项目打开 **自定义域**
2. 点 **设置自定义域**
3. 输入你的二级域名，例如 `lizi.fuck.cloudns.biz`，注意不要用根域名
4. 按 Cloudflare 提示，去你的 DNS 服务商添加一条 CNAME：
   - 主机记录：`lizi`
   - CNAME 目标：`edgetunnel.pages.dev`
5. 回到 Cloudflare 点 **激活域**

绑定成功后把前面的 `edgetunnel.pages.dev` 替换成你的自定义域名即可。

## 真实带宽与速度预期

- edgetunnel2 走的是 Cloudflare 免费额度，适合轻量、应急、临时访问。
- 免费额度下速度通常不稳定，即使部署成功，也不等于高速机场。
- 如果你需要稳定高速，还是优先自建 VPS + Realitiy/Hysteria2，或付费机场。
- 如果你的拨号速度慢，可以在后台尝试改成 `PROXYIP=proxyip.cmliussss.net:443`，
  或换一个受欢迎的反代 IP。

## 常见问题

- **Error 1101**：通常是 Workers/Pages 执行失败，重新上传 `main.zip` 再部署一次。
- 后台登录不了：检查 `ADMIN` 环境变量是否生效，并重新部署过。
- 订阅接口打不开：检查 `KEY` 变量是否配置，并确认访问路径和变量值一致。
- 速度慢：免费 CF 额度有限，属于正常现象；优先选地区近的出口。
- 免费节点不稳定：edgetunnel2 适合轻量使用，不适合大流量下载。

## 官方资料

- 项目仓库：https://github.com/cmliu/edgetunnel
- 官方图文教程：https://cmliussss.com/p/edt2/
- Error 1101 解析：https://www.youtube.com/watch?v=r4uVTEJptdE
