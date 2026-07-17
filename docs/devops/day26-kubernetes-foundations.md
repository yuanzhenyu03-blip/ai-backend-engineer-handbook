# Lesson 26 — Kubernetes Foundations

# Lesson Metadata

Status: Completed

Template: LESSON_TEMPLATE_v2

Version: v1.0

Difficulty: Intermediate

Estimated Time: 6-7 hours

Prerequisite: Day25 — Deployment Foundations

Previous Lesson: Day25 — Deployment Foundations

Next Lesson: Day27 — Kubernetes Workloads

Engineering Artifact: An example Kubernetes manifest (`examples/kubernetes/ai-backend-baseline.yaml`) with a ConfigMap, a Secret template, a three-replica Deployment (FastAPI + logging sidecar Pod template), and a Service — plus a README that separates static validation from runtime validation.

Estimated Study Time:

```text
Reading: 130-160 minutes
Exercises: 80-110 minutes
Hands-on manifest authoring / static validation: 80-110 minutes
Review: 30-45 minutes

Total: 6-7 hours
```

---

# Learning Objectives

After completing this lesson, the student should be able to:

* Explain the difference between a one-time command and a declared desired state that is continuously reconciled.
* Explain a Pod as the smallest deployable/schedulable unit of one or more tightly coupled containers, and when NOT to co-locate.
* Explain a Deployment as a Pod template plus a desired replica count with controller-managed replacement.
* Explain a Service as stable discovery for a changing set of Pods selected by labels.
* Separate non-sensitive runtime configuration (ConfigMap) from the immutable image, and explain why that preserves the verified digest.
* Classify sensitive values into a Secret, and explain why Base64 is encoding, not encryption, and why a Secret is not automatically a vault.
* Explain why a ConfigMap/Secret change does not mutate an already-running process environment.
* Diagnose a partial AI outage where `/health` returns 200 but one Pod uses an invalid rotated key, and order a safe rollback.
* Keep Deployment selector, Pod template labels, and Service selector consistent.
* Answer beginner, intermediate, and senior Kubernetes interview questions in English.

The engineering artifact is a Kubernetes manifest and a validation README, not application code.

---

# Why This Matters

Day25 turned one CI-verified immutable image into a safely reachable, observable, reversible
production service. But that single-host blue-green runbook still depended on an operator or a
deployment script to start, verify, switch, observe, drain, and roll back. Nobody continuously
owned the running state after the script finished.

Day26's central shift:

```text
Script     = execute an action once
Kubernetes = continuously maintain a declared state

Desired State: three replicas
Actual State:  two replicas (one host failed)
Controller:    create a replacement until the states converge
```

Why a backend engineer must care:

```text
Availability   -> declared replicas are continuously reconciled, not manually restarted.
Discovery      -> a Service gives a stable name/VIP even as Pod IPs change.
Configuration  -> ConfigMap/Secret keep runtime config out of the immutable image digest.
Security       -> a Secret is a control boundary, not automatic encryption or least privilege.
Correctness    -> reconciliation enforces the declared state, NOT business correctness.
Roadmap        -> Day27 adds Ingress, Autoscaling, Rolling Update, StatefulSet, and Helm on top.
```

The most important production lesson: reconciliation improves recovery but is eventual, not magic.
A wrong desired state is also enforced repeatedly — automation can amplify a bad configuration.

---

# Roadmap Position

Knowledge continuity chain (v3.2):

```text
Previous Knowledge (Day24-25)
        |
        v
Current Concept (Day26: declare desired runtime state; controllers continuously reconcile actual state)
        |
        v
Future Production Usage (Day27 Kubernetes workloads; Day28 Production AI Backend)
```

Where Day26 sits:

```text
Docker image (Day23) -> Docker Compose one-host system (Day24)
-> safe deployment state transition (Day25)
-> Kubernetes desired state & reconciliation (Day26)
-> Kubernetes workloads: Ingress/Autoscaling/Rolling Update/StatefulSet/Helm (Day27)
-> Production AI Backend architecture (Day28)
```

Direct prerequisites reused:

```text
Day23 -> Container is a replaceable process; image is an immutable artifact identity.
Day24 -> Runtime configuration lives outside the immutable image; started != ready.
Day25 -> Deployment is a serialized, observable, reversible state transition; stable entry + replaceable backend.
Day26 -> Declare the desired runtime state; controllers reconcile the actual state continuously.
```

Future connection only (Day27): Ingress, Autoscaling, Rolling Update, StatefulSet, and Helm build
on Pod, Deployment, Service, ConfigMap, and Secret. Do not teach them here as completed Day26 scope.

---

# Lesson Map

