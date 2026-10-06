# 动态扩展与知识更新

关键词：record、expected_revision、claims、evidence、修订、冲突、依赖、replace_units。

所有正文/表格/原生辅助数据属于来源证据；知识是可修订的派生解读。不要直接编辑 units.jsonl、事件日志或来源文件。更新通过 record，新增已选择来源或更新原件用 build --previous OLD --output NEW；保留旧包。

## 一个事务的最小结构

~~~json
{
  "expected_revision": 0,
  "model": "实际宿主/模型；准确版本未知则注明",
  "receipt_ids": ["read 返回的 Q..."],
  "visual_reads": [],
  "reads": [
    {"unit_id": "U...", "stage": "initial", "status": "read", "notes": "本次实际阅读的内容及边界"}
  ],
  "records": [
    {
      "kind": "term",
      "name": "来源中的术语",
      "scope": "明确的项目/来源/章节或对象范围",
      "aliases": [],
      "claims": [
        {"content": "有范围的解释", "authority": "interpretation",
         "evidence": [{"unit_id": "U...", "start": 0, "end": 4, "quote": "精确原文"}]}
      ],
      "unknowns": [],
      "review_status": "unreviewed"
    }
  ]
}
~~~

字段中的 ID 和 quote 必须使用本次 read 的实际结果，示例不是可提交数据。包内普通 JSON 更新文件用 record --file FILE 提交。expected_revision 取最近 review/read/query 的值；冲突时重新读取并合并，不强行覆盖。

reads 可用 unit_ids 保存一组实际读完的单元。深读用 stage=deep、status=deep_read；gap 必须给原因。长文本须用多份 receipt 覆盖全部字符。reads 的 knowledge_dependencies 可绑定具体知识版本，知识修订后受影响深读重新核验。

visual_reads 每项必须有 rendition_id、sha256、实际 tool 和具体 observation。视觉 claim 的 evidence 绑定 visual 单元；bbox 可选，使用原始阅读图像像素，必须在 dimensions_px 内。缩放后坐标须转换。查看声明仍是声明，脚本无法审计宿主工具历史，绝不能虚构。

## 知识记录

kind 可用 overview、term、concept、object、rule、process、interface、decision、conflict、issue、navigation 或实际需要的其他类型。claims 的 authority 必须为 source_requirement、visual_observation、interpretation、background、suggestion 之一。

- source-derived 断言逐条绑定证据，文本引用精确匹配本单元字符区间，脚本补入单元 fingerprint 和来源/资产/图像依赖。
- 原生字段可引用 {unit_id, field, value}，例如 formula、hidden_row、hidden_sheet；value 必须精确匹配 native_metadata。公式文本与缓存值分开，不能把没有缓存值的公式当作已计算结果。
- background 和 suggestion 可无文档出处，但不能冒充文档要求。引入外部材料须明确选择并作为独立来源，不自动爬取。
- aliases 需要证据绑定；候选翻译/缩写解释标为 interpretation/unreviewed。检索扩展不证明源文档定义了同义关系。
- source_checked 必须有 review_notes，说明限定条件和反证核对，文本证据须有完整 read receipt，视觉证据须有本次查看声明。它不等于人类业务批准。
- human_reviewed 只能在实际人类复核后填写 reviewer。未确认评分保持 unknown，不默认 medium。

## 新增、修订、关系与冲突

新增记录不指定 id 时自动生成。修订指定原 id，提交完整的新记录及 reason；版本递增，supersedes_version 关联历史。旧版本始终保留。kind/name/scope/claims 不得缺省，避免只更新别名时无意丢失规则。

relations 使用 kind、target_id，目标须存在或在同批创建；kind 例如 defines、applies_to、depends_on、contradicts。将作为判断前提的目标同时放入 knowledge_dependencies=[{id,version}]，才能在它修订时自动失效。关系名称不代表模型已证明关系。

conflict 至少保留两个不同阅读单元的证据及 unknowns。来源相同/内容去重副本不算独立佐证。不得因日期较新、正文位置或模型一致就自行消除冲突；解决依据和业务决定另行记录。

## 修订句子切分

replace_units 每项指定 parent_id（paragraph/page_text 单元）、reason、spans=[[start,end],...]。新区间必须连续覆盖完整原文，不得重叠/遗漏；切分变化使原引用或阅读记录重新核验。补充业务解释用 records，不能通过改原文来消除矛盾。

## 提交、恢复和问答闭环

每次事务提交一个带哈希链的事件，原子替换落盘后才算成功。索引与覆盖是可从事件重建的派生文件；中断后 read/review 回放日志，review --recover 重建缓存。同包写入串行；活跃进程锁不能被恢复命令强删。

问答前检查 verify、freshness、review；陈旧记录不进入有效知识检索。每次发现新定义、边界、例外、图中规则、关系或旧解释错误，调用 record 写回，再通过 query/read 验证能重新找到。没有新发现无需复制整段对话。问答不依赖聊天历史作为唯一记忆。

旧版 interpretation 仍可读取和追加，属于有范围的历史记录，不自动生成原子知识、阅读覆盖或全面复核声明。

## v3 输入兼容

事务输入保持上述格式。脚本将visual_reads放在事件级，阅读及知识只引用相关图，不向所有文本单元复制所有看图信息。read/query返回的visual_read_ids可在knowledge/checkpoint.json的visual_attestations中回查；它们是历史声明，不授权本次虚构查看。

新增关系要有来源核对基础；问答可用query --expand related回查并展开附件。不存在的关系、模型生成关键词或候选翻译不能冒充来源证据。业务未知与技术缺口分别记录，保留冲突双方及影响，不靠日期或位置自动解决。
