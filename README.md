# 静安体育单账号 API 客户端

WSL Ubuntu / Python 3.12 项目，用于读取官方消费券列表、检查本人账号资格，以及按下一轮时间单次领取。默认试运行，只有明确加 --send 才发送领券请求。

## 安装

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

需要本人通过官方小程序完成登录、实名、地址与实际定位。仓库不含个人凭据、定位、原始流量、证书或小程序源码。私人文件只在本机 private/ 中保存，该目录已被 Git 排除。

## 使用

```bash
.venv/bin/python jingan.py list
.venv/bin/python jingan.py doctor
.venv/bin/python jingan.py claim --coupon 4         # 60元券试运行
.venv/bin/python jingan.py claim --coupon 4 --send  # 等到官方下一轮，单次提交
```

Windows 可运行 Run-60.ps1，默认使用 WSL Ubuntu。命令在发券前十分钟启动即可。例如下一轮11:00发券，10:50启动。它先检查配置、登录、资格和时间，发券前20秒再次检查账号并刷新签名密钥，等到官方时间加平台账号等待时间后提交一次，不会提前提交。

运行期间保持电脑开机、网络可用、程序和WSL运行，避免休眠。相同项目同时只能运行一个发送任务。登录过期需通过官方小程序更新会话；当前位置改变时刷新实际定位。首次克隆的仓库没有私人会话，不能直接领券。

默认上游代理为 http://127.0.0.1:7897；可用 --proxy 指定其他代理。此地址只用于网络连接，与账号登录凭据无关。

Rule ID：20/21/22 对应通用5/10/20元券，3/4/5 对应35/60/80元券；以 list 返回的实时数据为准。

## 采集本人会话

Windows 运行 Start-Capture.ps1，采集代理位于本机127.0.0.1:18080，保留原系统代理作为上游。首次HTTPS调试证书安装需要用户确认，两小时后由WSL守护进程恢复原代理。Windows证书删除若需要交互确认，需用户完成；Restore-Capture.ps1 可提前停止。

Clash Verge 如开启 Proxy Guard，会周期性把系统代理回写到原端口，影响采集。调试期间临时关闭该自动维护选项，采集结束恢复。日常运行领券脚本不需要开启采集代理，也不需要关闭 Proxy Guard。

重新进入小程序，并在官方页面手动登录。private/index.json 仅记录JSON API元数据；最多300条原始请求暂存在内存。用 export_flow.py FLOW_ID NAME 导出本人所需请求，例如登录后 /api/v1/user/info 请求。然后：

```bash
.venv/bin/python jingan.py import-session private/flows/user-info/request.json
```

private/location.json 必须保存本人的真实设备位置，可参考 config/location.example.json。import_location.py 仅从已采集的小程序附近场馆请求中导入实际定位；不要用任意坐标替代本人位置。

## 接口与验证

已观测官方业务域名 shgypsapi.linkingfit.club，GET /api/v1/home/coupons?area_code=5、/api/v1/user/info、/api/v1/app/sign。领取为 POST /api/v1/coupon，包含 rule_id、实际位置 l 与签名 sign。

签名由本人Token、北京时间小时和Rule ID组成，采用官方客户端的AES-CBC/PKCS7协议，密钥通过官方 app/sign 获取。保留平台的 user_type_time 等待时间及实名、地址、实际定位条件。

16项离线测试通过，签名与独立Node crypto对照一致；官方券列表、本人登录资格和签名密钥读取已实测。一次当前售罄券的真实领取请求返回业务码40000、“消费券已经被领取完”。尚未成功领取，不保证库存及成功率。

HTTP 200不等于领取成功。超时、验证码、限流、登录失效和未知结果不自动循环提交；超时应先查本人券包。
