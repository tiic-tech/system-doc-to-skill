# Synthetic Request Portal BRD

本材料为虚构测试。角色、金额、规则和期限不来自真实项目。

## Roles and visibility

Applicant只能查看自己的申请。Reviewer能查看分配给自己的申请，不自动具有Administrator权限。SLA（Service Level Agreement，服务级别协议）在本材料中指响应时间约定。

## Conditions and exceptions

金额大于或等于1200个测试单位的申请需要两名不同Reviewer批准；小于1200时需要一名。否定条件：紧急申请即使尚未开始审批也不能撤回。

签署期限为12个自然日；异常处理期限为3个工作日，不能混用。原材料没有定义节假日日历。

| Field | Rule | Unresolved detail |
|---|---|---|
| requestId | 重复请求不得重复启动审批 | 未定义保存期 |
| attachment | 最大8 MB，允许PDF | 未定义MB的二进制/十进制口径 |
| fee | 空白 | 空白不等于0或免费 |

## Lifecycle

Submitted → Review → Approved。拒绝后是否允许修改和再次提交尚未定义，不能仅凭状态名称推断。

English retrieval fixture: a bid and several bids refer to the same inflected word. FAR is a separate identifier; Farmwork is a different word. This paragraph is a retrieval fixture and defines no business meaning for FAR.

## Short requirement

保留审计记录。短要求不得因为字数少而略读。
