# 生产工程 Second Brain(Day23–Day28)· 中文版

> 英文原版:[README.md](README.md)

面向 **Phase 2 生产工程** 的长期复习、工程实践与面试准备系统:Docker → Docker Compose → Deployment → Kubernetes Foundations → Kubernetes Workloads → 生产 AI Backend 架构。

这**不是**课程复述。它压缩课程、跨天建立连接、提取记忆模型,并链接回正式课程和真实制品。课程正文始终是唯一事实来源。

## 五份文档

| 文档 | 定位 | 什么时候用 |
|---|---|---|
| [一页速览(中文)](Day23-Day28-OnePage.zh.md) ｜ [EN](Day23-Day28-OnePage.md) | **回忆** — 整个阶段浓缩成一页 | 每天 5–10 分钟复习;面试前一晚 |
| [Super Cheat Sheet](Day23-Day28-Production-Super-CheatSheet.md) | **解释** — 每天的心智模型、责任地图、权衡、真实误区 | 三个月后恢复某一天的模型;面试前 30 分钟 |
| [架构与故障地图(中文)](Day23-Day28-Architecture-Failure-Map.zh.md) ｜ [EN](Day23-Day28-Architecture-Failure-Map.md) | **连接** — 跨课程 Mermaid 网络 + 统一 Failure Matrix | 线上故障定位;架构与归属推理 |
| [Artifact Templates](Day23-Day28-Artifact-Templates.md) | **执行** — 可复用制品模式,附来源链接 | 开发时需要 Dockerfile / Compose / Nginx / K8s / Helm / 架构模式 |
| [Interview Q&A](Day23-Day28-Interview-QA.md) | **表达** — Beginner/Intermediate/Senior 问答,含真实学生回答 | 英文面试练习;把概念转成口头判断 |

> 说明:Super Cheat Sheet、Artifact Templates、Interview Q&A 目前只有英文版。其中 **Interview Q&A 建议保持英文**——它包含专门的英文表达纠错(如 `sevral` → `several`、`is not meaning` → `does not prove`),译成中文会失去意义。

五份文档内容刻意**不重复**:Cheat Sheet 负责解释,Failure Map 负责连接,Templates 负责执行,Q&A 负责表达,OnePage 负责回忆。

## 推荐复习顺序

**第一轮(建立模型),约一次专注时段:**

```text
1. 一页速览            -> 先把完整知识链和终极模型装进脑子
2. Super Cheat Sheet   -> 每次一天,Day23 -> Day28
3. 架构与故障地图      -> 看这些天如何连成一个系统
4. Artifact Templates  -> 对照打开每个链接的示例文件
5. Interview Q&A       -> 把 strong answer 出声念出来
```

**每天 5 分钟复习:** 只看一页速览。

**面试前 30 分钟:** 一页速览 → Interview Q&A → 架构与故障地图里的 Failure Matrix。

**线上故障时:** 先看 Failure Matrix(判断哪一层拥有这个故障),再回到 Super Cheat Sheet 对应那一天。

**三个月后回归:** 一页速览 → Super Cheat Sheet 的"真实课堂误区"小节 → 架构与故障地图。

## 本阶段建立的十项工程判断

```text
Artifact Identity(制品身份)· Runtime Lifecycle(运行时生命周期)· State Ownership(状态归属)
Network Boundary(网络边界)· Desired State(期望状态)· Failure Boundary(故障边界)
Rollback Boundary(回滚边界)· Data Repair(数据修复)· Monitoring(监控)· Observability(可观测性)
```

重点不是记住工具名称,而是对任何一次变更都能说清:到底什么在运行、每份状态归谁所有、从哪里能访问到什么、声明了什么、故障止于何处、如何回退、用什么证据证明成功——以及**回滚修不了什么**。

## 课程与详细资料来源

| Day | 课程 | 主要制品 |
|---|---|---|
| Day23 | [Docker Fundamentals](../devops/day23-docker-fundamentals.md) | [examples/docker/fastapi/](../../examples/docker/fastapi/) |
| Day24 | [Docker Compose](../devops/day24-docker-compose.md) | [examples/docker/compose/](../../examples/docker/compose/) |
| Day25 | [Deployment Foundations](../devops/day25-deployment-foundations.md) | [examples/deployment/](../../examples/deployment/) |
| Day26 | [Kubernetes Foundations](../devops/day26-kubernetes-foundations.md) | [examples/kubernetes/ai-backend-baseline.yaml](../../examples/kubernetes/ai-backend-baseline.yaml) |
| Day27 | [Kubernetes Workloads](../devops/day27-kubernetes-workloads.md) | [examples/kubernetes/rag-platform/](../../examples/kubernetes/rag-platform/) |
| Day28 | [AI Backend Production Architecture](../devops/day28-ai-backend-production-architecture.md) | [examples/ai-backend-architecture/](../../examples/ai-backend-architecture/) |

详细参考资料(此处不重复):[cheat_sheets/devops.md](../../cheat_sheets/devops.md) 与 [interview/devops.md](../../interview/devops.md)。课程上下文:[CURRICULUM.md](../../CURRICULUM.md)、[ROADMAP.md](../../ROADMAP.md)。

## 验证边界(相信任何片段之前请先读这里)

本仓库中 Day23–Day28 的每一个示例都是**教学 / 概念模版**。这个手册仓库没有可运行的 FastAPI 应用、域名、TLS 证书、Kubernetes 集群、镜像仓库或模型提供商账号。因此:

```text
未执行:docker build / docker run / docker compose up / nginx -t /
        kubectl apply / helm install / 任何 AI backend 运行时、
        队列重投、provider 故障注入、压测、冒烟、运行时回滚、数据修复演练。

仅适用:静态推理、`docker compose config`、`helm lint` / `helm template`,
        以及仓库自带的确定性静态检查脚本。

静态验证 != 运行时成功。
```

占位镜像使用保留的 `.invalid` 顶级域或可变的 `:replace-...` 标签;`example.com` 是保留示例域名;所有 secret 均为占位值,真实值在带外注入。这些文档中不含任何真实 secret、token、密码、凭据或预签名 URL。

## 知识边界

本 Second Brain 只覆盖 Day23–Day28。Phase 3(后端基础:PostgreSQL、SQL、Redis、数据库设计)会深化 Day28 引入的持久数据、事务与 schema 设计边界。Day29 已列入课程规划,但其课程文件尚不存在——此处不对其内容做任何假设。
