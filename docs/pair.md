# 带上自己养的宠物

网页安装后的示例小窝可直接使用。本页适合想同步自己名下宠物、已有公开版 Cove 灵宠屋 v0.2.0 的用户。本地连接助手目前需要 Python 3.11 或更新版本。电脑与挂件须在同一可信家庭网络，挂件用 2.4 GHz Wi-Fi。

1. 先在电脑启动公开版小屋（默认本机端口 8767），用浏览器领养至少一只已有形象的宝宝。保持小屋运行。
2. 在本仓库点 **Code → Download ZIP**，解压，打开该文件夹里的终端。先在网页上完成示例版安装，然后关闭安装网页或断开串口。
3. 为连接助手建一个独立环境，然后运行配对。macOS 或 Linux 使用下面三行。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python companion.py --pair
```

Windows PowerShell 使用下面三行。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe companion.py --pair
```

助手会询问电脑的局域网 IPv4 地址、要带的宠物和 Wi-Fi。电脑的地址可以在系统的网络设置中查看。用 USB 数据线连接一台挂件，再选择伙伴编号；多只用英文逗号分隔。Wi-Fi 密码输入时不会显示。助手把当前形象和配对信息写到挂件，再启动家庭网络连接服务。上传时保持线缆连接。

保持助手窗口与原灵宠屋运行，即可拔线，从挂件喂一次，再打开网页核对粮仓和照顾记录。电脑防火墙询问时仅对可信家庭网络允许 TCP 8768。挂件和电脑之间使用带配对凭据的局域网 HTTP。不要将这个端口转发到公网。灵宠屋的网页登录凭据只由本机助手使用。

以后在这个目录运行上面第三行，去掉 `--pair` 即可。换 Wi-Fi、换选中名单或同步新阶段图集时再接 USB，用 `--pair`。启用新图集前会检查文件与是否有待确认的照顾。正式小窝的口粮和成长以电脑回执为准。

自定义数据目录可用 `--data`，小屋端口可用 `--core-port`，多个串口时可用 `--device` 指定。Linux 构建中文菜单需要 Noto Sans CJK；也可以用环境变量 `PASSPORT_FONT` 指向本机支持中文的字体。个人数据目录里的 `passport-bridge.json`、整机备份、个人形象和网络配置请勿公开。
