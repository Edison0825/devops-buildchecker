# 缺陷 Issue 与修复 PR

本文件记录 E13 交叉测试中发现的两个缺陷。两个 Issue 与修复 PR 同一个提交批次，`Closes #24`、`Closes #25`。

## 缺陷 D1：e11-b 直接接受被改动的修复报告

### Issue

- 用例编号与发现方：C3（跨组修复报告哈希变化）/ A 组 241880536（姚晟易）
- 输入仓库及完整 SHA：`data/real-project`（antirez/sds 课程适配 fork），base `f103947b89737ef40c5920a44cfc1df7911b6dfe`，target `3d658f2049015bba04df8d425d378fd196b15702`
- 预期 / 实际：预期消费前校验字节哈希，不符即拒；实际 main 上 `labs/e11e12/pipeline.py:135` 只按路径读取报告，只比较 `schema_version/kind/commit`，报告被改一个换行仍 `SUCCEEDED`
- 失败阶段、错误码和原始日志路径：e11-b 入口；修复前 `job-5baa01e21af34042bc70c6a38fd3a757` `SUCCEEDED`（`work/e13-c3-before/result.json`）；修复后 `job-a9e32c7aecfa41bba80625be2f2aea08` `FAILED` `ARTIFACT_HASH_MISMATCH`（`work/e13-c3-after/result.json`）
- 严重度（阻断 / 非阻断）与理由：阻断——被改动的报告可直接进入修复流程，污染候选依赖结论
- 最小复现步骤：复制 `data/e13-live-report-from-A/fixed-md.json` 加一个换行，作为 `fixed_report` 提交 e11-b 请求（`fixed_report_sha256` 仍填 `61d64dca…`）
- 是否影响其他任务或原仓库：不影响；仅 e11-b 交接入口

Issue 链接：https://github.com/Edison0825/devops-buildchecker/issues/24

### PR

- 关联 Issue：#24
- 修改文件与原因：`labs/e11e12/pipeline.py` 读报告前插入 `expected_sha256 = request.get('fixed_report_sha256')` 与 sha256 比对，不符抛 `Failure('ARTIFACT_HASH_MISMATCH', 'Fixed report changed during transfer')`；`labs/e13e14/shape.py` 把同一校验抽成 `verify_report_hash()` 供服务复用；`labs/e13e14/service.py` 的 mdfixer 改用它
- 失败前证据 / 修复后同一测试证据：`work/e13-c3-before/result.json`（SUCCEEDED）→ `work/e13-c3-after/result.json`（FAILED, ARTIFACT_HASH_MISMATCH）
- 新增或修改的回归测试：`labs/e13e14/test_shape.py::ReportTransferTests`（2 项：正常哈希返回、传输变更被拒）
- 原始仓库修复前后 SHA 核对：`data/e13-c3/fixed-md.json` sha `7cd52591…`，请求里的期望 sha `61d64dca…`；被测项目 `data/real-project` 的 base/target 提交未变
- CI 门禁链接与审查人：见 PR 检查列表（`e13e14-gate` 等四条）
- 剩余风险：若调用方不传 `fixed_report_sha256`，仍只做 commit 校验（保持对旧请求的兼容）

## 缺陷 D2：E14 echecker 把链接目标当对象目标

### Issue

- 用例编号与发现方：E14 固定样例四容器 E2E / A 组 241880536
- 输入仓库及完整 SHA：`data/integration-sample/repo`，base `6dce28e1ca66d5a1a115734925e13a5f88b917c1`，target `7065b1836424b9005d00df15d3cc25a895042519`
- 预期 / 实际：预期五阶段 `SUCCEEDED`；实际 echecker 把 baseline graph 的链接目标 `app` 也投影为对象目标，与 `gcc -MM` 的对象图比较必然不等 → `Baseline BuildChecker/GCC graph mismatch`（HTTP 422 `VALUEERROR`）
- 失败阶段、错误码和原始日志路径：`incremental-check`；`job-4cc3895ea86f40779242933cf5b1d6ec` `FAILED`（`work/e14-fixed-01/result.json`、`work/e14-fixed-01/incremental-response.json`）
- 严重度：阻断——固定样例跑不通，候选发布无法成立
- 最小复现步骤：compose 起四容器后跑 `work/e14-requests/fixed.json`
- 是否影响其他任务或原仓库：不影响；E11-A/E11-B 用 `pipeline.py` 的投影，sds 图里只有对象目标，故未暴露

Issue 链接：https://github.com/Edison0825/devops-buildchecker/issues/25

### PR

- 关联 Issue：#25
- 修改文件与原因：`labs/e13e14/service.py` 的 echecker 分支改用 `shape.object_targets()`，只保留「GCC 扫描结果 ∩ BuildChecker 图」里的对象目标；`orchestrate.py` 的 profile 检查改用 `compile_pairs()` 并把项目形状参数透传给四个服务，使服务能跑非 `main.o/helper.o` 形状的真实项目
- 失败前证据 / 修复后同一测试证据：`work/e14-fixed-01`（FAILED, graph mismatch）→ `work/e14-fixed-02`（`job-62b4a60e…`）、`work/e14-fixed-03`（`job-2c1a81c2…`）五阶段 SUCCEEDED；真实项目 `work/e14-real-03`（`job-9a8a9b48…`）同样 SUCCEEDED
- 新增或修改的回归测试：`labs/e13e14/test_shape.py::ProjectionTests`（3 项：链接目标被剔除、单对象真实项目形状、无交集时报错）
- 原始仓库修复前后 SHA 核对：固定样例 base/target 提交未变；`data/integration-sample/repo` 的 `make-db.txt` 声明与 target 提交一致
- CI 门禁链接与审查人：见 PR 检查列表（`e13e14-gate` 等四条）
- 剩余风险：若某个项目的链接目标与对象目标同名（极少见），`object_targets` 会把它当对象目标；此时以 `compile_pairs` 的结果为准，属既有约定

### 附带修复（CI 首次运行暴露）

PR #26 首轮 CI 的 `four-services` 作业失败：`COMMAND_FAILED ['git','rev-parse','HEAD'] fatal: detected dubious ownership in repository at '/course/work/ci-e14/base-project'`。原因是四容器以 root 运行、`/course` 由 runner（uid 1001）持有，git 拒绝跨用户仓库。修复：在 `labs/e13e14/compose.yaml` 的公共环境里加 `GIT_CONFIG_COUNT=1`、`GIT_CONFIG_KEY_0=safe.directory`、`GIT_CONFIG_VALUE_0=*`（四个服务都继承），并把 `PYTHONPATH` 补上 `/course/labs/e13e14`。修复后 `four-services` 通过（run 45157647200 / 45157660099）。该问题只出现在 CI 的跨用户挂载场景，本机 `--user $(id -u):$(id -g)` 不触发。
