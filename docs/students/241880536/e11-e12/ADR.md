# ADR：真实项目接入的泛化策略

编号：ADR-001　　日期：2026-11-14　　作者：241880536（苏州 A 组）

## 问题

E11–E12 的固定样例只有 `main.o/helper.o`、默认目标 `app`、头文件 `config.h`。要用真实仓库（`antirez/sds`：单目标 `sds-test`、头文件 `sds.h`、默认目标不是 `app`）走通 E12 五阶段，现有 `lab.scan()` 与 `pipeline.snapshot()/validate()` 会直接拒绝或只投影两个写死的目标。

## 候选方案

- **A：给真实项目补一层 shim** —— 在 `data/real-project` 里加 `main.c/helper.c/config.h` 并把目标改名为 `app`。改动最小、不动教学代码，但「真实项目」就变成了玩具项目，评审看不出真实语义差异，且 shim 本身要维护。否决。
- **B：泛化扫描与校验** —— 从 Makefile 解析显式编译规则（目标名、源文件、链接目标），扫描按规则枚举目标，`validate()` 接受链接目标/期望输出/头文件名/头文件替换。缺点是要改 `labs/e8e10/lab.py` 与 `labs/e11e12/pipeline.py`，影响 E8–E10 的教学代码（需回归）。**采用**。

## 采用 B 的原因

课程要求「真实项目接入」的目的就是暴露固定样例掩盖的假设：目标名、头文件名、默认构建目标、条件编译头。只有 B 能把这些假设变成可验证的输入字段，并且保留「`gcc -MM` 与 BuildChecker 投影必须一致」这条主断言。

## 输入/输出字段

| 字段 | 作用 | 默认值（固定样例不变） |
|---|---|---|
| `link_target` | 最终链接产物（`make <target>` / `./<target>`） | `app` |
| `build_command` / `clean_command` | 构建与清理命令（透传给 `full_check()`） | `make app` / `make clean` |
| `expected_output` | 程序标准输出（复验判据） | `"1"` |
| `header` / `header_after` / `header_expected` | 头文件整体替换 + 期望输出（测「改头必重编」） | `config.h` / `#define VALUE 2\n` / `"2"` |
| `header_edits` | 大文件定点替换 `[[old,new],…]`（找不到报 `HEADER_EDIT_NOT_FOUND`） | 无 |
| `build_timeout` | 单次构建超时（真实项目 600s） | 120 |

内部结构：`make_rules()` 解析规则表；`compile_pairs()` 只保留「一个 `.c` + recipe 含 `-o`」的显式规则，模式规则仍 `UNSUPPORTED_RULE`；`CFLAGS` 允许空串（编译器默认），其余未建模参数仍 `UNSUPPORTED_FLAGS`。

## 兼容性与验证

- 固定样例行为不变：e8e10 12 项、e11e12 契约 10 项、新增泛化 6 项全绿；`work/e11-a-03`、`work/e11-b-03`、`work/e12-03` 三份样例重跑均 `SUCCEEDED`（与改造前结论一致：新增 `MISSING main.o extra.h`、补丁加 `config.h extra.h`、MD 清零 RD 保留）。
- 真实项目：`work/e12-real-01` 五阶段 `SUCCEEDED`，增量 findings `[MISSING sds-test sdslog.h]`，补丁把 `sdslog.h` 加入 `sds-test` 前置，`validation.accepted=true`，终检 findings `[]`。
- 已知边界：仍要求显式编译规则（`%.o: %.c` 不支持）、单个 `.c` 源（多源编译不建模）、只跟踪 `%file`/`%process` 两类 trace；真实项目中 `-DSDS_TEST_MAIN` 条件包含需要在源码层做成无条件 include 才能让两条依赖图一致——这属于「分析器可见性」的真实约束，已记录在报告故障表。
