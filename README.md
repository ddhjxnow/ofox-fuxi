# 小米13 (fuxi) OrangeFox 云端编译

目标：在 GitHub Actions 上把 OrangeFox Recovery 编出来，本机只负责推代码、下产物。

- 机型：Xiaomi 13 / `fuxi`（SM8550 kalama，A/B 机型，无独立 recovery 分区，镜像写 `recovery_ab`）
- 分支：`fox_12.1`（当前 OrangeFox R12.0 主线；该 device tree 就是以 12.1 基线做的，作者官方预编译包也是 R11.3/12.1 基线）
- device tree：`lamadaemon/device_xiaomi_fuxi_OFRP` @ `twrp-12.1`（自包含，含 vendor 预编译，**不需要** common tree）

## 一、编译到底在做什么（因果链）

1. `OrangeFox/sync` 里的 `orangefox_sync.sh` 用 TWRP minimal manifest 拉一套 AOSP 精简源码树（约 25–30 GB），
   再 clone/打补丁进 OrangeFox 自己的 `bootable/recovery`（就是 OF 的 UI、脚本、TWRP 核心）。
2. 把机型 device tree 放到 `device/xiaomi/fuxi`，`lunch twrp_fuxi-eng` 让 build 系统把
   `BoardConfig.mk`（分区表、A/B、页大小、kernel 头版本、ramdisk lz4）+ `prebuilt/`（vendor blobs、预编译 kernel）
   合并成一个产品配置。
3. `mka recoveryimage` 编出 `out/target/product/fuxi/recovery.img`（ramdisk 是 lz4 压缩的 cpio，里面是 OF 的 `twres` 主题 + `init.recovery` 等）。
4. 主题分辨率：`gui/pages.cpp` 用主题里 `<resolution width height>` 的声明值算 `scale_w/scale_h`，
   声明的 1080x1920 对上真实 1080x2400 → 横竖缩放不一致 → 界面纵向拉伸。
   所以编译前把声明值改 1080x2400（`scripts/fix_ofox_theme.py`，幂等）。
   （mifs 支持是 HyperOS2 私有 f2fs 变体，用于解密 /data；R11.3 之后上游 `partition.cpp` 已内置，本脚本只做检查。）

## 二、云端编译步骤

前提：一个 GitHub 账号。仓库**公开**时 Actions 标准 runner 不计分钟数；私有仓库每月 2000 分钟免费（一次构建约 60–120 分钟）。

```bash
# 1) 本地已有现成仓库骨架：/nas/mobile/ofox-cloud
cd /nas/mobile/ofox-cloud
git init -b main
git add .
git commit -m "ofox fuxi cloud build"

# 2) 在 GitHub 网页新建空仓库（比如 ofox-fuxi），然后
git remote add origin https://github.com/<你的用户名>/ofox-fuxi.git
git push -u origin main
```

3. 打开 `Actions` → 左侧 `Build OrangeFox for Xiaomi 13 (fuxi)` → `Run workflow`，参数默认即可：
   - `MANIFEST_BRANCH` = `12.1`
   - `DEVICE_TREE_URL` = `https://github.com/lamadaemon/device_xiaomi_fuxi_OFRP`
   - `DEVICE_TREE_BRANCH` = `twrp-12.1`
   - `DEVICE_PATH` = `device/xiaomi/fuxi`
   - `MAKEFILE_NAME` = `twrp_fuxi`，`DEVICE_NAME` = `fuxi`
   - `FOX_VARIANT` = `A15`（A14 ROM 就填 A14）
4. 等 1–2 小时。产物两处都有：本次 run 的 **Artifacts**（`OrangeFox-fuxi-<run_id>`）和 **Releases**（tag `fuxi-<run_number>`）。
5. 刷入：

```bash
fastboot flash recovery_ab OrangeFox-*-fuxi.img
fastboot reboot recovery        # 或 音量上+电源 进 recovery
```

> fuxi 是 A/B + 无 recovery 分区的机型，写 `recovery_ab`（当前活动槽）。HyperOS 官方包会校验 AVB，
> 如果刷完进不去系统/进不去 recovery，需要 `fastboot --disable-verity --disable-verification flash vbmeta_ab`（用原厂 vbmeta）。
> 首次进 OF 解密 /data 可能慢（mifs），卡 logo 超过 5 分钟才算失败。

## 三、目标机是 Android 16 时要注意什么

先说结论：**分支还是 12.1，`FOX_VARIANT` 填 `A16`**。理由分三层：

1. `FOX_VARIANT` 是纯标记：`orangefox.mk` 里只做 `LOCAL_CFLAGS += -DFOX_VARIANT="A16"`，
   最后落到 `ro.orangefox.variant` 属性和版本号/界面显示，**不改变任何功能**。所以填 A16 只是让版本串说实话。
2. 决定 A16 ROM 能不能用的是这三样，跟分支号无关：
   - `/data` 文件系统：HyperOS 3 仍是 `mifs`（小米私有 f2fs 变体）。上游 `partition.cpp` 已把它当 f2fs 处理（`Mount/Wipe/fsck` 都有分支），本仓 12.1 HEAD 已包含。
   - 密钥后端：这棵树 `device.mk` 里 `OF_DEFAULT_KEYMASTER_VERSION := 4.1` + `TW_FORCE_KEYMASTER_VER := true`，
     `recovery/root` 带的是 QTI 的 HIDL keymaster4.1 服务 + `weaver@1.0`。fuxi 的 vendor blob 就是这套，
     12.1 的 `prebuilt/Android.mk` 也只打包 `android.hardware.weaver@1.0.so`（HIDL）。
   - 主题/分辨率：与 Android 版本无关，已由 `scripts/fix_ofox_theme.py` 处理。