```text
One-time command vs desired state (reconciliation)
  -> Pod (smallest deployable unit; one or more tightly coupled containers)
  -> Deployment (Pod template + replica count; controller replacement, not scheduling)
  -> Service (stable discovery for changing Pods via labels)
  -> ConfigMap (non-sensitive runtime config out of the image)
  -> Secret (sensitive values; Base64 != encryption; not an automatic vault)
  -> Integrated failure & rollback (health 200 != business success)
  -> Final mental model (declare -> observe -> reconcile -> verify -> rollback)
```

---

# Core Mental Model

```text
Declarative Specification
-> Kubernetes observes Actual State
-> Controllers reconcile the difference
-> Deployment maintains replaceable Pods
-> Service provides stable discovery across changing Pod IPs
-> ConfigMap supplies non-sensitive runtime configuration
-> Secret supplies controlled sensitive values
-> verification and observability prove business behavior
-> rollback restores a known-good desired state
```

You declare *what* should be true. Kubernetes continuously compares actual to desired and acts to
close the gap. It maintains the declared state; it does not guarantee the declared state is correct.

---

# Main Concepts

## Concept 1: Desired State vs a One-time Command

Tech Lead Question:

Day25 deployed three FastAPI instances with a script. One host fails after the script has already
finished. Do you want to preserve the one-time command that started three containers, or declare
that three available replicas must continue to exist?

Student Thinking:

A one-time command runs and ends. If an instance stops later, someone has to notice and restart it,
and manual steps get skipped.

Student Answer:

> "我希望保存必须持续存在三个可用副本的期望状态，启动三个容器的一次性命令执行以后，之后任何实例的关闭，都需要人工去启动，而人工就会带来遗漏。可能会因此影响业务服务"

Tech Lead Review:

Correct instinct. The durable distinction is ownership of the count over time:

```text
One-time command:
execute action -> create three instances -> command ends -> nobody continues to own the count

Desired state:
declare three replicas -> observe actual state -> detect drift -> create a replacement
```

```text
Script     = execute an action once
Kubernetes = continuously maintain declared state
```

Two honest limits: Kubernetes does not resurrect the *identity* of the vanished instance — it
creates a replacement that restores the count. And reconciliation is eventual, not instantaneous;
a wrong desired state is enforced just as reliably as a right one.

Engineering Thinking:

Reconciliation moves operations from "run an action" to "declare an invariant and let a controller
maintain it." That reduces manual omission but adds control-plane and operational complexity.

Production Example:

A node dies at 03:00. With a script, three replicas silently become two until a human notices. With
a Deployment, the controller observes the drift and schedules a replacement Pod automatically.

Framework Connection:

This is the Kubernetes control loop: `observe -> diff -> act`, applied to every object kind in the
rest of the lesson.

Exercise:

State the difference between "start three containers" and "keep three replicas available."

## Concept 2: Pod — the Deployment and Scheduling Unit

Tech Lead Question:

One FastAPI container and one tightly coupled logging sidecar must be co-located, share a network,
optionally share a volume, and be created and replaced together. What is the right unit?

Student Thinking:

They belong together and must live and die together, so they should be one runtime unit rather than
two separately operated instances.

Student Answer:

> "组合成一个共同调度、共同生命周期的运行单元，因为要一起创建与一起销毁，独立的部署实例，则会加入人工操作，带来误操作，遗漏操作。"

Tech Lead Review:

Right unit, but one correction. The Pod boundary is not "avoid manual operation" — separate
Kubernetes objects can also be fully automated. The real boundary is tight runtime coupling.

```text
Pod = Kubernetes' smallest deployable and schedulable unit
Pod = one or more tightly coupled containers
Pod != container
```

Containers in one Pod:

```text
- are scheduled to the same Node;
- share the Pod network namespace and Pod IP;
- can communicate through localhost;
- can mount shared volumes;
- share the Pod's replacement/lifecycle boundary;
- remain separate processes; individual containers may restart independently.
```

Reverse decision rule:

```text
Needs independent scaling, release, ownership, or failure isolation
-> should normally be a separate workload/Pod
```

FastAPI + a tightly coupled sidecar can share a Pod. FastAPI + PostgreSQL should NOT share a Pod
merely because the API uses the database — their state, scaling, and lifecycle boundaries differ.

Engineering Thinking:

Co-locate only what must share fate, network, and volume. Everything with an independent lifecycle
becomes its own workload.

Production Example:

A log-shipping sidecar reads the API's log volume over `emptyDir` and shares the Pod IP. If the Pod
is rescheduled, both move together; but the sidecar process can crash and restart without discarding
the API container.

Framework Connection:

