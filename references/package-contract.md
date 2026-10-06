# 文档包契约 v3（兼容 v2）

## 文件与证据

manifest.json 保存来源、资产、出现位置、阅读版本、限制及历史解读索引；knowledge/ 保存全文阅读单元、导航、事件日志与可重建的索引和覆盖状态；SKILL.md 是项目入口，visual-index.md 是视觉目录。全部工作引用为包内相对路径，show 的显示结果输出绝对路径供宿主打开。

来源 original 是完整文件；资产 original 是逐字节保留的内嵌成员或独立材料。ID 由内容哈希生成。正文段落编号仅在同一来源哈希内有效；xml_para_id 是额外原生定位，不保证跨版本永久有效。

资产按内容去重，origins 保留多个来源成员，occurrences 保留多次出现。内容相同的内嵌 Excel 不构成独立证据。附近 Visio 和 JPEG 仅为 candidate_not_verified_equivalent。

## 定位精度

- DOCX：part、paragraph、relationship_id、target_part、shape_id 构成原生定位，正文与辅助结构可反查锚点。
- DOCX 渲染：页面及像素属于派生排版，不能冒称 Microsoft Word 原始页码。记录程序、分辨率、哈希；XML 到页面坐标映射尚未自动实现。
- PDF：文件页序从 1 开始，与印刷页码分开；转换图像记录页面尺寸、旋转与像素尺寸。
- 模型图内定位：估计位置，说明像素坐标系并复核。裁剪记录父图、区域、偏移和缩放。

## 状态及辅助数据

readable_unreviewed / rendered_unreviewed 表示有图像但语义未复核；pending 表示原件保留而内容图像待生成；icon_only 不得作为内容证据。阅读 role 区分 original_image、page_content、region_content、icon；原件不会被派生图覆盖。

Excel sidecar 保存 sheet、隐藏状态、单元格、原始值、类型、样式索引、公式、缓存、合并范围和样式 XML，不计算公式或自动转换日期。打印导出可能遗漏隐藏行列、打印范围外内容，须核对原件及 sidecar。

Visio sidecar 保存页、图形文字、父图形、原生属性、几何 cell 和连接。BeginX/EndX 不自动代表业务方向；泳道、继承与隐藏层需视觉核对。导出页与原生 page part 的映射未自动认证。

DOCX sidecar 保留段落、编号属性、直接层级表格、合并和嵌套关系、批注及修订；不补全源样式不一致、显示编号与页码。

## 更新与验证

新版本生成新包，旧包保留。interpretations 迁移时核对 dependencies；来源、阅读版本哈希改变或消失触发 needs_revalidation。原图不变但正文上下文改变也可能使解读失效，记录必须绑定来源。

verify 检查实际文件哈希、成员清点、定位及引用；freshness 仅核对清单依赖，不替代 verify。历史清单是旧状态快照，不承诺旧文件位于新包。

```text
docpack.py check
docpack.py build --input FILE_OR_DIRECTORY ... --output NEW --doctype BRD --renderer auto
docpack.py list --package PACK
docpack.py query --package PACK --term "Commercial" --limit 12
docpack.py show --package PACK --asset ASSET_ID
docpack.py crop --package PACK --asset ASSET_ID --rendition RENDITION_ID --bbox X1 Y1 X2 Y2
docpack.py record --package PACK --file INTERPRETATION_JSON
docpack.py cellview --package PACK --asset ASSET_ID --sheet SHEET --cells A1 D4
docpack.py verify --package PACK
docpack.py freshness --package PACK
docpack.py build --input UPDATED ... --output NEW --previous OLD --renderer auto
```

包内 scripts/docpack.py 可独立继续使用，无需全局安装。none 只捕获并生成 PDF/原图阅读版本；LibreOffice 使用隔离配置，不复用用户运行会话。导出超时/失败写入限制，原件保留。

