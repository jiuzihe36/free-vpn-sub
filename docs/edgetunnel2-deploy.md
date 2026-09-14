# edgetunnel2 傻瓜式部署（Cloudflare Pages 上传法）

> 这是 cmliu/edgetunnel2 官方推荐最简单的方法，全程不用命令行，也不用 Fork。

## 准备工作

- 一个 Cloudflare 账号：https://dash.cloudflare.com/
- 一个邮箱密码，登录用
- 可选：一个域名，并且 DNS 已经迁到 Cloudflare 下

## 第一步：下载项目压缩包

下载最新代码：

- https://github.com/cmliu/edgetunnel/archive/refs/heads/main.zip

下载完不要解压，后面直接上传 zip。

## 第二步：创建 Cloudflare Pages

1. 打开 Cloudflare 控制台
2. 左侧菜单选择 **Workers 和 Pages**
3. 点 **创建** > **Pages** > **上传资产**
4. 项目名称随便填，例如 `edgetunnel`
5. 点 **创建项目**
6. 把 `main.zip` 拖进去上传
7. 点 **部署站点**
8. 部署完点 **继续处理站点**

## 第三步：设置后台密码

1. 进入 Pages 项目
2. 打开 **设置** > **环境变量**
3. 点 **制作**，为生产环境定义变量
4. 添加变量：
   - 变量名称：`ADMIN`
   - 值：你自己设置的后台密码，比如 `123456`
5. 点击 **保存**
6. 回到 **部署** 页面
7. 右上角点 **创建新部署**
8. 重新上传 `main.zip`
9. 点 **保存并部署**

## 第四步：绑定 KV 命名空间

edgetunnel2 需要绑定一个 KV，用于记录日志/状态。

1. 进入 **设置** > **绑定**
2. 点 **添加绑定** > **KV 命名空间**
3. 如果还没有 KV，就现场创建一个，例如叫 `edgetunnel_kv`
4. 变量名称必须填：`KV`
5. 保存后，重新创建一次部署

## 第五步：访问后台 / 获取订阅

部署成功后，你会得到一个默认域名：

```text
https://edgetunnel.pages.dev
```

后台地址：

```text
https://edgetunnel.pages.dev/admin
```

输入你设置的 `ADMIN` 密码即可进入管理面板。

订阅地址：项目支持 `KEY` 变量，如果设置过：

```text
https://edgetunnel.pages.dev/你的KEY
```

这个订阅地址可以直接填进 NekoBox / v2rayNG / Clash。

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

## NekoBox 导入

安卓推荐 NekoBox：

1. 打开 NekoBox
2. 点右上角 **+**
3. 选择 **从 URL 导入**
4. 粘贴 edgetunnel2 给你的订阅地址
5. 保存后连接即可

## 常见问题

- **Error 1101**：通常是 Workers/Pages 执行失败，更新代码后重新部署。
- 后台登录不了：检查 `ADMIN` 环境变量是否生效，并重新部署过。
- 速度慢：免费 CF 额度有限，属于正常现象；优先选地区近的出口。
- 免费节点不稳定：edgetunnel2 适合轻量使用，不适合大流量下载。

## 官方资料

- 项目仓库：https://github.com/cmliu/edgetunnel
- 官方图文教程：https://cmliussss.com/p/edt2/
- Error 1101 解析：https://www.youtube.com/watch?v=r4uVTEJptdE
