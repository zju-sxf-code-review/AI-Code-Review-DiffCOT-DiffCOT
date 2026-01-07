# DiffCoT Benchmark

以下将对比本方法与官方指定的**5种语言*10个案例的50案例数据集**中各个工具的Bug检测结果。
> 实验步骤：1)Fork 5个仓库; 2)正确填写并运行自动拉取pr脚本，50个PR即可保存至到仓库; 3)配置好（详见readme.md，注意填写正确的apikey和**权限足够**的github token）运行本项目diffCoT，点击Start Analysis，分析完毕后Comment on GitHub，并根据是否找出核心逻辑错误来评判正误。

## 1. 检测案例统计
| 工具                  | Critical 15  | High 17      |  Medium 11   | Low 7        |Total 50|
|-----------------------|--------------|--------------|--------------|--------------|-------|
| Greptile              | 11 |14 |10 | 6 | 41  |
| Copilot               | 8  |7  |7  | 4 | 26  |
| CodeRabbit            | 5 | 6  |6 | 5 | 22  |
| Cursor                | 9 |9 |7 | 4 | 29  |
| Graphite              | 1 |0  |1 | 1 | 3  |
| **DiffCoT(本方案)**   | 13 |14  |6 | 5 | 38 |

## 2. 检测率性能对比

| 工具                  | Critical 15  | High 17      | Medium 11    | Low 7        | Total 50 |
|-----------------------|--------------|--------------|--------------|--------------|----------|
| Greptile              | *73.33%*      | **82.35%**       | **90.91%**       | **85.71%**       | **82.00%**   |
| Copilot               | 53.33%       | 41.18%       | *63.64%*       | 57.14%       | 52.00%   |
| CodeRabbit            | 33.33%       | 35.29%       | 54.55%       | *71.43%*       | 44.00%   |
| Cursor                | 60.00%       | 52.94%       | 63.64%       | 57.14%       | 58.00%   |
| Graphite              | 6.67%        | 0.00%        | 9.09%        | 14.29%       | 6.00%    |
| **DiffCoT(本方案)**   | **86.67%**      | **82.35%**       | 54.55%       | *71.43%*       | *76.00%*   |

### 说明
- 难度:Critical/High/Medium/Low
- **加粗**表示最优性能，*斜体*表示次优性能
- 每列百分比 = (该工具在该类难度的数值 / 该类难度的总数) × 100%
- Critical 案例总数：15
- High 案例总数：17
- Medium 案例总数：11
- Low 案例总数：7
- Total 案例总数：50


## 3. 详细PR/Bug检测结果

### SENTRY

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Enhanced Pagination Performance for High-Volume Audit Logs | High | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Optimize spans buffer insertion with eviction during insert | Critical | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Support upsampled error count with performance optimizations| Low | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| GitHub OAuth Security Enhancement | Critical | ✗| ✓ | ✗  | ✓ | ✗ | ✓ |
| Replays Self-Serve Bulk Delete System | Critical | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Span Buffer Multiprocess Enhancement with Health Monitoring | Medium | ✓ | ✓| ✗  | ✗ | ✗ | ✓ |
| Implement cross-system issue synchronization | Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Reorganize incident creation / issue occurrence logic | High | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Add ability to use queues to manage parallelism| High | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Add hook for producing occurrences from the stateful detector| High | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **8/10** | **4/10** | **3/10** | **4/10** | **0/10** | **8/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/sentry/pulls](https://github.com/zju-sxf-code-review/sentry/pulls)


### CAL.COM

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Add Booking Migration functionality| Critical | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| Update Prisma and fix Prisma Client caching issues| Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Add missing permissions check for create_booking and get_booking_by_uid | Critical | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Fix incorrect usage of `start` and `end` in event queries| Medium | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Update z-index for modals to fix layering issues | Low | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| feat: add API endpoint for booking cancellation| High | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Fix timezone handling in booking calculations| Medium | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Update booking form validation| Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Add booking reminder functionality| High | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |
| Update dependency versions to fix security vulnerabilities| Critical | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **10/10** | **8/10** | **9/10** | **8/10** | **0/10** | **7/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/cal.com/pulls](https://github.com/zju-sxf-code-review/cal.com/pulls)

### Grafana

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Anonymous: Add configurable device limit | High | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| AuthZService: improve authz caching| High | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| Plugins: Chore: Renamed instrumentation middleware to metrics middleware | Critical | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Advanced Query Processing Architecture | Critical | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Notification Rule Processing Engine| Medium | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |
| Dual Storage Architecture | Medium | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Database Performance Optimizations | Low | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ |
| Frontend Asset Optimization| High | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Advanced SQL Analytics Framework| Critical | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Unified Storage Performance Optimizations| High | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **8/10** | **5/10** | **5/10** | **7/10** | **3/10** | **8/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/grafana/pulls](https://github.com/zju-sxf-code-review/grafana/pulls)


### Keycloak

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Fixing Re-authentication with passkeys | Medium | ✓ | ✗ | ✗ | ✗ | ✗ |✗ |
| Add caching support for IdentityProviderStorageProvider .getForLogin operations | Critical | ✓ | ✗ | ✗ | ✗ | ✗ |✓ |
| Add AuthzClientCryptoProvider for authorization client cryptographic operations | High | ✓ | ✗ | ✓ | ✗ | ✗ | ✓|
| Add rolling-updates feature flag and compatibility framework | Medium | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Add Client resource type and scopes to authorization schema| High | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| Add Groups resource type and scopes to authorization schema | High | ✓ | ✓ | ✓ | ✓ | ✗ | ✗|
| Add HTML sanitizer for translated message resources| Low | ✓ | ✓ | ✓ | ✓ | ✗ | ✓|
| Implement access token context encoding framework | Critical | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Implement recovery key support for user storage providers | Medium | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Fix concurrent group access to prevent NullPointerException| Critical | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **8/10** | **4/10** | **5/10** | **6/10** | **0/10** | **7/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/keycloak/pulls](https://github.com/zju-sxf-code-review/keycloak/pulls)

### Discourse

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Enhanced Pagination Performance for High-Volume Audit Logs| High | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Optimize spans buffer insertion with eviction during insert| Critical | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Support upsampled error count with performance optimizations| Low | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| GitHub OAuth Security Enhancement| Critical | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Replays Self-Serve Bulk Delete System | Critical | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Span Buffer Multiprocess Enhancement with Health Monitoring | Medium | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| Implement cross-system issue synchronization| Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Reorganize incident creation / issue occurrence logic| High | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Add ability to use queues to manage parallelism| High | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Add hook for producing occurrences from the stateful detector| High | ✓ | ✗ | ✗ | ✓ | ✗ | ✓|
| **Total Catches** | - | **8/10** | **4/10** | **3/10** | **4/10** | **0/10** | **8/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/discourse/pulls](https://github.com/zju-sxf-code-review/discourse/pulls)

## 结论
1. 本方案diffCoT在Critical任务上检测率达86%**位列第1**，High任务上达82%**并列第1**，在高难任务上展现出较强的竞争力，这可能得益于本方案的意图解析（同时含解析和扩展）、优化后的四大问题通用的逻辑排查Prompt库；
2. 而本方案在中难度表现欠佳（并列第4），低难度**并列第2**，中低难度表现一般，可能受制于规则库的体量以及静态分析工具的合理性使用，需要后续考虑如何更好地权衡；
3. 总体来说，对于高难任务，本方案或许能提供良好的解决思路。

