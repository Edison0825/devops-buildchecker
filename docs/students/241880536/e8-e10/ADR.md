# 决策记录（ADR）— E8–E10／A 组／241880536

## 背景与约束

- 课程 1.1 里程碑要求 A 组从 BuildChecker 延展到 EChecker（ISSTA 2024）的**增量依赖检查**：用历史依赖图 + 保守失效判据，避免每次全量重扫。
- 材料给的参考实现 `labs/e8e10/lab.py` 已经把机制写死为「`key` 一变 → 两个目标全部刷新」。硬性约束：原 E4–E7 服务文件不得覆盖；每轮输出必须落在 `work/` 下的**新目录**；至少补一项有独立预期的测试；提交必须走 `student/<学号>/e8-e10` 分支 + PR，原有 `e7-a-quality-gate` 必需检查不能被绕过。
- 时间约束：苏州 11/3 三节合并授课（E8+E9+E10 共约 2 小时），实验须在单机 2 vCPU／3.5 GiB 内可重复跑完。

## 选择与替代方案

### 决策 1：不动 `lab.py` 的失效策略，只补测试（采纳）

- 选择：保留「`key = {directives, recipes, flags, compiler}` 任一维变化 → `refreshed = 全部目标`」的保守策略，`save/run/fixture/commit/declarations/scan/patch/validate/buildchecker/demo` 全部按参考实现执行。
- 替代 A：改成「受影响目标 + 传递闭包」的精确失效（论文的进一步优化方向）。**拒绝原因**：这会改变 30 行矩阵的既有语义，需要新的回归对照证明没有漏边；在只有两小时的上机窗口里，改实现 + 重跑全部证据的风险高于收益，而且课程要验证的是「理解机制并能做等价性对照」，不是把教学实现做成研究原型。
- 替代 B：只跑参考用例、不补测试。**拒绝原因**：手册与 `docs/00` 的硬性约定要求「至少一项补充测试且有独立预期」，这是个人门槛（§11）的组成部分。

### 决策 2：新增用例选「间接头文件」这条失效路径（采纳）

- 选择：`test_nested_include_invalidates_whole_graph` —— `main.c` 一个字节不改，只让 `config.h` 去 include 一个新文件 `nested.h`。
- 替代：再写一个「直接给 main.c 加 include」的用例（与参考 `test_include_added_invalidates_cache` 同路径）。**拒绝原因**：重复覆盖同一分支，测不出新东西；而间接头恰恰是保守失效最容易出错的地方——若实现按「源文件的直接 include 列表」判 key，就会漏掉这种变化并长期带着过期依赖。
- 代价：该用例断言的是「两个目标全刷」，等于把当前保守策略**固化**成契约。若将来做决策 1 的替代 A（精确失效），此用例必须同步改成「只刷 main.o」。这一点写进注释与本文档，避免后来者误以为它是优化后的正确行为。

### 决策 3：历史图必须来自真实 BuildChecker，而不是只用 `gcc -MM` 自证（采纳）

- 选择：E8 的 `baseline.actual` 用 `buildchecker.fullcheck.full_check()` 的 `actual-graph.json` 投影到对象目标，并在 `buildchecker()` 内部断言「BuildChecker 投影到 main.o/helper.o 的 findings == gcc -MM 的 findings」，不一致直接抛 `BuildChecker/GCC projection mismatch`。
- 替代：只跑 `gcc -MM` 生成 actual，省掉 strace 与容器内 BuildChecker。**拒绝原因**：那样「历史图」就只是另一个 gcc 调用的输出，无法证明与上一阶段（E5–E7）的 BuildChecker 是同一套判定；而课程主线正是把 E7 的造检查器接到 E8–E10 的增量检查上。
- 代价：每次 baseline 都要跑一次 `strace -ff ... make -p app`（本机 `elapsed_ms=128`），比纯 `gcc -MM` 慢一个量级；但只在 E8 基线与 E10 最终交叉核对各跑一次，可接受。

