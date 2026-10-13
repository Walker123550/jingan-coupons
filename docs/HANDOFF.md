# 接手运行说明

更新：2026年10月13日。目标是静安体育通用60元券（Rule ID 4，满100元使用）。请先用实时列表核对日期、时间与规则。

## 当前验证范围

已验证官方券列表读取、本人账号登录、实名与地址检查、实际定位导入、AES签名格式和失败业务响应。尚未成功领取消费券，成功领取流程没有实测证明，不保证领取成功。

2026年10月12日曾向确认售罄的20元券发送一次请求，服务端返回40000、“消费券已经被领取完”。10月13日用户报告60元券返回“太多人抢了，请再试一次”；旧版没有保存那次返回码，不能确认具体原因。后续版本已补齐日志。

## 沿用现有电脑

1. 在已有项目目录打开 WSL，运行下面的 `doctor` 和试运行，不需要重新克隆或安装。日常领取不要求微信和小程序常驻；程序使用本机已保存的会话。
2. 检查登录、实名和地址。若会话过期，必须在官方小程序中手动重新登录并采集，不能靠重复启动修复。
3. 核对本机实际位置。当前位置改变时，需要刷新小程序真实定位，不得沿用不符的位置。
4. 检查网络和代理。原电脑的网络配置保存在 `private/config.json`；这一配置不会上传GitHub。
5. 在目标发券前十分钟启动发送任务。只启动一个窗口，保持电脑、WSL和网络运行，避免休眠。

```bash
.venv/bin/python jingan.py list
.venv/bin/python jingan.py doctor
.venv/bin/python jingan.py claim --coupon 4
.venv/bin/python jingan.py claim --coupon 4 --send
```

当前电脑已有的 Windows 入口：`检查领券账号.cmd`、`试运行60元券.cmd`、`抢60元券.cmd`、`查看运行日志.cmd`、`检查券包.cmd`。入口位于原来的 outputs 文件夹。最后两个用于查看结果。

## 换电脑或新克隆

支持范围：Linux/WSL客户端；本次测试环境为Windows 64位、WSL Ubuntu、Python 3.12。Windows原生Python直接运行未支持，客户端依赖Linux进程锁。Windows采集脚本需64位PowerShell、可用的WSL发行版，并将仓库放在可从Windows访问的目录中。

仓库为私有仓库。接手人的GitHub账号需要已有访问权限，或由仓库所有者提供不含私人文件的源码副本。本项目不会自动添加协作者或发送凭据。

```bash
git clone https://github.com/Walker123550/jingan-coupons.git
cd jingan-coupons
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

推荐使用Python 3.12。若Ubuntu缺少venv组件，先安装与当前Python匹配的venv包，再创建虚拟环境。不同发行版的包名和权限由接手人自行确认。

首次克隆不包含会话、位置或网络配置。此时 `list` 可以匿名读取公开券列表；`doctor` 和实际领取必须先配置本人会话。

### 网络配置

新克隆默认直连，不依赖原电脑的7897端口。三种配置方式，优先顺序为：命令行、JINGAN_PROXY环境变量、本机配置文件。

```bash
# 明确直连
.venv/bin/python jingan.py --proxy direct list

# 显式使用WSL能够访问的HTTP代理；端口按自己的环境调整
.venv/bin/python jingan.py --proxy http://127.0.0.1:7897 list

