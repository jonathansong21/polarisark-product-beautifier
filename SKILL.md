---
name: polarisark-product-beautifier
description: 将单张商品实拍图精修为真实、克制的电商白底图；适用于清理摄影瑕疵、主体抠图、轻微校正、色彩光影与材质细节优化，同时严格保持商品结构、材质、颜色、Logo 和文字不变。不用于场景合成、非白底背景、换色、换款或商品重设计。
metadata:
  short-description: 单图商品白底精修，保持真实结构与颜色
---

# PolarisArk Product Beautifier

## 目标与范围

把一张商品实拍图变成可审核的电商白底精修成片。核心原则是：修复摄影问题，不重新设计商品。

- v0.1 每次只精修一张目标原始图、一个 SKU；可以接收色卡、产品事实档案或参考图作真实性证据，但不精修或交付这些参考资料。
- 背景固定为纯白 `#FFFFFF`。默认使用 1:1 构图、均衡留白和自然投影；用户明确提供的比例或阴影要求可以覆盖对应默认值。
- 不内置任何平台预设。仅提供平台名称不等于提供平台规范，也不得据此声称平台合规。
- 交付最终精修图、实际使用的最终 Prompt、执行模式及简短说明；不交付透明背景版本、蒙版或其他中间资产。

## 触发与路由

触发于用户要把现有商品实拍图清理、校正并输出白底成片，例如“精修成电商白底图”“清掉灰尘和支架但不要改变产品”“校正这张商品图的拍摄倾斜和光线”。

不处理以下意图：

- 场景图、广告创意图、模特图、复杂合成或非白色背景。
- 换 SKU 颜色、创造新款、改变包装或重绘 Logo、标签文字、认证标识。
- 仅裁剪、压缩、改格式等不涉及精修判断的机械处理。

如果用户一次提供多张待精修图，说明当前只支持单图，请用户选定一张后继续；不要批量处理。

## 输入判断

1. 确认有一张可读取的目标原始图；没有原图时请求补充。
2. 判断商品售卖单元边界。若画面包含多个物体、配件或道具且归属不清，询问哪些属于该 SKU；确认后的组件要保留真实数量和位置关系。
3. 识别主体、可见结构、部件数量、Logo/文字、主要材质、颜色线索、透明/半透明/镂空区域，以及明显的摄影瑕疵。
4. 仅当不确定性会改变商品真实性时询问必要问题。缺少非真实性相关的审美或规格信息时，直接采用默认规则继续。
5. 无可靠参考时，不把商品事实当作常识猜测；对颜色只做有依据的还原和明显色偏、曝光问题修复。

## 工作流程

按“问题诊断 → 选择必要处理 → 构造 Prompt → 调用系统生图 → 商品一致性 QA”完成任务。以下能力是可选菜单，不是必须全部执行或固定顺序：

- **Clean 清理**：移除确认属于拍摄环境的灰尘、污点、指纹、毛屑、胶痕、支撑物和杂物；保留商品真实纹理、褶皱和磨损。
- **Cutout 抠图**：完整提取主体，保留透明、半透明、毛绒、织物和镂空边缘；清除背景残留、白边、黑边、锯齿和色污染。
- **Correct 校正**：修复拍摄倾斜、轻微透视和镜头畸变，整理方向、居中和留白；不得改变商品真实几何比例或进行塑形。
- **Color 色彩与光影**：优先真实还原而非美化；校正白平衡、曝光、高光、暗部和局部光照不均，避免夸张饱和、死黑和过曝。
- **Enhance 材质与细节**：按可识别材质整理高光、反射、通透度和纹理；不得把一种材质变成另一种材质或改变表面工艺。
- **Finish 成片**：使用纯白 `#FFFFFF` 背景，修整轮廓并保留或重建自然投影。自然投影以接触阴影为主，可以包含克制的柔和投影；方向要与原有光线一致，不得制造悬浮感或抢夺主体视觉。

## 生图执行与 Prompt

使用系统内置 `image_gen` 的编辑模式处理原图；不得只输出文字方案或 Prompt 代替成片。将目标原图标记为 `edit target`，将其他图片逐一标记为 `authenticity reference`。内置能力不可用或调用失败时说明失败并停止当前任务；可以告知用户存在需要明确确认的 CLI/API 回退方案，但不要静默切换。

根据诊断结果生成传给 `image_gen` 的最终 Prompt。使用以下紧凑结构，只保留与本次任务有关的内容：

```text
Use case: precise-object-edit
Asset type: ecommerce white-background product image
Input images: Image 1: edit target; additional images: authenticity references only
Primary request: perform only the product-photo corrections identified in this task
Scene/backdrop: solid pure white #FFFFFF
Subject: preserve the same SKU and every confirmed sellable component
Composition/framing: use the user's explicit ratio and shadow requirements; otherwise use 1:1, balanced padding, and a natural grounded shadow
Lighting/materials: apply only the diagnosed lighting, color, and material corrections
Text: preserve every visible logo, label, certification mark, model number, and marking exactly; do not redraw or guess unclear text
Constraints: preserve structure, component count, positions, proportions, color, material, surface finish, transparency, holes, and fine edges; change only confirmed photographic defects
Avoid: no new objects, recoloring, reshaping, redesign, invented details, altered text, watermark, halo, hard cutout edge, duplicated texture, or abnormal reflection
```

用实际诊断出的修改项替换通用的 `Primary request` 和 `Lighting/materials` 内容。不要附加未使用的能力或创意美化要求；每次纠正调用都要重复全部真实性约束。

对照原图和参考资料检查生成结果。首次结果存在明确且可修正的违规时，在保留全部真实性约束的前提下最多进行一次定向纠正；纠正后仍违反商品事实时，不得作为成功结果交付。

## 最高优先级的真实性约束

- 不增加、删除、移动或改造商品本体的结构、零件、装饰、孔位、拉链、缝线、宝石、接口、配件或文字。
- 不改变商品真实颜色、材质类别、表面工艺、比例或结构关系。
- 不改写、重绘或伪造 Logo、认证标识、包装文字、刻度、型号等信息。文字或 Logo 模糊时宁可保留并披露风险，不要猜写。
- 不删除真实破损、磨损、纹理、褶皱或制造特征。只有用户确认该问题是拍摄样品的偶发损伤、且不代表正常交付商品时，才可以修复。
- 不为遮挡、过曝或低清区域编造无参考依据的细节。
- 用户明确要求换色、重设计或删除真实商品特征时，说明超出本 Skill 边界，不执行该部分。

## 输出与失败处理

交付内容必须包括：

- 一张白底精修成片，或明确说明该原始图为何无法安全交付。
- 实际传给 `image_gen` 的完整 Prompt；成功时返回与成片对应的最终 Prompt，失败时返回最后一次尝试的 Prompt 并标明未产出合格成片。
- 执行模式，标明为“系统内置 `image_gen`”。
- 简短处理摘要，只列实际发生的主要变更。
- 真实性说明：使用了哪些参考、采用了哪些默认假设、哪些区域未处理及原因。

最终 Prompt 使用可复制的 Markdown 代码块呈现，属于结果元数据，不另存为文件。

输出前检查：主体仍为同一 SKU；部件数量、位置、比例、轮廓、Logo 和文字未改变；材质和颜色与证据一致；无背景残留、硬边、断边、孔洞填错、伪影、重复纹理、异常反射或新增物体；主体完整，背景为纯白，且画面符合用户明确指定的比例与阴影要求，未指定时使用 1:1 构图和自然投影。

若无法安全修复，指出具体区域和可观察的问题，给出最少的补充材料或补拍建议；不得用猜测性成片掩盖不确定性。
