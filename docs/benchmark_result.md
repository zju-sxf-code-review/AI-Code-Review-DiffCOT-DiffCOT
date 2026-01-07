# DiffCoT Benchmark

以下将对比本方法与官方指定数据集中的Bug检测结果。

## 1. 检测率性能对比

| 工具                  | 检测率 |
|-----------------------|--------------|
| Greptile              | 82%          |
| **DiffCoT(本方案)** | 76%   |
| Cursor                | 58%          |
| Copilot               | 54%          |
| CodeRabbit            | 44%          |
| Graphite              | 6%           |


## 2. 详细PR/Bug检测结果

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