Excel 导出使用 SinglePageSheets（整张 sheet，不被打印范围切开），但隐藏行列仍可能不显示。cellview 可按坐标输出原生单元格的辅助证据图，明确标为 structured_cell_view，既不是作者原始可见版面，也不计算公式。LibreOffice 自身打开/导出可能重算公式，出现数值差异时比较原始缓存与导出版本，不能默认采用新计算结果。

大页面初始预览限制为 4096 像素边长/1600 万像素，实际 dpi 单独记录；保留矢量 PDF，局部从 PDF 重新以高 dpi 渲染，避免只放大低分辨率预览。源文件内容不因预览尺寸或检索返回上限被裁掉。

## v2 兼容与质量

旧包保留；upgrade --package OLD --output NEW 在新目录迁移原件、阅读版本与历史解读，不推断已读状态。build 默认建立两阶段队列；宿主按 reading-workflow.md 执行。record 原有 interpretation 格式继续有效，但不自动产生原子知识或阅读覆盖；新版事务使用 expected_revision。

query 返回 total_hits、next_offset 和匹配原因，正文片段仅用于导航；read 支持完整正文分页、上下文、原生数据与图像输入路径。read receipt 证明材料已返回，不证明宿主模型已理解。视觉查看和 source_checked 属于可检查出处的声明，脚本无法核验宿主工具历史或自动证明语义蕴含。

事件是知识更新的提交点，索引和 coverage 可重建。verify 分别输出 evidence 与 learning 结果；review 的 pending/completed_with_gaps 与 actually_read 明确分开。新语义层不设正文、短条款或知识记录数量的省略上限。


升级原生索引时保留旧单元格派生图生成时的 auxiliary_snapshot（相对路径与哈希），不将旧图默默绑定到新索引。cached_result_present 表示原件有实际存储值；value_element_present 单独标记 XML 值元素，即使是空 <v/>。全部已序列化空白单元格均保留，未在XML中出现的坐标不虚构为已捕获证据。


XLSX 中尚未单独解释的批注、图形/媒体、嵌入对象、外部链接、透视表及结构化表等原生部件，以及 VSDX 母版部件，按 ZIP 成员记录位置与哈希并加入明确缺口。可读页面不自动证明这些隐藏或继承内容已全部阅读；后续可通过原件中的成员继续处理，不能绕过缺口宣称全文完整。


read 指定知识ID时同时展开其当前有效证据单元、上下文及图像路径，去重但不自动标记已读。已丢失、被替换或指纹变化的历史单元明确列出，不把旧引文重新绑定到新来源。必要时按 next_text_offset 继续读展开的原文。

## v3 契约与性能

新包schema_version=3、learning.version=3；v3运行时仍支持v2读取与旧事件回放。build默认renderer=auto；none明确不导出版面，但DOCX未生成页面仍计视觉缺口。可用工具由check探测，不自动安装。

内嵌DOCX资产的content_source_id指向同字节内容来源；来源的parent_assets保留父资产与出现ID。内容源是文本/页面的唯一阅读队列，资产共用其阅读版本，不重复清点已读量。附件证据同时依赖其父来源上下文。相同内容去重不等于各出现上下文相同。

query支持--expand related，沿已有知识关系、证据、邻近附件出现位置展开一跳。结果的related_via解释导航路径，total_hits和next_offset包含展开候选；不是自动语义等价证明。检索不自动发明同义词或来源优先级。

日志journal_schema_version=2，每事务visual_reads只存一次，记录/阅读状态使用visual_read_ids引用相关查看信息；回放使用带事务版本的V标识。输入record协议仍接受原visual_reads数组；旧事件字节保持不变。

checkpoint、倒排索引及coverage都是可重建投影。缓存绑定manifest、units、navigation及每个事件的文件内容哈希和版本；不以mtime/大小替代完整性。缓存损坏回放恢复，源或日志篡改拒绝。写入仍串行、预期版本检查与原子提交。

upgrade只在新目录运行，保留旧manifest与阅读单元快照，展开旧包内DOCX；不重写旧日志。旧引用因新格式、上下文或单元变化失效时保留历史，不能默默重绑；未读材料不会自动变成已读。