Docker (Day23) gave one isolated container process; Kubernetes wraps one or more such processes into
a Pod as the scheduling unit.

Exercise:

Decide whether FastAPI and a tightly coupled logging sidecar belong in one Pod, and justify it by
coupling — not by automation.

## Concept 3: Deployment — Maintain Replaceable Pod Replicas

Tech Lead Question:

You need three identical FastAPI replicas. Do you write three independent Pod manifests, or one Pod
template with `replicas: 3`?

Student Thinking:

Three hand-written Pods are three independent objects; if one disappears, nothing recreates it.

Student Answer:

> "我选择B，最重要的生产原因是独立对象，如果消失，就没法自动化重建"

Tech Lead Review:

Correct, and for the right reason: a Deployment owns the count and template, so it recreates missing
replicas.

```text
Deployment = Pod template + desired replica count + controller-managed lifecycle
```

Conceptual ownership chain (ReplicaSet is implementation context, not a new Day26 topic):

```text
Deployment -> ReplicaSet -> Pods -> Containers
```

Production behavior:

```text
Pod disappears
-> actual count becomes 2
-> desired count remains 3
-> a new replacement Pod is created
```

Three honest limits:

```text
- Deployment maintains count and template, not the identity of the old Pod
  (new name, new IP, possibly a new Node).
- Deployment does NOT schedule Pods; the Kubernetes scheduler chooses the Node.
- replicas: 3 != three business-ready replicas
  (a bad template is replicated three times; local ephemeral Pod data is not recovered).
```

Rolling update strategy belongs to Day27.

Engineering Thinking:

Treat application Pods as replaceable cattle behind a template and a count. Correctness still depends
on the template being good.

Production Example:

A memory leak crashes one replica. The Deployment replaces it, restoring three — but if the leak is
in the template, all three eventually crash-loop. Reconciliation restores count, not correctness.

Framework Connection:

This is the Day25 "replaceable backend" idea made continuous: instead of an operator restarting
containers, a controller maintains the declared replica count.

Exercise:

Choose three hand-written Pod objects vs one Deployment template with `replicas: 3`, and explain the
production consequence when a Pod disappears.

## Concept 4: Service — Stable Access to Changing Pods

Tech Lead Question:

A replacement Pod got a new IP, but callers still hold the vanished Pod's old IP. How do callers keep
reaching the application?

Student Thinking:

Callers should target something stable, not a Pod IP that changes on every replacement.

Student Answer:

> "访问一个不会随 Pod 替换而改变的稳定入口，因为deployment对pod进行替换以后，pod的IP发生了变化。再次调用就会失败"

Tech Lead Review:

Exactly. The Service is the stable front for a changing set of Pods.

```text
Deployment = keep the desired Pod count
Service    = provide stable network access to the current matching Pods
Pod        = replaceable runtime instance with an ephemeral identity/IP
```

Flow:

```text
Cluster caller
-> stable Service DNS / virtual IP
-> current Pods selected by labels
```

The Service selector must match the Pod labels. In class we used `port: 80` for the Service-facing
port and `targetPort: http` for the named FastAPI container port 8000.

Critical limitation:

```text
Pod Running
!= Service has matching endpoints
!= business request succeeds
```

A Service does not create Pods, repair application logic, or make local Pod data durable. This is the
cluster-internal version of Day25's stable-entry principle. Public Ingress is Day27, not here.

Engineering Thinking:

Decouple identity (stable Service name) from instances (ephemeral Pods). Callers bind to the name;
the endpoint set changes underneath.

Production Example:

During a replacement, `rag-api` (the Service name) keeps resolving while individual Pod IPs churn.
Callers never track Pod IPs.

Framework Connection:

Day24 Compose service DNS resolved to a container; a Kubernetes Service resolves to a label-selected,
continuously-updated set of Pod endpoints.

Exercise:

Diagnose why callers fail after a replacement Pod gets a new IP, then add a Service with a label
selector that fixes it.

## Concept 5: ConfigMap — Separate Non-sensitive Runtime Configuration

Tech Lead Question:

Only `LOG_LEVEL` and `MODEL_NAME` change; code and dependencies do not. Do you rebuild the image or
externalize the configuration?

Student Thinking:

Rebuilding the whole image just to change a couple of values wastes build resources.

Student Answer:

> "非敏感运行配置从镜像中分离出来，因为其它的应用代码与依赖都没有变化，不需要每次修改一小部分，就进行重建镜像消耗资源"

Tech Lead Review:

Reasonable, but the resource argument is the weaker one. The stronger reason is artifact integrity.

```text
Code/dependency change
-> new image -> new digest -> new build/test/scan/approval

Runtime configuration change
-> external configuration -> same verified image digest
```

