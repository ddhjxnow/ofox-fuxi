# 小米13（fuxi）OrangeFox 云端编译

这是用于 GitHub Actions 的测试构建配置，不是已经通过真机验证的 Android 16 recovery。

## 目标与验证边界

- 设备：Xiaomi 13，代号 `fuxi`。
- 目标系统：用户提供的 HyperOS `3.0.310.0` / Android 16；地区后缀以手机实际显示为准。
- 源码基线：`fox_12.1`。
- 设备树：[`lamadaemon/device_xiaomi_fuxi_OFRP`](https://github.com/lamadaemon/device_xiaomi_fuxi_OFRP)，分支 `twrp-12.1`，放置于 `device/xiaomi/fuxi`。
- 该树作者只注明在 xiaomi.eu HyperOS 2 上测试，并说明 A15/mifs 支持；不能据此保证 HyperOS 3.0.310.0 能启动或解密。
- `FOX_VARIANT=A16` 是版本标签，不会自动增加 Android 16 解密支持。

源码是否编译成功、镜像是否启动、当前固件是否能解密 `/data`，需要分别验证。当前仓库的回归测试验证脚本路径、XML 幂等性、保留变量配置和构建步骤的退出控制，不执行 Android 编译。

## 云端使用

工作流入口：

https://github.com/ddhjxnow/ofox-fuxi/actions/workflows/ofox-fuxi.yml

1. 如仓库是 fork，先在 Actions 页面按 GitHub 提示启用工作流。
2. 点击 `Run workflow`，选择 `main`。
3. 默认参数如下：

| 参数 | 默认值 |
|---|---|
| `MANIFEST_BRANCH` | `12.1` |
| `DEVICE_TREE_URL` | `https://github.com/lamadaemon/device_xiaomi_fuxi_OFRP` |
| `DEVICE_TREE_BRANCH` | `twrp-12.1` |
| `DEVICE_PATH` | `device/xiaomi/fuxi` |
| `DEVICE_NAME` | `fuxi` |
| `MAKEFILE_NAME` | `twrp_fuxi` |
| `BUILD_TARGET` | `recovery` |
| `FOX_VARIANT` | `A16` |
| `OF_MAINTAINER` | `ddhjxnow` |

4. 查看每个步骤的实际日志。完整构建成功后，工作流会尝试将镜像上传到本次运行的 Artifacts 和仓库 Releases。
5. 修改 workflow 后创建一次新的 `Run workflow`；重跑旧任务可能仍使用旧提交。

这个 workflow 使用托管 Ubuntu runner，包含清理磁盘、安装依赖、swap 和 ccache。资源用量与构建时间以实际日志为准；不要把静态检查通过当作构建成功。

## 这次修正的路径问题

Android 源码根目录和 recovery 仓库根目录是不同目录：

```text
fox_12.1/                          # source envsetup、lunch、mka 在这里执行
  bootable/recovery/               # 修主题脚本接受这里
    gui/theme/portrait_hdpi/
    partition.cpp
```

正确调用：

```bash
SRC="$GITHUB_WORKSPACE/fox_12.1"
FIX="$GITHUB_WORKSPACE/ci/fix_ofox_theme.py"
python3 "$FIX" "$SRC/bootable/recovery" 1080 2400
```

如果只传 `$SRC`，脚本会查找不存在的 `$SRC/gui/theme/...` 并失败。

依赖仓库 `OrangeFox/misc/scripts` 克隆到 `$RUNNER_TEMP/ofscripts`，不要为了避免目录冲突而删除 builder 自己的 `ci/`。

主题脚本保留旧设备树中的分辨率修改思路；XML 改动不代表真机布局已经验证，也不证明所有屏幕都需要同样修改。

## 构建变量和失败处理

不要在 workflow、job 或 step 的 `env` 中设置 `TARGET_DEVICE_DIR`。它由 Android 构建系统根据产品配置推导；手动导出会触发 `board_config.mk` 的 `TARGET_DEVICE_DIR may not be set manually` 错误。

这个错误可能导致后续 `dumpvars`、`lunch` 和产品规格查找失败。应先消除最早的致命错误，不要直接将连锁报错当作设备树不存在。

构建步骤会检查 `source build/envsetup.sh`、`lunch` 和 `mka` 的返回码。初始化失败时立即退出，不再执行后续编译；每次使用全新源码目录，不运行 `make clean`。

但 OrangeFox 的 12.1 同步补丁在 `orangefox_envsetup()` 末尾使用了 `[ -s 可选文件 ] && 清空文件`：文件不存在或已经为空时，这条检查返回 1，即使 `lunch`、`mka` 已加载也会让整个 source 返回 1。`ci/fix_envsetup_return.py` 在 source 前只把这条已知检查改为等价 `if`，使“不需要处理”返回 0，保留真实写入错误和其他初始化失败。它支持 `build/envsetup.sh` 符号链接，重复运行不重复修改；没有该旧语句时不改动文件。

该问题已通过真实 TeamWin envsetup、vendor envsetup 和 OrangeFox 官方补丁在最小目录布局上复现并验证修正；这不等于完整 Android 源码构建通过。

## 本地回归检查

```bash
cd /nas/mobile/ofox-cloud
uv run --with pyyaml python -m unittest discover -s ci -p 'test_*.py' -v
```

测试使用明确标注的最小 XML fixture 和模拟 Android 目录布局，执行 workflow 中真正的主题步骤，检查传参、输出 XML 和再次运行幂等。构建控制流测试通过显式的 shell 函数替身验证初始化失败即停止、构建退出码保留，并检查各级 env 不导出保留变量。它不下载完整源码、不执行 Android 编译、不刷机。

有 actionlint 时再执行：

```bash
actionlint .github/workflows/ofox-fuxi.yml
```

## 安全与兼容性

- 不要把 `mifs` 文件系统识别与 FBE / metadata encryption 解密混为一谈。
- 解密失败时先保存 `/tmp/recovery.log`，核对当前固件的 fstab、内核、vendor blobs 和密钥服务；不要直接格式化 `/data`。
- 不要因为 `/data` 显示 0MB 就断定必须换 14.1 或 16.0。
- A/B 不代表没有独立 recovery 分区。刷入位置需核对 fuxi 实际分区表、镜像格式和设备树说明。
- 刷写前确认 bootloader 已解锁、备份重要数据及原恢复镜像。不要将关闭 AVB 或刷其他固件的 vbmeta 当作通用修复。
- 当前源码如果拒绝 `FOX_VERSION`，不要设置它；维护者版本变量 `FOX_MAINTAINER_PATCH_VERSION` 按上游规则使用整数。

真正基于 `fox_16.0` 构建需要独立 checkout，并移植/验证设备树；不能只改分支输入。参考官方说明：

- https://wiki.orangefox.tech/en/dev/building
- https://gitlab.com/OrangeFox/sync/-/blob/master/README.md
