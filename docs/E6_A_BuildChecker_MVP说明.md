# E6 BuildChecker MVP 说明

## 1. 实现

`buildchecker/fullcheck.py` 的 `full_check()` 把 E5 的手工流程固化为程序，六个步骤：

1. 复制 fixture 到独立目录，记录逐文件 `input_sha256`；
2. 执行 clean 命令，失败则拒绝声明“clean build”；
3. `strace -ff -s 4096 -e trace=%file,%process make -p app`，同时得到 trace 与 Make 数据库；
4. 解析 trace 建实际依赖图（进程归属 + 路径过滤）；
5. 解析 `make -p` 的 `# Files` 段建声明图（剔除 pattern rule、展开 `.PHONY`、order-only 单列）；
6. 求差集：`actual − declared = MISSING`，`declared − actual = REDUNDANT`，每条错误带 evidence。

## 2. 缺陷样例（before）

```bash
python3 scripts/lab_cloud.py e6 --out work/e6-before --image course1020-buildchecker:241880536
```

| 项 | 值 |
|---|---|
| 状态 | `SUCCEEDED`，`clean_exit_code=0`，`build_exit_code=0` |
| `trace_id` | `e6-3c646860bc0e4d059ea0168d8d4c581e` |
| findings | 2 条：`MISSING main.o/config.h`、`REDUNDANT main.o/unused.h` |
| CLI 退出码 | `1`（`--fail-on-findings` 生效） |
| 检测耗时 | `elapsed_ms = 126` |
| 观测目标 | `app`、`main.o`（不只检查 main.o） |

证据可回溯：MD 的 evidence 第一条指向 `t.14:579`（读 `config.h`），第二条指向 `t.15:23`（写 `main.o`）；RD 的 evidence 指向 `make-db.txt:1053` 的声明原文 `main.o: main.c unused.h`，并标注 `scope = Not observed in this recipe job under this build configuration`。

> 注：E5 的声明行号为 1061，E6 为 1053。两次构建根目录不同（`/evidence` 与 `/evidence/project`），`make -p` 输出的路径长度与条目顺序随之微移，引用时不可混用。

## 3. 修复复检（after）

```bash
python3 scripts/lab_cloud.py e6 --fixed --out work/e6-after --image course1020-buildchecker:241880536
python3 scripts/verify_e6_evidence.py \
  --before work/e6-before/evidence/findings.json \
  --after  work/e6-after/evidence/findings.json
```

`--fixed` 只修改**独立副本**中的 Makefile（`main.o: main.c unused.h` → `main.o: main.c config.h`），原始 `fixtures/md-rd/Makefile` 不变。

| 项 | 值 |
|---|---|
| `trace_id` | `e6-31a29967dcea422d860f6dee412e3985` |
| findings | `[]`，CLI 退出码 `0` |

## 4. 输入哈希（证明只改声明、不动源码）

| 文件 | before | after |
|---|---|---|
| `Makefile` | `fd1dcd76…772f` | `128069c9…00ae` |
| `config.h` | `ac32a92f…9696` | `ac32a92f…9696` |
| `main.c` | `bfa1c2d1…a197` | `bfa1c2d1…a197` |
| `unused.h` | `1e431554…66c9` | `1e431554…66c9` |

`verify_e6_evidence.py` 结论：`passed=true`、`before_findings=2`、`after_findings=0`、`changed_inputs=["Makefile"]`。即错误是通过修正**声明**消除的，源码未改动。

## 5. E7 门禁结果

| case | 退出码 | 判定 | 说明 |
|---|---|---|---|
| `unit-tests` | 0 | PASS | 容器内 pytest |
| `original-1/2/3` | 1 | PASS | 三次得到完全相同的 2 条 findings |
| `fixed` | 0 | PASS | findings 为空 |
| `build-failed` | 1 | PASS | `FAILED` + `CHECK_FAILED` |
| `unsupported` | 1 | PASS | 单规则多输出 → `UNSUPPORTED` |
| `timeout` | 1 | PASS | `TIMED_OUT` |

八项全 `passed=true`。注意：故障场景的工具退出码为 `1` 且门禁判定为 PASS —— 评的是“程序是否正确报告了问题”，不是“程序是否成功”。

## 6. 测试

| 阶段 | 服务测试数 |
|---|---|
| 基线（学生包） | 15 |
| 加入自主扩展测试（路径归一化边界 3 项） | 18 |
| 独立判定器自测（`tests/e7`） | 6 |

## 7. 验证边界

教学档位：单 Make 进程、每个 recipe job 单输出、仅 C/汇编小样例、不支持符号链接与 `fchdir`。以上限制在实现中都是**显式拒绝**（`Unsupported`），不会静默产生错误结论。