```text
Image     = immutable code, dependencies, and runtime base
ConfigMap = mutable non-sensitive runtime configuration
```

Typical values: `MODEL_NAME`, `LOG_LEVEL`, feature flags, non-sensitive service addresses, timeouts.

Lifecycle boundary (important):

```text
ConfigMap object updated
!= existing process environment changed

Configuration stored
!= configuration delivered
!= application behavior changed
```

Environment-variable injection is read at container start, so existing Pods usually need replacement
to consume new values. A mounted ConfigMap file may update later, but the app must actually reload it.

Engineering Thinking:

One verified digest serves many environments through external configuration — but configuration is
now a first-class artifact needing review, versioning, observation, and rollback.

Production Example:

Flipping `LOG_LEVEL` from `INFO` to `DEBUG` via ConfigMap changes nothing until the Pods that read it
at startup are replaced. Storing the value is not delivering it.

Framework Connection:

This continues Day24's "runtime configuration lives outside the image," now as a named cluster object
that many Pods reference.

Exercise:

Decide whether `MODEL_NAME` and `LOG_LEVEL` require a new image or a ConfigMap, and explain the digest
consequence.

## Concept 6: Secret — Sensitive Values Are Not Ordinary Configuration

Tech Lead Question:

Now add `OPENAI_API_KEY` and `DATABASE_PASSWORD`. Same as a ConfigMap, or something else?

Student Thinking:

These are credentials. Even Base64 in a ConfigMap can be read back, so they need a dedicated object.

Student Answer:

> "我选择使用专门的 Secret 对象，因为就算经过编码ConfigMap存的是非重要的配置，通过base64解密一样可以解析出来"

Tech Lead Review:

Right choice, one terminology fix: Base64 is encoding, not decryption.

```text
Base64 = encoding/decoding
Base64 != encryption/decryption
```

```text
ConfigMap = non-sensitive runtime configuration
Secret    = sensitive data requiring controlled access
```

A Kubernetes Secret is NOT automatically a complete vault. Real protection is composed:

```text
Secret object
+ encryption at rest for etcd
+ least-privilege RBAC
+ namespace/workload isolation
+ selective mounting
+ audit and rotation
+ external Secret Manager when appropriate
```

Secret `data` values are commonly Base64-encoded, not encrypted. A manifest containing a real secret
is unsafe to commit whether it uses `data` or `stringData`. Use safe placeholders in the repo and
inject real values out of band.

Least privilege is selective: only the API container needs the OpenAI/database credentials; the
logging sidecar must not receive them. The Secret object does not enforce that by itself — RBAC and
workload references must be designed.

Secret environment-variable lifecycle:

```text
Secret updated
!= existing process environment updated

old Pod -> old credential
new Pod -> new credential
```

Engineering Thinking:

A Secret classifies and gates sensitive data; the surrounding cluster and operational controls make
it actually safe. Rotation needs a compatibility window, controlled Pod replacement, verification,
and only then revocation of the old credential.

Production Example:

Rotating `OPENAI_API_KEY` updates the Secret, but running Pods keep the old env value until replaced.
Rotation without a compatibility window and verified replacement is how outages start.

Framework Connection:

FastAPI reads the credential from the environment at startup; the sidecar shares the Pod but must not
reference the Secret.

Exercise:

Classify `OPENAI_API_KEY` and `DATABASE_PASSWORD` as Secret values and explain why Base64 is not
protection.

## Concept 7: Integrated Production Failure and Rollback

Tech Lead Question:

Three Pods use a valid old key. A rotation stores an invalid new key. One Pod is later replaced and
reads the invalid key. `/health` returns 200 (it does not call the provider), but the Service sends
~1/3 of AI requests to the faulty Pod, which returns upstream `401`. How do you roll back without
turning a partial outage into a full one?

Student Thinking:

Health 200 does not prove business success. Restore the good key first, then replace only the faulty
Pod — and do not touch the two healthy Pods still holding the correct env value.

Student Answer:

> "一个pod故障被替换为新的pod，这个时候新pod读取的是新key，虽然health状态是200，但是不代表能正常处理业务，包含业务指标、日志、错误率等不知道是否正常。发生故障以后，按照先将key替换为旧的key，再将新的pod移除，由deployment重新启动另外一个pod使用恢复的key。如果在这个过程中删除另外正常pod会直接导致业务服务崩溃"

Tech Lead Review:

The rollback order is correct. Production-complete order derived in review:

