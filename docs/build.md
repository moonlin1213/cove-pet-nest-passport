# 从源码验证与构建

普通使用者只需要打开项目首页的网页安装入口。以下是维护者流程。

- 使用 Python 3.11+ 安装 `tools/requirements-build.txt`，用 `python -m unittest discover -v` 运行设备和桥接测试。需要支持简体中文的本机字体，可用 `PASSPORT_FONT` 指定。
- 从 [FoloToy 官方 v0.1.1](https://github.com/FoloToy/ai-passport-micropython/releases/tag/v0.1.1) 下载 `build-FOLOTOY_AI_PASSPORT-merged.bin`。生成器先校验整份原厂底座 SHA-256，再核对公开素材清单。
- 运行 `python tools/build_starter.py /path/to/build-FOLOTOY_AI_PASSPORT-merged.bin`。程序在新临时目录中从源码和仓库内的通用素材构建，重新挂载并检查每个文件，再生成 8 MiB 的安装镜像。底座从 0 字节开始，用户文件系统从 0x300000 开始。不要使用任何真机整盘转储制作发布包。
- 使用 Node.js 20+ 运行 `npm ci`、`npm test`、`npm run build`。安装网页与串口依赖均为静态文件，自托管时使用 HTTPS（本机测试可用 localhost）。GitHub Pages 发布 main 分支的 docs 目录，入口为 install/。
- 提交前核对 `git ls-files`。只应包含公开源码、文档、测试、通用素材和上述生成文件。发布后的 `install/image.json` 提供整机镜像 SHA-256。
