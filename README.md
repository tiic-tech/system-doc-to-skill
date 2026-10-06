# system-doc-to-skill

把复杂系统开发文档拆解成保留原件、可追溯、可持续问答和更新的本地文档包。

适用于 RFP、TP（投标技术方案）、BRD、PRD，以及架构、接口、设计、实施和运维材料。Skill 的角色是需求工程与多模态文档架构师；脚本负责捕获、定位、版本和索引，宿主模型负责真实阅读与解释。本项目独立实现，没有 book-to-skill、PaperIndex、向量数据库或模型 API 运行依赖。

## 使用方式

将仓库根目录作为一个完整 Skill 放入 Codex 的 skills 目录；入口为 [SKILL.md](SKILL.md)，界面配置为 [agents/openai.yaml](agents/openai.yaml)。在支持本地文件与图像工具的宿主中调用：

```text
$system-doc-to-skill 将我明确选定的文档拆解为文档包，完成全文初读和深读，保留证据与未决项，支持后续问答和持续完善。
```

项目文档包自带脚本与项目 Skill，可以整体搬迁，不要求注册每个项目包。Claude 或其他宿主可读取同一文件协议，但必须使用各自的实际文件/图像工具；这不是跨宿主语义正确性的认证。

## CLI 快速开始

Python 3.10+。正文/OOXML捕获、检索和日志使用标准库；PDF读取、图像和裁剪需要已有 PyMuPDF；Office页面导出需要已有 LibreOffice。缺失能力会列为技术缺口，脚本不安装软件。运行check查看当前能力。

```bash
python -B scripts/docpack.py check
python -B scripts/docpack.py build --input examples/requirements.md --output work/example-docpack --title "Synthetic requirements" --doctype BRD
python -B scripts/docpack.py verify --package work/example-docpack
python -B scripts/docpack.py review --package work/example-docpack --next --limit 8
python -B scripts/docpack.py query --package work/example-docpack --term "审批" --expand related --limit 10
python -B scripts/docpack.py read --package work/example-docpack --unit 从候选取得的ID
python -B scripts/docpack.py record --package work/example-docpack --file 本次发现事务.json
```

`read` 返回材料不会自动标记已读。宿主应完成初读、深读后用 `record` 写入实际阅读状态及断言级证据；事务示例见[动态更新协议](references/dynamic-updates.md)。问答检查版本、检索候选、展开相关正文/表格/附件、核验决定性证据，再将新增发现写回。

`build --renderer auto`默认探测已有工具；也可选none/libreoffice。none不会生成Office页面，缺口仍保留。更新来源用 `build --input 更新材料 --previous 旧包 --output 新包`，保留历史，不直接修改原件或事件日志。

## 能力与边界

- 自动递归展开内嵌DOCX，按内容哈希去重，保留各出现位置和父文档上下文。图标不是附件内容证据。
- 原文、句内范围与格式提示分开；保存表格、批注、修订、删除线、高亮、隐藏文字及样式来源。格式不自动代表业务批准或取消。
- 支持Unicode/中文、英文词项边界和基础词形；别名与一跳关系须有记录依据。检索未命中不能证明规则不存在。
- 查看记录按事务共享；索引和检查点按文件内容哈希校验，可从串行、原子、版本检查及哈希链日志恢复。
- 支持TXT、Markdown、CSV/TSV、DOCX、PDF、XLSX、VSDX、PNG、JPEG、WebP。难以读取的原生部件显式计入缺口，不声明任意复杂度均已验证。

材料完整性、实际阅读覆盖与解释复核分开报告。`source_checked`是宿主来源核对声明，不是专家审批；脚本不能证明模型真正调用了图像工具或证明解释蕴含于原文。允许带明确缺口进行有范围问答，业务冲突、未知定义、占位符和派生计算值须保持区别。

## 合成样例与验证

[requirements.md](examples/requirements.md)是重新编写的虚构材料，未改写真实客户文档。复杂结构可用标准库生成器产生：

```bash
python -B examples/generate_office.py --output work/synthetic-inputs
python -B scripts/docpack.py build --input work/synthetic-inputs/requirements.docx --output work/office-docpack --renderer none --title "Synthetic office materials"
```

生成器演示重复内嵌Word、合并/嵌套表格、继承删除线和显式关闭、隐藏文字，以及内嵌Excel隐藏行与无缓存公式；none模式保留视觉缺口。原始样例、包和解读不要作为已完成模型深读的证明。

本版本保留43项原有程序测试及13项v3回归测试，共56项已通过；完整测试需要现有PyMuPDF。测试为确定性行为验证，不等于业务语义准确率：

```bash
python -B -m unittest discover -s scripts -p 'test*.py' -v
```

公开仓库包含通用实现和虚构测试材料，不包含真实项目文档包、业务答案、内部附件或本机验收日志。详细协议见[包契约](references/package-contract.md)、[两阶段阅读](references/reading-workflow.md)、[多模态阅读](references/multimodal-protocol.md)。
