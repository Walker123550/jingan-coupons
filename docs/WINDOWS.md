# Windows 原生使用说明（无需 WSL）

已在 Windows 64 位、Python 3.12 上验证安装、32项测试、账号检查及60元券试运行。未实测成功领取，不保证抢到。这里的入口都不调用 WSL。

## 首次安装

1. 安装64位 Python 3.12，安装时启用 Python Launcher。下载仓库源码或交接ZIP，解压到普通可写文件夹。
2. 在项目文件夹打开 Windows PowerShell，运行：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Setup-Windows.ps1 -WithCapture
```

这会创建本机专用 `.venv-win`、安装依赖并运行测试。只运行客户端、不需要重新采集时，可以省略 `-WithCapture`。若找不到Python，用 `-PythonPath 'C:\实际目录\python.exe'` 指定已安装的Python3.12。不要复制其他电脑的虚拟环境。

安装依赖需要网络；失败时查看安装窗口的报错。Windows需要的时区数据包含在依赖中。`requirements.lock.txt` 是原WSL环境快照，含Linux专用包，不能用于Windows安装。

## 日常使用

在项目文件夹打开PowerShell：

```powershell
# 公开券列表，新解压即可查看
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Windows.ps1 -Action list
# 账号资格检查（需要先配置会话）
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Windows.ps1 -Action doctor
# 60元券试运行，不发送领取请求
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Windows.ps1 -CouponId 4 -DryRun
# 发券前十分钟运行，保持窗口、电脑和网络运行，避免休眠
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Windows.ps1 -CouponId 4
# 查看结果和券包
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Windows.ps1 -Action logs
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Run-Windows.ps1 -Action bag
```

也可双击仓库根目录的 `Run-Windows.cmd`，默认进入60元券真实发送；试运行、检查账号等请用上述参数。默认发送只允许当天轮次，提前一天运行会停止。确认具体计划后可加 `-At '2026-10-14T11:00:00+08:00'`，日期必须按实际计划修改。

默认直连；需要代理时加 `-Proxy 'http://127.0.0.1:自己的端口'`，或保存到 `private/config.json`。原电脑7897端口不是通用默认值。一次只启动一个发送任务，WSL入口和Windows入口也不要并行使用。

会话仍有效时，微信、小程序无需常驻。会话过期时，需要本人在官方小程序重新登录并采集。GitHub和交接ZIP没有Token和定位，换电脑不会自动带上这些数据。本人会话用于识别领券账号，真实定位是官方请求所需字段；不得使用别人的账号凭据或编造位置。

## 新电脑首次配置会话和定位

本节采集工具在Windows前台运行；**不会自动修改或恢复系统代理、不会自动安装或删除证书**。操作时务必记下原代理设置，结束后按第7步恢复。不要使用需要WSL的 `Start-Capture.ps1` / `Restore-Capture.ps1`。

1. 已执行 `Setup-Windows.ps1 -WithCapture`。记录Windows原有代理设置；若Clash的Proxy Guard会覆盖系统代理，采集期间临时关闭。
2. 在项目PowerShell窗口启动采集，保持窗口打开：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-Windows-Capture.ps1
# 如果直连目标接口不可达，指定本机HTTP上游代理，例如：
# powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\Start-Windows-Capture.ps1 -UpstreamProxy 127.0.0.1:7897
```

3. Windows设置 → 网络和Internet → 代理，手动设置HTTP代理地址 `127.0.0.1`，端口 `18080`。浏览器访问 `http://mitm.it`，按页面说明手动信任本次项目 `private/mitm` 生成的Windows调试证书。若这台电脑已有同名mitmproxy证书，记录新证书的指纹，结束时只删除本次证书。
4. 重新打开微信小程序，本人手动登录、进入“我的”，再进入首页并完成定位授权。采集仅保存目标域名的JSON请求。另开一个项目PowerShell窗口，查看索引：

```powershell
$env:PYTHONUTF8='1'
& .\.venv-win\Scripts\python.exe -m json.tool private/index.json
```

5. 找到登录后的 `/api/v1/user/info` 请求，以及带非空经纬度的 `/api/v1/businesses` 请求。下面占位符替换为本次索引的真实id；采集窗口须仍在运行，索引只保留最近300条：

```powershell
& .\.venv-win\Scripts\python.exe export_flow.py PROFILE_FLOW_ID user-info
& .\.venv-win\Scripts\python.exe jingan.py import-session private/flows/user-info/request.json
& .\.venv-win\Scripts\python.exe export_flow.py LOCATION_FLOW_ID businesses
& .\.venv-win\Scripts\python.exe import_location.py
```

6. 确认导入完成。私人数据仅保存在 `private/`，不要上传、公开或打包给其他账号使用。移动位置后重新获取真实定位。
7. 在采集窗口按Ctrl+C停止；恢复Windows原代理设置，在当前用户证书管理器 `certmgr.msc` 的“受信任的根证书颁发机构”中按记录的指纹删除本次临时mitmproxy证书。恢复Clash Proxy Guard。随后执行 `doctor` 和试运行。

未收到请求时，先检查系统代理是否仍为18080、微信是否重新打开、Proxy Guard是否改回其他端口。证书不受信任会导致HTTPS失败，需本人处理系统确认。结束后应恢复正常网络。

## 查看结果

`logs` 显示最近真实发送任务，日志在 `private/runs/`。HTTP200或窗口结束不能证明成功；成功业务响应后还要在官方券包确认。超时代表结果未知，先查券包。售罄、未知拥堵、限流不会循环重发。详细状态含义见 [交接说明](HANDOFF.md)。
