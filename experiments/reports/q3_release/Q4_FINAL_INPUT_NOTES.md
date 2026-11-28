# Q4最终输入说明

本版本为`final_original_flags_278`，以原始HVA标记为响应定义；旧Latency排除版仅作敏感性。入口是q4_final_input_manifest.csv，每项给源文件和SHA-256。所有历史文件保留，不依靠旧文件名猜新事件。

## 必须保留的语义

- 原V标记在Data02中恰等于`N_after>N_before`，不是任意发声。计数q定义`N_after>0`，不得与原V门槛混用。000指原始标记均为0，不意味着无发声、无行为或未感知。
- Vocal的`cdf_ts`表示`P(最终满足原始发声增加标记，且记录发声时间≤t)`，不是发声次数首次超过基线的时间分布。最终增量由整个60秒窗口决定，不能把记录首声时间叫作增量发生时刻。
- 概率来自同一原联合八状态，H/V/A边际与Latency窗口概率一致，CDF(60)与对应边际一致。条件时间只含type，不能称调整全部条件后的速度因果效应。
- conditional_time_information_required和positive_time_evidence区分窗口门槛与时间信息。Control Approach的9个场景没有正时间观测：条件时间及中间时间CDF仅借用模型，标为敏感性；其原标记窗口概率由278行联合模型给出，不能将时间无证据误称整个概率模型不存在。

## 跨模块一致性诊断：未校准

数据事件要求p_V≤q，基线为0时p_V=q。两个独立拟合模块未强制满足这些关系。36场景基线均0，10个p_V>q（最大6.93个百分点），36个预测不精确相等，平均绝对差1.75个百分点。实际观测条件114/278个超过，最大10.21个百分点；已有OOF为121/278个，最大12.94个百分点。

NB2推导`P(N_after>b)=q*SF_NB2(b)/(1-P_NB2(0))`，其中b=N_before。b=0时它恰为q；b>0时再与Pattern同事件概率比较。聚合结果见vocal_probability_conditions_36.csv及vocal_cross_module_summary.csv。观测/OOF逐行诊断仅在本地完整版中。不能把b>0时合法的p_V<q本身当违反约束；只用pv_le_q_violated和zero_baseline_identity_violated判断这两项约束。

当前允许：原HVA单模块响应/组合推断、原标记Latency、独立计数均值/尾部的各自分析及并列情景敏感性。当前不提供：一个同时生成HVA标记与发声次数的相容联合分布。因此不能把两概率相乘、相除推导新的联合事件或条件次数，也不能将同一个V事件和q重复计入效能。若Q4必须依赖这种联合分布，接口标不可用，不能静默校准或挑一个更有利概率代替。

common_joint_count_pattern_distribution_available=false与within_HVA_probability_coherence_pass=true可以同时成立：前者是跨模块问题，后者是原联合概率内部检查。诊断完成不意味着约束已修复，也不直接否定各模块已有的折外证据。

## 参考人口、支持与不确定性

36条件是场景，不是配对平均。主要配对按对应Control、每对等权、两侧半权；全278口径支持后Flat/Mod/TV分别30/20/39对。不同类型主要人口不能据差值直接排名。各条件保留joint_support、positive_time_type_n、positive_time_context_type_n及conditional_time_joint_support；模型推算不写成实际观测。

expID和natural_track分别使用，不平均两套区间；同单位同replicate保留相关性。NPZ中combo/count/time/paired_time分别保存；共享同抽样不等于跨模块事件逻辑已相容。置信区间为固定模型、参考和规则下逐点参数区间，不包含模型选择、全部标注机制或个体身份依赖。

没有更新新主口径的未来Latency预测范围；原S6未来V/A预测保留为历史，不能改标签后重用。Duration真实时长不提供数值，文件中为空加原因。Q2到Q4的依赖、距离重复计入、噪声因果解释仍需单独论证；群体概率不是响应人数。


## 仓库交付范围

本目录只含聚合结果和运行元数据；原始数据、逐条预测、配对映射、完整审计和NPZ均未上传。private_context_manifest.json列出复用所需私有历史文件的路径及哈希，需按docs/Q3_REPRODUCIBILITY.md从队内渠道恢复。历史报告中的results/及原附件链接只在恢复本地材料后可用。
