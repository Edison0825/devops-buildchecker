# AI 使用记录 — E8–E10／A 组／241880536

## 工具/模型/日期

- 工具：DeepSeek Harness（命令行／Web 会话式编程助手，可执行 PowerShell 与 SSH 命令）
- 模型：deepseek 系列对话模型（会话内标识 deepseek-flash）
- 日期：2026-11-08（E8/E9/E10 实机执行与文档起草均在同一天完成）
- 范围：把 `02_操作手册` 的三份 A 组手册转成可执行步骤、在云主机上实跑并留存 OUT、汇总实测数字、起草本目录三份文档。**没有让模型代为决定课程要求层面的取舍**，那些由本人拍板（见「采纳/拒绝」）。

## 输入上下文与问题

提供给模型的是课程原始材料，不含任何密钥：

1. `E8-E10/DevOps_E8_E10/README.md`、`02_操作手册/{00_公共准备,8_E8_A组,9_E9_A组,10_E10_A组,07_提交与排错,08_个人测试编写示例}.md`
2. `03_实验包/{run_lab.py,classroom_helpers.sh,labs/e8e10/{lab.py,test_profile.py}}`
3. `04_模板/{个人报告,ADR,AI_USAGE}.md`
4. 云主机只读查询结果（`docker images`、`git log`、仓库目录清单）

具体问题：

- 手册的 9／12／15 步如何在不改动参考实现的前提下逐条跑通，并把每一步的判据字符串（如 `BASELINE_PASS`、`REUSE_PASS`）原样落到日志里？
- 三个实验的历史图分别从哪里来、哪些变化会让缓存失效？
- 怎样写一个「有独立预期」的新测试，而不是把实现抄一遍？
- 30 行矩阵与五次计时的数字怎么汇总、比值小于 1 的情况怎么解释？

## 模型建议

- 建议把长命令写成 `scripts/e8a.sh`、`e9a.sh`、`e10a.sh` 这类脚本，`scp` 上传后在容器里分步执行，每步落 `steps/<时间戳>-<序号>.log` 与 `STEP_EXIT_CODE`，便于事后回溯。
- 建议新测试选**间接头文件**场景（`main.c` 不变，`config.h` 去 include `nested.h`），理由是参考用例只覆盖「直接改 main.c 的 include」，间接头是保守失效最容易漏的分支。
- 建议 E8 基线必须用真实 `buildchecker.fullcheck.full_check()` 产出 `actual-graph.json` 再投影到对象目标，并保留「BuildChecker 投影 == gcc -MM」的断言。
- 建议性能只报 `scan()` 口径、保留 0.97–0.99× 的负加速，不把 clean build 算进分母。
- 建议提交走 `student/241880536/e8-e10` 分支、报告放 `docs/students/241880536/e8-e10/`、PR 用 `--body-file 个人报告.md`，与 `07_提交与排错.md` 一致。

## 采纳/拒绝及理由

|建议|处置|理由|
|---|---|---|
|分步脚本 + 每步日志|采纳|事后能逐个 `STEP_EXIT_CODE` 回溯，比一次性长命令更可审计；也避免 PowerShell 把远程 `2>` 当重定向等坑|
|间接头文件测试|采纳|与参考用例不重复，且能暴露「按直接 include 列表判 key」的错误实现|
|真实 BuildChecker 做历史图|采纳|课程主线是把 E7 的检查器接到增量检查上，只用 gcc 自证会断掉这条线|
|只报 `scan()` 计时|采纳|避免把「依赖分析快」偷换成「构建快」|
|把 `lab.py` 改成精确失效（受影响目标 + 传递闭包）|**拒绝**|会改变 30 行矩阵语义、需要额外回归证明没漏边；两小时窗口内风险大于收益。已在 ADR 记为扩展计划|
|把 include/flags/header 的计时剔除或改写|**拒绝**|剔除负加速等于选择性报告；保留 <1 的比值本身就是「保守失效有成本」的证据|

## 人工修改

- 由本人决定「不改 `lab.py` 实现、只补测试」，并在 ADR 中固化该取舍及其代价。
- 由本人核对模型汇总的数字与原始文件是否一致（`gate.json` rows=30、`results.csv` 31 行、`make-db.txt:1052` 内容、`trace_id`），确认后才写进报告。
- 由本人执行账号与凭证相关操作（GitHub 登录、临时 PAT 的使用与回收、`gh api user --jq .login` 校验身份），这些不交给模型自动完成。
- 由本人决定最终 PR 的提交信息与合并方式（合并由组长按 E7 既有门禁流程执行）。

## 实际验证命令/输入/结果

```text
python3 run_lab.py build
→ course-e8e10:241880536 / sha256:83b5eefdcd5a9301c02ff2ca698ef67a2b55a8c6a15577a7c2d79e2503b066b2

source 03_实验包/classroom_helpers.sh && lab_ready && lab_new_run e8 A
→ work/e8-A-manual.ZAWGNG，steps 3/4/6 分别 BASELINE_PASS、BUILDCHECKER_BASELINE_PASS、REUSE_PASS，STEP_EXIT_CODE=0

lab_new_run e9 A → work/e9-A-manual.lPlfuh
→ C1_REUSE_PASS、C2_REFRESH_PASS（added MISSING main.o→extra.h）、C3_RESOLVED_PASS（resolved 2）

lab_new_run e10 A → work/e10-A-manual.MmzLVF
→ gate.json {"track":"A","passed":true,"rows":30}；results.csv 31 行；MATRIX_PASS 六类各 5 次

docker run --rm --network none --user "$(id -u):$(id -g)" -e HOME=/tmp \
  -v "$PWD:/course" -w /course course-e8e10:241880536 \
  python3 -m unittest discover -s labs/e8e10 -p test_profile.py -v
→ Ran 8 tests, OK（原包 7 项 + 本人 1 项）
```

模型生成的每一段数字都对应上面某个文件的实测输出；没有使用模型凭记忆给出的数值。若某步失败，日志与 `STEP_EXIT_CODE` 会原样保留，不删除失败记录。