```text
freeze further rotation and destructive actions
-> identify the faulty/new-secret Pod from 401s, logs, and metrics
-> restore the previous known-good Secret
-> verify the Secret object was restored
-> remove ONLY the faulty Pod
-> Deployment creates a replacement
-> run a real AI smoke test
-> observe 401 rate, business errors, latency, and logs
-> record the rollback and known final state
```

Why the two healthy old Pods must remain:

```text
delete healthy old Pods while the wrong Secret is current
-> all replacements read the wrong key
-> partial outage becomes full outage
```

Final production lesson:

```text
Health check passed != business succeeded
Automatic reconciliation != automatic business correctness

Correct desired state -> automation restores service
Wrong desired state   -> automation can amplify failure
```

Engineering Thinking:

Reconciliation is a force multiplier in both directions. During an incident, control what the
"desired state" is before letting the controller replace anything.

Production Example:

This is a real partial-outage signature: healthy liveness, high provider-error rate on a fraction of
traffic. The fix is to correct the desired state (Secret) first, then let controlled replacement heal.

Framework Connection:

Same shape as Day25 rollback (restore known-good, replace only the faulty unit, verify, observe), now
expressed through Kubernetes objects.

Exercise:

Order a rollback that preserves two healthy old Pods and replaces only the faulty Pod after restoring
the known-good Secret.

---

# Common Misconceptions

## Mental Model Evolution (Day25 -> Day26)

```text
Initial: "A safe deployment script that starts three verified replicas is enough."
Reasoning: Day25 made the production state transition serialized, observed, and reversible.
Correction: The script ends and stops owning the count; a later host failure is not reconciled.
Final: Kubernetes declares the desired runtime state and continuously reconciles the actual state —
       maintaining replaceable Pods, stable discovery, externalized config/secrets — while engineers
       remain responsible for declaring, securing, observing, and validating the CORRECT state.
```

## Misconception list

```text
Separate Pods imply manual operation
❌ Splitting into separate runtime units necessarily adds manual steps and omissions.
✅ Separate Kubernetes objects can also be controller-managed; the Pod boundary is tight coupling,
   co-location, shared network/volume, and lifecycle — not whether automation exists.
```

```text
Deployment schedules Pods
❌ The Deployment places Pods on Nodes.
✅ Deployment maintains a template and replica count; the scheduler selects Nodes. A Pod can exist
   without a Deployment.
```

```text
Pod means several containers
❌ A Pod must contain multiple containers.
✅ A Pod contains one or more containers; a single-container Pod is normal.
```

```text
Shared lifecycle means containers cannot restart separately
❌ Containers in a Pod must restart together.
✅ They share the Pod scheduling/network/replacement boundary, but individual container processes
   can restart independently.
```

```text
Avoid rebuild mainly to save resources
❌ The main reason to externalize config is saving build resources.
✅ The stronger reason is preserving the verified immutable artifact identity; a rebuild creates a
   new digest requiring new verification.
```

```text
Base64 is encryption
❌ A Base64-encoded Secret value is encrypted.
✅ Base64 is encoding; anyone with the content can decode it. Encryption at rest is separate.
```

```text
Secret automatically provides least privilege
❌ Using a Secret means access is already least-privilege.
✅ Least privilege needs RBAC, selective references/mounts, storage encryption, audit, and rotation.
```

```text
Health 200 proves deployment success
❌ A 200 from /health proves the deployment works.
✅ Readiness/liveness are limited evidence; business smoke tests, provider errors, logs, latency, and
   business metrics must also be observed.
```

```text
Kubernetes automation always improves the outcome
❌ Reconciliation always makes things better.
✅ Reconciliation enforces the desired state, not business correctness; a bad desired state can be
   automated and amplified across replicas.
```

---

# Engineering Trade-offs

```text
One-time script vs continuous reconciliation
+ Script: simple, explicit, easy to read.
- Script: does not repair drift after it exits.
+ Reconciliation: continuously restores declared state.
- Reconciliation: adds control-plane and operational complexity, and enforces bad state too.
```

```text
Single-container Pod vs multi-container Pod
+ Multi-container: tight collaboration, shared network/volume, shared fate.
- Multi-container: couples scheduling, scaling, and replacement boundaries.
Rule: co-locate only what must share fate; give independent lifecycles their own workload.
```

```text
Hand-written Pods vs Deployment
+ Direct Pods: simple teaching objects.
- Direct Pods: no automatic replacement.
+ Deployment: replica recovery from a template.
- Deployment: treats Pods as replaceable and will replicate a bad template.
```

```text
Direct Pod IP vs Service
+ Direct IP: simplest possible call.
- Direct IP: breaks on every replacement.
+ Service: stable discovery/routing abstraction.
- Service: depends on correct labels/selectors and matching endpoints.
```