### 决策 4：性能数字只报 `scan()` 口径，不冒充论文的整体构建倍数（采纳）

- 选择：`performance-summary.csv` 报告 `scan()` 内部（Git 状态与编译器检查、声明解析、`gcc -MM`）的五次中位数，include/flags/header 三类如实记录 0.97–0.99× 这种「没有加速」的结果。
- 替代：把 clean build 与链接也算进分母，制造出更大的加速比。**拒绝原因**：那会把「依赖分析快了」偷换成「构建快了」，与被测对象不符；课程 E10 的判据是「增量与全量的 actual/declared/findings 必须相等」，性能只是附带观察。如实保留 <1 的比值，本身就是对「保守失效有成本」的证据。

## 代价与覆盖范围

- 覆盖：C 语言、两个对象目标（main.o/helper.o）、六类变化（未变、函数体、新增直接 include、补声明、改 CFLAGS、改被引入头文件）；每类 5 次增量 vs 全量共 30 行对照，全部 `equal=True`。
- 不覆盖：链接期依赖、宏配置矩阵（`-DMODE` 只作为白名单里的一个取值，没有做多配置矩阵）、目标粒度剪枝、文件删除场景、并行 make。
- 已知偏差：宿主机 3.5 GiB 内存低于材料建议 4 GiB；未触发失败，故只在报告里记录、不当作结论。
- 成本侧：命中复用 5.6–5.9×；失效场景 0.97–0.99×，即保守策略在「看起来只改了一行」但触到 key 的情况下没有收益，这是设计的代价而非测量误差。

## 验证命令与实际证据

```text
# 1) 镜像（复用 BuildChecker 的 Dockerfile 与锁文件，不覆盖原服务文件）
python3 run_lab.py build
# → course-e8e10:241880536  sha256:83b5eefdcd5a9301c02ff2ca698ef67a2b55a8c6a15577a7c2d79e2503b066b2

# 2) 三个实验（每个都新开 work/ 下的 OUT）
source 03_实验包/classroom_helpers.sh && lab_ready
lab_new_run e8 A   # → work/e8-A-manual.ZAWGNG
lab_new_run e9 A   # → work/e9-A-manual.lPlfuh
lab_new_run e10 A  # → work/e10-A-manual.MmzLVF

# 3) 定向回归（原包 7 项 + 本人 1 项）
docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/course" -w /course course-e8e10:241880536 \
  python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v
```

实际证据（全部在服务器 `~/devops-students/241880536/buildchecker` 下）：

- `work/e8-A-manual.ZAWGNG/steps/*.log`：`BASELINE_PASS`、`BUILDCHECKER_BASELINE_PASS {'main.o': ['config.h','main.c'], 'helper.o': ['helper.c']}`、`REUSE_PASS ['main.o','helper.o'] []`，每步 `STEP_EXIT_CODE=0`
- `work/e8-A-manual.ZAWGNG/buildchecker/make-db.txt:1044` = `main.o: main.c unused.h`；`buildchecker/trace/t.14:579` = `openat(AT_FDCWD, "config.h", O_RDONLY|O_NOCTTY) = 4`
- `work/e9-A-manual.lPlfuh/`：C0 `bc73c17` → C1 `149b359` → C2 `d184c06` → C3 `9084561`，`C2_REFRESH_PASS` 含 `added=[['MISSING','main.o','extra.h']]`，`C3_RESOLVED_PASS` 两条 MD 消除
- `work/e10-A-manual.MmzLVF/matrix/gate.json` = `{"track":"A","passed":true,"rows":30}`；`results.csv` 31 行；`final-buildchecker` 为 `status=SUCCEEDED`、`trace_id=e6-c0632d08b80e4038bc2ed723fe61509c`、`elapsed_ms=127`、`make-db.txt:1052` 已含 config.h 与 extra.h
- 测试：`Ran 8 tests … OK`（日志 `work/unit-tests-*.log`）
