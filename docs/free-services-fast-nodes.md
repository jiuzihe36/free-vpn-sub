# 免费服务搭建高速节点：GitHub 项目清单

> 注意：免费额度通常只适合轻量使用，不能保证高速。真正高速稳定还是付费机场
> 或自建 VPS 更靠谱。

## Cloudflare Workers / Pages

- [cmliu/edgetunnel](https://github.com/cmliu/edgetunnel): 45k+ star，基于 Cloudflare Workers/Pages 的 VLESS/Trojan/SS 多功能面板，最常用
- [zizifn/edgetunnel](https://github.com/zizifn/edgetunnel): 在 edge/serverless runtime 里跑 V2Ray 的早期经典项目
- [6Kmfi6HP/EDtunnel](https://github.com/6Kmfi6HP/EDtunnel): Cloudflare Workers/Pages 代理工具，支持多种协议
- [code3-dev/foxcloud](https://github.com/code3-dev/foxcloud): 高性能 VLESS 代理 for Cloudflare Workers
- [Surfboardv2ray/v2ray-worker-sub](https://github.com/Surfboardv2ray/v2ray-worker-sub): 基于 Worker 的免费 v2ray 订阅生成器

## Railway / Render / Serverless

- [MHDLabs/FreeNET](https://github.com/MHDLabs/FreeNET): Railway 上的 VLESS/Trojan/XHTTP 轻量代理，不用面板
- [markwilliams123456/railway-xray](https://github.com/markwilliams123456/railway-xray): Railway 免费 tier 部署 Xray VLESS+Reality

## 无需代理内核的 Python / Java

- [eooce/python-ws](https://github.com/eooce/python-ws): 2.8k+ star，纯 Python 起 VLESS/Trojan/SS，适合有任意公网服务器的环境
- [eooce/java-ws](https://github.com/eooce/java-ws): 同作者 Java 版本

## 免费订阅处理

- [AmirHosseinJPL/Jpl-sub-processor](https://github.com/AmirHosseinJPL/Jpl-sub-processor): Cloudflare Worker 订阅处理 + 测活 + ping

## 使用提醒

- Cloudflare Workers 免费版有 10 万请求/日限制，且部分国家线路不稳定，不适合跑大流量
- Railway/Render 免费实例可能休眠、随机换域名，只适合临时测试
- 免费服务搭建的节点更建议做轻量访问，不建议当主用高速节点
- 要真正高速稳定，仍然优先考虑付费机场或自建 VPS + Reality/Hysteria2
