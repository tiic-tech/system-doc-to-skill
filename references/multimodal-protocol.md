# 多模态持续解读

## 检索与实际查看

1. 检查 verify 结果及来源版本；首次读视觉目录，发现文字索引尚未描述的图和 pending 对象。
2. 用章节、图注、上下文、原生文字定位候选，不把搜索未命中当作图中没有规则。
3. show 返回图像绝对路径，用当前宿主的图像工具把像素送入模型。Codex 通常使用可用的 view_image；Claude/其他宿主用其图像读取或附件机制，不硬编码不存在的工具名。
4. 先看全图确定边界、角色、方向和注释；小字按需 crop。跨区域箭头查看两个端点和完整连线，不只看一个局部。
5. 与正文、批注、native sidecar 核对；审批、权限、金额、期限、循环上限必须保留限定语。
6. 输出观察、业务解释、未知及出处；建议验收或设计另列，不升格为来源要求。

无图像工具时列出问题、阅读版本路径、辅助数据与未核验边界，不声称视觉核验。不另接付费 API 或自动上传包。

## 持续记录

使用 [动态更新协议](dynamic-updates.md) 的新版事务，不依赖聊天历史。visual_reads 必须保存 rendition_id、sha256、实际 tool 和具体 observation；重要观察分别绑定 visual 单元，必要时增加原图像素 bbox。read receipt 只证明材料已返回，不能代替看图。

```json
{
  "expected_revision": 0,
  "model": "实际宿主/模型；版本未知则注明",
  "receipt_ids": ["Q..."],
  "visual_reads": [{"rendition_id": "R...", "sha256": "实际哈希", "tool": "实际工具", "observation": "本次看到的节点、箭头、注释与边界"}],
  "records": [{
    "kind": "process", "name": "流程名", "scope": "具体来源及范围",
    "claims": [{"content": "限定范围的观察", "authority": "visual_observation", "evidence": [{"unit_id": "U..."}]}],
    "review_status": "source_checked", "review_notes": "实际核对的图及正文，未核验部分另列", "unknowns": []
  }]
}
```

示例 ID 不可直接提交。unreviewed 是候选；source_checked 是已核对决定性出处、条件及反证的宿主声明；human_reviewed 须有实际人工 reviewer；needs_revalidation 不能作为当前已核验结论。source_checked 不代表业务方批准，模型一致不证明真实。

绑定上下文来源、资产与图像依赖，避免图相同而上下文变化时错误复用。旧版 question/interpretation/dependencies 格式仅用于兼容历史记录，不自动增加新知识或阅读覆盖。脚本无法审计宿主工具历史，也不能证明解释正确。

## 视觉边界

小字不清、已压缩、截图截断、交叉箭头、线型/颜色规则、字体替换及隐藏层：保留原件和未知，再导出/裁剪；模型不能恢复原图不存在的细节。PDF 服务器缩放不保证坐标精度，需要定位时使用包中明确尺寸图像。

局部截图不替代原生 Excel 单元格、隐藏数据或 Visio 其他页的证据。

官方能力边界：
- [OpenAI 文件输入](https://developers.openai.com/api/docs/guides/file-inputs)：非 PDF 内嵌图片不自动进入图像上下文。
- [Claude 文件上传](https://support.claude.com/en/articles/8241126-upload-files-to-claude)：非 PDF 内嵌图像不能依赖普通文字提取。
- [Claude 坐标说明](https://platform.claude.com/docs/en/build-with-claude/vision-coordinates)：缩放和估计坐标需映射与复核。