# 保存为本机配置，随后编辑proxy字段
mkdir -p private
cp config/network.example.json private/config.json
```

配置文件的proxy可为null（直连）或HTTP/HTTPS代理URL。7897只是原电脑示例，不是项目必需端口。WSL的127.0.0.1是否能访问Windows代理取决于网络模式，须实际测试；必要时配置WSL可达的代理地址。

### 本人会话和位置

在Windows PowerShell中运行 `Start-Capture.ps1`。可用 `-Distro` 指定已安装的WSL发行版，可用 `-UpstreamProxy host:port` 指定WSL可达的上游代理。首次证书信任和删除证书的Windows提示需用户手动确认。

若Clash开启Proxy Guard，临时关闭它，再启动采集；该选项会周期性覆盖系统代理。采集结束恢复该选项。日常领取不需要开启采集或关闭Proxy Guard。

在官方小程序中手动登录并进入“我的”，然后进入首页获取真实位置。采集器只保留目标业务域名 `shgypsapi.linkingfit.club` 的JSON请求。使用下面的命令查看索引，在里面寻找登录后 `/api/v1/user/info` 请求及包含非空latitude、longitude的 `/api/v1/businesses` 请求。

```bash
.venv/bin/python -m json.tool private/index.json
.venv/bin/python export_flow.py PROFILE_FLOW_ID user-info
.venv/bin/python jingan.py import-session private/flows/user-info/request.json
.venv/bin/python export_flow.py LOCATION_FLOW_ID businesses
.venv/bin/python import_location.py
.venv/bin/python jingan.py doctor
```

PROFILE_FLOW_ID和LOCATION_FLOW_ID要替换成当前索引中的真实id，不能使用其他人的请求。没有定位时先在官方小程序处理定位授权。不要公开 `private/`；它包含Token、个人资料、真实位置、证书和原始请求。

在Windows执行 `Restore-Capture.ps1` 结束采集，确认原代理已恢复。如果Windows弹出删除临时证书的确认窗口，由用户处理；若删除未完成，检查 `private/certificate-cleanup-pending.json`。恢复Clash Proxy Guard。

## 明天的操作顺序

若10月14日实时列表仍显示60元券11:00发放：

- 10:40：运行 `doctor`，核对网络、账号资格和真实位置；运行 `list` 核对券档。
- 10:50：运行 `claim --coupon 4 --send`，核对输出的 `at` 为当天11:00加官方账号等待时间。
- 11:00后：看窗口结果，再运行 `logs` 和 `bag`。保留本次日志，不要看到窗口结束就认定成功。

脚本默认仅发送到当日轮次。如果启动时官方下一轮已经变成明天，它会报错停止，不会悄悄转去等待明天。需要跨日等待时，必须显式指定目标：

```bash
.venv/bin/python jingan.py claim --coupon 4 --at '2026-10-14T11:00:00+08:00' --send
```

日期只是示例，必须用实际计划日期。不要同时运行默认入口和跨日入口。

Windows仓库内通用入口：

```powershell
.\Run.ps1 -CouponId 4 -DryRun
.\Run.ps1 -CouponId 4
.\Run.ps1 -CouponId 4 -Distro Ubuntu
```

## 结果和日志

```bash
.venv/bin/python jingan.py logs
.venv/bin/python jingan.py bag
```

日志位于 `private/runs/*.jsonl`。`logs` 优先显示最近一次真实发送任务，不会被后面的doctor、bag或试运行覆盖。记录包括启动时间、目标时间、预检、提交时间、HTTP状态、业务码和最终结果，不记录Token、签名或精确位置。原始日志保留在本机，不上传GitHub。

| 状态或现象 | 含义与操作 |
|---|---|
|success|业务响应包含成功码和有效期；再在官方券包中确认|
|sold_out|明确返回已领完；本轮结束，不循环提交|
|signature_rejected|40013签名密钥拒绝；程序按官方客户端逻辑刷新密钥后最多再提交一次，仍失败则停止|
|business_rejected|其他业务拒绝；保留code和message。今天的拥堵提示具体返回码未知，不自动重试|
|rate_limited|HTTP429；停止，查看retry_after，不绕过限制|
|transport_error_result_unknown|网络超时或连接异常，结果未知；先查官方券包，不直接重发|
|configuration_or_login_required|查看reason和日志中的API状态，区分登录、配置、时间或接口变更|
|another_claim_process_is_running|已有一个发送任务；保留一个窗口|
|Next release is not today|当日轮次已过或选择了次日；当天任务停止|
|Press any key to continue|CMD启动文件的暂停提示；按键只会结束窗口，不会重抢|

除已确认的40013密钥刷新外，不会自动循环重发。成功流程、拥堵情况下的领取效果和会话有效期仍需实际验证。

## 交接时须确认

代码已更新并通过测试；接手人在目标电脑上完成一次doctor和试运行；有真实位置；知道本次发券时间；能保持电脑开机；能读取日志并查询官方券包。更换账号需账号本人手动登录，GitHub源码不能代替会话。