```text
Image-baked config vs ConfigMap
+ Baked: explicit per artifact, fully reproducible.
- Baked: any change forces rebuild/reverification (new digest).
+ ConfigMap: one digest, many environments.
- ConfigMap: introduces drift and rollout concerns; storing != delivering.
```

```text
Secret object vs full secret management
+ Secret: a sensitive-data control boundary and reference mechanism.
- Secret: not automatically encrypted at rest or least-privileged.
Strong security = Secret + RBAC + encryption at rest + isolation + audit + rotation.
```

```text
Broad health check vs narrow health check
+ Broad: can catch dependency failures (e.g. provider auth).
- Broad: adds cost and couples liveness to external failures.
+ Narrow: cheap and stable.
- Narrow: cannot prove end-to-end business success.
```

```text
Manual operations vs automated reconciliation
+ Automation: reduces manual omission.
- Automation: can rapidly amplify a bad desired state across all replicas.
```

---

# Hands-on Exercises

The engineering artifact is a Kubernetes manifest and a validation README (see
`examples/kubernetes/`).

## Exercise 1: One-time Startup vs Desired State

Question: Choose between a one-time command that starts three containers and a declared desired state
of three continuously maintained replicas.

Think First: What happens at 03:00 when a host fails under each option?

Expected Output: Declare desired state; a controller reconciles the missing replica. A script does
not own the count after it exits.

Explanation: `Script = execute once; Kubernetes = maintain declared state`.

Follow-up Question: Does reconciliation restore the *identity* of the failed instance?

## Exercise 2: Pod Boundary

Question: Decide whether FastAPI and a tightly coupled logging sidecar belong in one Pod.

Think First: Do they share fate, network, and a volume — or independent scaling and lifecycle?

Expected Output: Same Pod, justified by tight coupling and shared network/volume — not by "avoiding
manual operation."

Follow-up Question: Why should FastAPI and PostgreSQL NOT share a Pod?

## Exercise 3: Three Pods vs One Deployment

Question: Choose three hand-written Pod objects or one Deployment template with `replicas: 3`.

Expected Output: One Deployment; it recreates a missing replica, whereas independent Pods are not
recreated.

Follow-up Question: Does `replicas: 3` guarantee three business-ready replicas?

## Exercise 4: Diagnose the New-IP Failure

Question: Callers fail after a replacement Pod receives a new IP. Why?

Expected Output: Callers targeted an ephemeral Pod IP instead of a stable Service; the Pod was
replaced with a new IP.

Follow-up Question: What must match between the Service and the Pods?

## Exercise 5: Add a Service with Label Selection

Question: Give the Pods stable access.

Expected Output: A Service whose `selector` matches the Pod labels (`app: rag-api`), `port: 80`,
`targetPort: http`.

Follow-up Question: Does a running Pod guarantee the Service has matching endpoints?

## Exercise 6: ConfigMap or New Image?

Question: `MODEL_NAME` and `LOG_LEVEL` change; code does not. New image or ConfigMap?

Expected Output: ConfigMap — the verified digest is unchanged; a rebuild would create a new digest
needing re-verification.

Follow-up Question: After you edit the ConfigMap, why might running Pods still show old behavior?

## Exercise 7: Classify Secrets

Question: Classify `OPENAI_API_KEY` and `DATABASE_PASSWORD` and explain why Base64 is insufficient.

Expected Output: Secret values; Base64 is encoding, decodable by anyone with the content. A committed
manifest with a real value is unsafe.

Follow-up Question: What else, beyond a Secret object, is required for least privilege?

## Exercise 8: Partial AI Outage with Health 200

Question: Health returns 200 but one Pod uses an invalid rotated key and returns 401 on ~1/3 of AI
traffic. Diagnose it.

Expected Output: Liveness is not business success; confirm via 401 rate, logs, and business metrics;
identify the new-secret Pod.

Follow-up Question: Which signal, not `/health`, reveals the failure?

## Exercise 9: Order the Rollback

Question: Roll back while preserving two healthy old Pods and replacing only the faulty Pod.

Expected Output: Freeze rotation -> restore known-good Secret -> verify restoration -> delete only the
faulty Pod -> let the Deployment replace it -> AI smoke test -> observe -> record.

Follow-up Question: What happens if you delete the two healthy Pods while the wrong Secret is current?

## Exercise 10: English Interview

Question: Answer the Beginner, Intermediate, and Senior questions in the English Interview section.

Expected Output: Correct technical content with the specific corrections (Deployment does not
schedule; Base64 is not encryption; health 200 is not business success).

## Exercise 11: Final Mental Model Synthesis

