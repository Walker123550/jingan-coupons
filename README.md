# 静安体育单账号 API 客户端

Windows原生或WSL/Linux + Python 3.12 项目，用于读取官方消费券列表、检查本人账号资格，并按官方轮次时间领取。

**尚未成功领取消费券。** 已验证券列表、账号资格、签名格式和售罄业务响应。2026年10月13日用户报告的拥堵提示没有旧版返回码记录，原因不能还原，不保证领取成功。

接手运行请先阅读 [交接说明](docs/HANDOFF.md)；已处理问题和剩余边界见 [通用性检查](docs/REVIEW.md)。

2026-10-20 登录恢复修复：Windows和WSL各通过41项测试。当前本机会话仍返回50001，尚未恢复领取条件。详见 [登录恢复状态](docs/SESSION-RECOVERY.md)。import-session现在会先验证候选会话再替换，失败时保留原文件。

## 安装

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

本次验证环境为Windows64位原生Python3.12和WSL Ubuntu，两种环境均通过32项测试。无需WSL的安装、启动和采集步骤见 [Windows原生说明](docs/WINDOWS.md)。原有Start-Capture.ps1采集入口仍需要WSL。requirements.lock.txt仅为WSL环境快照；Windows请使用Setup-Windows.ps1。

仓库不含本人会话、Token、定位、原始流量、证书或第三方小程序源码。它们仅存于被Git忽略的private/。新克隆可以读取公开券列表，实际领取需要配置本人会话和实际位置，步骤见交接说明。

## 常用命令

```bash
.venv/bin/python jingan.py list
.venv/bin/python jingan.py doctor
.venv/bin/python jingan.py claim --coupon 4         # 60元券试运行
.venv/bin/python jingan.py claim --coupon 4 --send  # 当日轮次发送
.venv/bin/python jingan.py logs                    # 最近一次真实发送任务日志
.venv/bin/python jingan.py bag                     # 查询券包
```

在发券前十分钟启动。例如当天11:00发券，10:50启动；发券前20秒重新验证资格和刷新密钥，到官方时间加平台账号等待时间后提交。保持窗口、电脑、WSL和网络运行，避免休眠；相同项目只运行一个发送任务。

默认发送仅允许当日轮次，避免迟到启动后悄悄转去等明天。有明确跨日计划时使用 --at 指定完整日期时间。系统自动校时应开启。

Windows原生入口：Run-Windows.ps1 -CouponId 4，试运行加 -DryRun，详见Windows原生说明。WSL入口：Run.ps1 -CouponId 4；试运行加 -DryRun，发行版可用 -Distro 指定。也保留Run-60.ps1。

## 网络

新安装默认直连。命令行、JINGAN_PROXY环境变量和private/config.json均可指定HTTP/HTTPS代理。原电脑7897端口不是项目的通用默认值。命令行全局选项放在子命令之前：

```bash
.venv/bin/python jingan.py --proxy direct list
.venv/bin/python jingan.py --proxy http://127.0.0.1:7897 doctor
```

配置示例：config/network.example.json、config/location.example.json。不要把实际配置或凭据上传仓库。

## 日志、结果与重试

每次运行保存private/runs/*.jsonl，含时间、预检、提交、HTTP状态、业务码和结果，不记录凭据、签名、精确位置。logs优先选择真实发送任务。

HTTP200不代表成功。success要求业务成功码和有效期，之后仍应确认官方券包。超时是结果未知，先查券包。售罄、未知拥堵、限流、登录失效不循环重发。仅对已确认的40013签名密钥拒绝，按照官方客户端逻辑刷新密钥并最多重提一次。

Press any key to continue是启动文件的暂停提示，按键不会重抢。

## 采集和协议

Start-Capture.ps1支持Distro和UpstreamProxy；Restore-Capture.ps1恢复原代理。采集只保留shgypsapi.linkingfit.club业务JSON请求。Clash Proxy Guard若周期性回写系统代理，采集期间临时关闭，结束后恢复；日常领取无需修改它。Windows证书安装、删除确认需用户手动完成。

已观测GET /api/v1/home/coupons?area_code=5、/api/v1/user/info、/api/v1/app/sign。领取POST /api/v1/coupon，包含rule_id、实际位置l和sign。采用官方客户端的AES-CBC/PKCS7签名协议，保留实名、地址、实际定位及user_type_time等待时间。

Rule ID 20/21/22为通用5/10/20元券，3/4/5为35/60/80元券，以实时list为准。GitHub保存源码，不会自动为使用者运行或抢券。
