# BKT + DAG 评测重构说明

## 架构数据流

1. Master Agent 仍按原顺序调度：State Analyzer -> KC Planner -> Question Selector -> Time Analyzer。
2. State Analyzer 在得到 correctness 和耗时后，不再直接做启发式加减分，而是调用 Bayesian 更新模块。
3. Bayesian 模块对每个 KC 的 Beta 后验参数 (alpha, beta) 做增量更新，并回写 mastery/confidence。
4. 若高阶 KC 在本轮达到高掌握高置信阈值，DAG 反向传播会沿前置边给依赖 KC 增加 alpha，减少冗余基础题。
5. 更新后的状态继续进入下轮规划，形成闭环。

## 数学定义

- 掌握概率（后验均值）：
  - `E[X] = alpha / (alpha + beta)`
- 不确定性（后验方差）：
  - `Var[X] = alpha * beta / ((alpha + beta)^2 * (alpha + beta + 1))`
- 置信度映射：
  - `confidence = 1 - min(Var[X] / 0.25, 1)`

时间惩罚因子：

- `r = T_actual / T_expected`
- 当 `r <= 1` 时，`gamma = 1`
- 当 `r > 1` 时，`gamma = exp(-k * (r - 1))`，并裁剪到 `[0.2, 1]`

证据更新：

- `alpha += gamma * correctness`
- `beta += (1 - correctness) * (1 + 0.5 * (1 - gamma))`

这保证了“答对但很慢”只注入 gamma 权重，而不是完整 1 单位正证据。

## DAG 反向传播

触发条件：

- source KC 的 mastery >= 0.78
- source KC 的 confidence >= 0.68

传播公式（到前置 prereq 节点）：

- `delta_alpha = clip(base_boost * edge_weight * mastery_source * confidence_source, 0, 0.6)`
- `prereq.alpha += delta_alpha`

## 集成建议

1. 继续保持 API 层与 pipeline 层接口不变，仅替换内部状态更新函数，避免前端/调用方破坏。
2. 首次上线建议灰度：对 10%-20% 会话开启 BKT 路径，监控平均轮次、完成时长、调用 token。
3. 在日志中记录 gamma、alpha/beta 增量、DAG 传播记录，便于评估“快答正确”和“慢答正确”的区分效果。
4. 对不同题型可分配不同 k（时间惩罚斜率），后续可基于离线数据做贝叶斯优化。
