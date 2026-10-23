# E5 复现说明：BuildChecker 手工采集 MD/RD

## 1. 目标与范围

按 TSE《Detecting Build Dependency Errors by Dynamic Analysis of Build Execution against Declaration》的思路：在一次 clean build 中采集“实际读取的文件”与“Makefile 声明的依赖”，比较两个集合得到缺失依赖（MD，读了没声明）与冗余依赖（RD，声明了没读）。

本阶段是**手工采集**，不使用检测器代码，目的是先证明证据链本身成立。

## 2. 运行环境

| 项 | 值 |
|---|---|
| 主机 | Ubuntu 22.04.5 LTS，kernel 5.15.0-191-generic，x86_64 |
| 规格 | 2 vCPU / MemTotal 3.5 GiB / 可用磁盘 68.6 GiB（低于 doctor 建议的 4 vCPU、8 GiB、100 GiB） |
| Docker | 29.1.3（Client 与 Server 同版本），compose 2.40.3，buildx 0.30.1 |
| 服务镜像 | `course1020-buildchecker:241880536`，构建时镜像 ID `sha256:45ac2ec35593ee2181968ecce1611d86a6a00ff929ccd91a602d491f1d41cf1b` |
| 基础镜像 | `python:3.13-slim@sha256:f82c96458eedc847b233e582eb31336f4954b39cae020b6dcf5b3ed0e5cbcd74` |
| 镜像内工具 | gcc、make、strace、git；Python 3.13.14（版本记录于镜像内 `/opt/toolchain.lock`） |

镜像内 Python 3.13.14 与宿主 Python 3.10.12 不同，属预期：依赖按 `requirements-dev.lock` 以 Python 3.13 / linux 平台固定。

## 3. 命令

统一入口：

```bash
python3 scripts/lab_cloud.py e5 --out work/e5-01 --image course1020-buildchecker:241880536
```

该入口在容器内执行（即本阶段的实际采集过程）：

```bash
cp -R /app/fixtures/md-rd/. /evidence/ && cd /evidence
mkdir trace && make clean
strace -ff -s 4096 -o trace/t -e trace=%file,%process make -p app > make-db.txt 2> build-stderr.log
./app > program-output.txt
```

要点：`-ff` 每进程一个 `t.<pid>`；`-s 4096` 避免路径截断；`-e trace=%file,%process` 只采集文件操作与进程创建；`make -p` 在构建同时把 Make 内部数据库打印到 stdout，重定向进 `make-db.txt`。

## 4. 结果

| 检查项 | 预期 | 实际 | 证据 |
|---|---|---|---|
| 构建与运行 | 成功 | 退出码 0 | `evidence/build-stderr.log` |
| 程序输出 | `1` | `1` | `evidence/program-output.txt` |
| Makefile 声明 | `main.o: main.c unused.h` | 同 | `evidence/make-db.txt:1061` |
| 实际读取 | 成功打开 `config.h` | `openat(AT_FDCWD, "config.h", O_RDONLY\|O_NOCTTY) = 4` | `evidence/trace/t.16:580` |

## 5. MD/RD 推导

- **MD = `main.o → config.h`**：声明中没有 `config.h`，但 `cc1`（`t.16`）在第 580 行以 `O_RDONLY` 成功打开它（返回值 `4 ≥ 0`）。返回值是关键：若为 `-1 ENOENT` 则只是“尝试过”，不构成依赖。
- **RD = `main.o → unused.h`**：Make 数据库声明了 `unused.h`，但全部 7 个进程的 trace 中 `unused.h` 零次出现，即本次构建配置下从未被读取。

## 6. 进程归属

本次 trace 共 7 个进程（`t.14`–`t.20`，行数分别 72/115/582/26/135/104/156）。根进程为 `make`，其直接子进程构成一个 recipe job，该 job 的全部后代（`cc` → `cc1`、`as`）归属同一 job；job 写出的唯一最终输出即目标（这里是 `main.o`）。`main.o` 的依赖 = 该 job 中读到的、且非本 job 产出的项目内路径。

## 7. 与论文原型的差异

| 论文 | 本次 |
|---|---|
| ptrace 拦截 GNU Make 及其子进程 | `strace -ff -e trace=%file,%process` 事后解析 |
| 完整依赖图与增量能力 | 仅单次 clean build 的实际图/声明图 |
| 真实项目基准 | 单个 4 文件教学样例 |

`strace` 只能观测系统调用，无法证明字节级读取；本阶段把“成功 read-open”作为读取证据，这是明确的教学档位近似。

## 8. 验证边界

仅验证：MD/RD 的精确集合、证据可回溯到具体 trace 行、程序输出正确。

不验证：多 Make 进程（递归 Make）、单 job 多输出、符号链接、`fchdir`、数字 fd 的相对路径 —— 这些情况检测器会显式返回 `UNSUPPORTED` 而不是猜。