Question: Produce a Chinese Mental Model synthesis of Pod, Deployment, Service, ConfigMap, Secret,
and the health-vs-business distinction.

Expected Output: See the student's synthesis in Mental Model Summary, with the four narrow
corrections applied.

---

# Relevant Framework Connections

## Kubernetes

The whole lesson is a Kubernetes foundation: declarative objects, a reconciliation control loop, and
five core kinds — Pod, Deployment, Service, ConfigMap, Secret. Watch for: selector/label agreement,
`started != ready`, and config/secret env updates not mutating running processes.

## Docker / Docker Compose

Day23 image/container identity and Day24 service/runtime configuration carry forward:

```text
- container = process isolation unit (Day23);
- Pod = Kubernetes scheduling/deployment unit around one or more containers;
- runtime configuration stays outside the immutable image (Day24);
- Compose coordinates a declared multi-service system on ONE host;
- Kubernetes continuously reconciles declared state across a cluster.
```

## Day25 Deployment / Nginx

Same stable-entry, replaceable-backend principle:

```text
Day25: client -> DNS/Nginx -> replaceable backend
Day26: cluster caller -> Service -> replaceable Pod
```

Public Ingress behavior is NOT expanded here; Ingress belongs to Day27.

## FastAPI

FastAPI is the application container inside the Pod, exposed internally on named port `http` / 8000.
Its local `/health` endpoint is intentionally shown as insufficient evidence of successful provider
calls.

No Playwright connection is used in this lesson; it is not forced in.

---

# AI Backend Connections

```text
- A RAG/FastAPI service runs as three replaceable replicas.
- MODEL_NAME and LOG_LEVEL are non-sensitive runtime configuration in a ConfigMap.
- OPENAI_API_KEY and DATABASE_PASSWORD are sensitive and referenced through a Secret.
- The logging sidecar shares the Pod/volume but must not receive AI/database credentials.
- A provider credential can fail while /health stays 200.
- Production success needs AI business smoke tests plus provider 401 rate, business error rate,
  logs, latency, and relevant cost/quality indicators.
- Secret rotation must preserve old/new compatibility until replacement Pods are verified.
- Reconciliation can amplify an invalid credential or configuration across replicas.
- A verified application image digest stays separate from runtime model selection and credentials.
```

---

# English Interview

Key vocabulary: desired state, reconciliation, control loop, Pod, sidecar, Deployment, ReplicaSet,
replica, Service, selector, label, endpoint, ConfigMap, Secret, Base64 encoding, least privilege,
RBAC, rotation, readiness, liveness, smoke test.

## Beginner

Question:

What is a Pod in Kubernetes, and why is a Pod not the same as a container?

Actual student attempt (preserved):

> "pod is a sevral compose of container,it depend on deployment schedual.it is the smallest deployable unit.one or more containers share common lifecycle/network in pod."

Technical correction:

```text
Correct  : smallest deployable unit; one or more containers; shared network/lifecycle boundary.
Incorrect: a Pod does not depend on a Deployment, and a Deployment does not schedule it to a Node.
```

English corrections:

```text
sevral      -> several
compose of  -> consists of / is composed of
container   -> containers
schedual    -> scheduled / schedule
depend      -> depends
```

Strong Answer:

> A Pod is the smallest deployable unit in Kubernetes. It contains one or more tightly coupled
> containers that share the same network namespace and lifecycle. A Deployment can manage Pod
> replicas, while the Kubernetes scheduler decides which node runs each Pod.

## Intermediate

Question:

A Pod fails and its replacement gets a new IP address. How do a Deployment and a Service work
together to keep the application available?

Actual student attempt (preserved):

> "the deployment offer replica recovery pod,service offer stable network access"

Technical review: correct distinction but incomplete mechanism. Deployment maintains desired
replicas; Service selects current Pods by labels and keeps a stable address.

Strong Answer:

> The Deployment maintains the desired number of replicas. If a Pod fails, it creates a replacement
> Pod. The Service selects the current Pods by their labels and provides a stable DNS name and
> virtual IP, so clients do not need to track changing Pod IP addresses.

## Senior

Question:

After a Secret rotation, one replacement Pod reads an invalid API key. Its health endpoint still
returns 200, but AI requests routed to that Pod return 401. How would you diagnose and roll back this
failure without turning the partial outage into a full outage?

Actual student attempt (preserved):

> "the result of return 200 is not meaning logs,bussiness metric,error rate,latency process health.i would recovry old stable secrets,and then delete pod which goes wrong,deployment replace a new replica pod.the new pod recive old secrets."

Technical review: rollback direction correct. Add freeze, verify Secret restoration, remove only the
faulty Pod, run a real business smoke test, and observe recovery.