3. 社区事实核对：社区（FiimeROM、@RaeBaeXXX）给 fuxi 出的包标注支持 Android 16/15/14，
   基线是 R11.3（就是 `fox_12.1` 那条线，R12.0 是它的后继），且注明"数据解密可用"。所以 12.1 走 A16 是走得通的路线。

什么时候该换 `14.1`：**只有解密失败（进 recovery 后 /data 显示 0MB、要求格式化）时**。
`orangefox_sync.sh` 对 `fox_14.1` 会额外给 `system/vold/` 打 AIDL weaver 补丁（12.1 只有 HIDL weaver@1.0），
如果 HyperOS 3 把密钥后端换成了 keymint AIDL，就需要它。代价：14.1 是实验分支，补丁多、失败点更多，先试 12.1。

`16.0` 分支不适合这个场景：它是**完整的 OrangeFox manifest**（含 AOSP 全套 + device/google/*），
仓库 60 GB 起、CI 时间翻倍，而且这套 `twrp-12.1` 设备树没在 A16 build 系统下验证过。

刷 A16 官方固件的额外注意：HyperOS 官方包有 AVB 校验，`fastboot flash recovery_ab` 后若进不去系统，
用原厂 `vbmeta` 配 `--disable-verity --disable-verification`；刷前先备份（A16 上 /data 一旦被错误格式化就没了）。

## 四、关键文件

| 文件 | 作用 |
|---|---|
| `.github/workflows/ofox-fuxi.yml` | 完整流水线：腾磁盘 → 装依赖/repo → swap/ccache → sync 源码 → 放 device tree → 修主题 → 编译 → 上传 |
| `scripts/fix_ofox_theme.py` | 把主题声明分辨率改成 1080x2400（幂等，跑两次不会重复改） |

流水线里几个不得不做的动作（都是踩过的坑）：

- `rokibhasansagar/slimhub_actions`：GitHub runner 默认只剩 ~14 GB，源码树 30 GB，必须先删掉预装 SDK/工具链。
- `set-swap-space 12G`：16 GB 内存编 AOSP 系容易 OOM。
- `git config --global user.name/email`：`repo init` 需要身份，不配会直接失败。
- ccache 缓存：第二次起编译时间明显缩短（首次冷编 ~90 分钟）。
- **不要设 `FOX_VERSION`**：OrangeFox R12 起该变量已 obsolete，`orangefox.mk` 里是 `$(error ...)`，设了会直接中断编译。
  维护者版本号用 `FOX_MAINTAINER_PATCH_VERSION`，且必须是纯整数（流水线里用 `date +%y%m%d`）。
- 失败时自动把 `out/*.log`、`verbose.log.gz` 传成 artifact，别只盯着 Actions 控制台翻 2 小时日志。

## 五、备用：本地编（这台 NAS）

本机 4 核 / 15 GB 内存，根盘只剩 15 GB，所以要放到 `/nas`（12 TB 空闲）：

```bash
cd /nas/mobile
git clone --depth=1 https://gitlab.com/OrangeFox/sync.git && cd sync
./orangefox_sync.sh --branch 12.1 --path /nas/mobile/fox_12.1     # ~25-30G，几十分钟

cd /nas/mobile/fox_12.1
git clone --depth=1 -b twrp-12.1 https://github.com/lamadaemon/device_xiaomi_fuxi_OFRP device/xiaomi/fuxi
python3 /nas/mobile/ofox-cloud/scripts/fix_ofox_theme.py . 1080 2400

export ALLOW_MISSING_DEPENDENCIES=true FOX_BUILD_DEVICE=fuxi FOX_AB_DEVICE=1 \
       FOX_VARIANT=A16 FOX_DELETE_MAGISK_ADDON=1 FOX_USE_BASH_SHELL=1 LC_ALL=C \
       USE_CCACHE=1 CCACHE_EXEC=/usr/bin/ccache
source build/envsetup.sh
lunch twrp_fuxi-eng
mka adbd recoveryimage -j4
```

注意 device tree 自带的 `setup.sh` 里 `export USE_CCACHE=]1` 是笔误、`CCACHE_DIR=` 是空的，别直接 source 它，
按上面手写 export 更稳。Ubuntu/Debian 系依赖装 `OrangeFox/misc/scripts/setup/android_build_env.sh`；
Arch 上要自己补 `bison flex gperf lib32-ncurses lib32-zlib ncurses zlib libxml2 libpng imagemagick ccache schedtool zip` 等。

## 六、排错对照

| 现象 | 原因 |
|---|---|
| `repo: command not found` | 没跑 `android_build_env.sh`，或它在 `/usr/local/bin` 不在 PATH |
| `No space left on device` | 没做 slimhub 清理，或没删 `out/` |
| `ninja: fatal: posix_spawn: Cannot allocate memory` | 内存不够，加 swap 或 `-j` 降到 2 |
| `lunch: twrp_fuxi-eng not found` | device tree 路径不是 `device/xiaomi/fuxi`，或 `AndroidProducts.mk` 没被扫到 |
| 界面纵向拉伸/按钮错位 | 主题分辨率没改（本流水线已处理） |
| 进不去 recovery、卡 fastboot | A/B 槽写错或 vbmeta 校验，见上面刷入说明 |
| /data 解密失败 | ROM 用 mifs 且内核/OF 不支持（上游 12.1 已内置） |