English corrections:

```text
is not meaning -> does not mean / does not prove
bussiness      -> business
metric         -> metrics
recovry        -> restore / recover
goes wrong     -> is faulty / is using the invalid key
recive         -> receive
```

Strong Answer:

> First, I would freeze further Secret rotation and avoid deleting the two healthy Pods. A 200
> response from the health endpoint does not prove that real AI requests are working, so I would
> confirm the failure through 401 errors, logs, and business metrics. Then I would restore the
> previous known-good Secret and verify that the Secret object has been updated. I would delete only
> the faulty Pod, allow the Deployment to create a replacement, and verify that the new Pod receives
> the restored credential. Finally, I would run a real AI smoke test and observe the error rate and
> latency before completing the rollback.

---

# Mental Model Summary

```text
Desired State    = what should be true (declared)
Reconciliation   = observe -> diff -> act, continuously
Pod              = smallest deployable unit; one or more tightly coupled containers
Deployment       = Pod template + replica count (recovery, not scheduling)
Service          = stable discovery for label-selected, changing Pods
ConfigMap        = non-sensitive runtime config outside the image
Secret           = sensitive values; Base64 = encoding, not encryption
Health 200       != business success
Reconciliation   != business correctness
Rollback         = restore a known-good desired state, then replace only the faulty unit
```

Preserve the student's actual final synthesis:

> "pod是多个容器共同组成的kubernetes的最小运行单元，里面的一个或多个container使用的是同一个网络同一个生命周期，可以一同调度到节点。deployment负责提供pod模版的副本，始终保持期望的pod运行数量。service给提供一个统一的访问入口，不会在new pod因为IP的改变而无法继续访问到服务。configmap保存非敏感的配置，secret保存密钥及密码等比较敏感的配置，并且只是提供最小权限，以及限定范围。健康检查通过，还需要看错误率、延迟、日志、业务指标等是否与期望的业务状态相符合"

Narrow corrections to that synthesis:

```text
- A Pod contains one or more containers, not necessarily multiple.
- Pod containers share scheduling/networking and one Pod lifecycle, but individual container
  processes can restart independently.
- Deployment maintains replicas from a Pod template; it does not perform scheduling itself.
- Secret classifies sensitive data, but least privilege and scope require selective references,
  RBAC, encryption-at-rest configuration, and operational controls.
```

Final durable model:

```text
Declarative Specification
-> Kubernetes observes Actual State
-> Controllers reconcile differences
-> Deployment maintains replaceable Pods
-> Service provides stable discovery across changing Pod IPs
-> ConfigMap supplies non-sensitive runtime configuration
-> Secret supplies controlled sensitive values
-> verification and observability prove business behavior
-> rollback restores a known-good desired state
```

Kubernetes maintains declared state; engineers remain responsible for declaring, securing, observing,
and validating the correct state.

---

# Today's Takeaway

```text
Most important mental model:
Declare desired state; controllers continuously reconcile actual state. Script = act once;
Kubernetes = maintain the declaration.

Most important production risk:
Reconciliation enforces the desired state, not business correctness. Health 200 != business success,
and a wrong desired state (e.g. a bad rotated Secret) is amplified across replicas.

Most important framework/AI connection:
A RAG/FastAPI Deployment of replaceable Pods behind a stable Service, with MODEL_NAME/LOG_LEVEL in a
ConfigMap and OPENAI_API_KEY/DATABASE_PASSWORD in a Secret referenced only by the API container.

Most important interview answer:
A Deployment maintains replicas from a template; the scheduler places Pods; a Service provides stable
label-based discovery; Base64 is encoding, not encryption.
```

Scope honesty: multi-node scheduling internals, autoscaling, rolling update, StatefulSet, Helm, and
public Ingress were NOT taught or validated in Day26. No Kubernetes runtime (`kubectl apply`, Pod
Ready, Service routing, rollout) was executed; see `examples/kubernetes/README.md`.

---

# Before Next Lesson Checklist

- [ ] Can I explain desired state vs a one-time command in plain English?
- [ ] Can I explain why a Pod is not the same as a container, and when NOT to co-locate?
- [ ] Can I explain that a Deployment maintains replicas but does not schedule Pods?
- [ ] Can I explain how a Service keeps access stable across changing Pod IPs?
- [ ] Can I explain why a ConfigMap/Secret change does not mutate a running process environment?
- [ ] Can I explain why Base64 is not encryption and why a Secret is not an automatic vault?
- [ ] Can I diagnose a health-200-but-401 partial outage and order a safe rollback?
- [ ] Can I answer beginner, intermediate, and senior Kubernetes questions in English?
