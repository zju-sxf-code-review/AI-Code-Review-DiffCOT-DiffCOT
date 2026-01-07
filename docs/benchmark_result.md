# DiffCoT Benchmark

以下将对比本方法与官方指定数据集中的Bug检测结果。

## 1. 检测率性能对比

| 工具                  | 检测率 |
|-----------------------|--------------|
| Greptile              | 82%          |
| **DiffCoT(本方案)** | 78%   |
| Cursor                | 58%          |
| Copilot               | 54%          |
| CodeRabbit            | 44%          |
| Graphite              | 6%           |


## 2. 详细PR/Bug检测结果

### SENTRY

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Enhanced Pagination Performance for High-Volume Audit Logs<br>Importing non-existent OptimizedCursorPaginator | High | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Optimize spans buffer insertion with eviction during insert<br>Negative offset cursor manipulation bypasses pagination boundaries | Critical | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Support upsampled error count with performance optimizations<br>sample_rate = 0.0 is falsy and skipped | Low | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| GitHub OAuth Security Enhancement<br>Null reference if github_authenticated_user state is missing | Critical | ✗| ✓ | ✗  | ✓ | ✗ | ✓ |
| Replays Self-Serve Bulk Delete System<br>Breaking changes in error response format | Critical | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Span Buffer Multiprocess Enhancement with Health Monitoring<br>Inconsistent metric tagging with 'shard' and 'shards' | Medium | ✓ | ✓| ✗  | ✗ | ✗ | ✓ |
| Implement cross-system issue synchronization<br>Shared mutable default in dataclass timestamp | Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Reorganize incident creation / issue occurrence logic<br>Using stale config variable instead of updated one | High | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Add ability to use queues to manage parallelism<br>Invalid queue.ShutDown exception handling | High | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Add hook for producing occurrences from the stateful detector<br>Incomplete implementation (only contains pass) | High | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **8/10** | **4/10** | **3/10** | **4/10** | **0/10** | **8/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/sentry/pulls](https://github.com/zju-sxf-code-review/sentry/pulls)


### CAL.COM

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Add Booking Migration functionality<br>SQL Injection vulnerability in raw SQL query | Critical | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| Update Prisma and fix Prisma Client caching issues<br>Missing await on async function call | Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Add missing permissions check for create_booking and get_booking_by_uid<br>Bypassing authentication via direct URL access | Critical | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ |
| Fix incorrect usage of `start` and `end` in event queries<br>Off-by-one error in date range calculation | Medium | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Update z-index for modals to fix layering issues<br>Incorrect z-index value causing UI rendering issues | Low | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| feat: add API endpoint for booking cancellation<br>Missing error handling for invalid booking IDs | High | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Fix timezone handling in booking calculations<br>Incorrect timezone conversion leading to wrong time displays | Medium | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ |
| Update booking form validation<br>Missing input validation for email field | Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Add booking reminder functionality<br>Memory leak due to unclosed database connections | High | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |
| Update dependency versions to fix security vulnerabilities<br>Using outdated library with known security issues | Critical | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **10/10** | **8/10** | **9/10** | **8/10** | **0/10** | **8/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/cal.com/pulls](https://github.com/zju-sxf-code-review/cal.com/pulls)

### Grafana

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Anonymous: Add configurable device limit<br>Race condition in CreateOrUpdateDevice method | High | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| AuthZService: improve authz caching<br>Cache entries without expiration causing permanent permission denials | High | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| Plugins: Chore: Renamed instrumentation middleware to metrics middleware<br>Undefined endpoint constants causing compilation errors | Critical | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Advanced Query Processing Architecture<br>Double interpolation risk | Critical | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Notification Rule Processing Engine<br>Missing key prop causing React rendering issues | Medium | ✓ | ✗ | ✓ | ✓ | ✗ | ✗ |
| Dual Storage Architecture<br>Incorrect metrics recording methods causing misleading performance tracking | Medium | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| Database Performance Optimizations<br>Incorrect error level logging | Low | ✓ | ✓ | ✓ | ✗ | ✓ | ✓ |
| Frontend Asset Optimization<br>Deadlock potential during concurrent annotation deletion operations | High | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Advanced SQL Analytics Framework<br>enableSqlExpressions function always returns false, disabling SQL functionality | Critical | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Unified Storage Performance Optimizations<br>Race condition in cache locking | High | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **8/10** | **5/10** | **5/10** | **7/10** | **3/10** | **8/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/grafana/pulls](https://github.com/zju-sxf-code-review/grafana/pulls)


### Keycloak

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Fixing Re-authentication with passkeys<br>ConditionalPasskeysEnabled() called without UserModel parameter | Medium | ✓ | ✗ | ✗ | ✗ | ✗ |✗ |
| Add caching support for IdentityProviderStorageProvider .getForLogin operations<br>Recursive caching call using session instead of delegate | Critical | ✓ | ✗ | ✗ | ✗ | ✗ |✓ |
| Add AuthzClientCryptoProvider for authorization client cryptographic operations<br>Returns wrong provider (default keystore instead of BouncyCastle) | High | ✓ | ✗ | ✓ | ✗ | ✗ | ✓|
| Add rolling-updates feature flag and compatibility framework<br>Incorrect method call for exit codes | Medium | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| Add Client resource type and scopes to authorization schema<br>Inconsistent feature flag bug causing orphaned permissions | High | ✗ | ✗ | ✗ | ✓ | ✗ | ✓ |
| Add Groups resource type and scopes to authorization schema<br>Incorrect permission check in canManage() method | High | ✓ | ✓ | ✓ | ✓ | ✗ | ✗|
| Add HTML sanitizer for translated message resources<br>Lithuanian translation files contain Italian text | Low | ✓ | ✓ | ✓ | ✓ | ✗ | ✓|
| Implement access token context encoding framework<br>Wrong parameter in null check (grantType vs. rawTokenId) | Critical | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Implement recovery key support for user storage providers<br>Unsafe raw List deserialization without type safety | Medium | ✓ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Fix concurrent group access to prevent NullPointerException<br>Missing null check causing NullPointerException | Critical | ✓ | ✓ | ✗ | ✓ | ✗ | ✓ |
| **Total Catches** | - | **8/10** | **4/10** | **5/10** | **6/10** | **0/10** | **7/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/keycloak/pulls](https://github.com/zju-sxf-code-review/keycloak/pulls)

### Discourse

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|-------------------------|
| Enhanced Pagination Performance for High-Volume Audit Logs<br>Importing non-existent OptimizedCursorPaginator | High | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| Optimize spans buffer insertion with eviction during insert<br>Negative offset cursor manipulation bypasses pagination boundaries | Critical | ✗ | ✗ | ✓ | ✓ | ✗ | ✓ |
| Support upsampled error count with performance optimizations<br>sample_rate = 0.0 is falsy and skipped | Low | ✓ | ✗ | ✗ | ✗ | ✗ | ✓ |
| GitHub OAuth Security Enhancement<br>Null reference if github_authenticated_user state is missing | Critical | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| Replays Self-Serve Bulk Delete System<br>Breaking changes in error response format | Critical | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ |
| Span Buffer Multiprocess Enhancement with Health Monitoring<br>Inconsistent metric tagging with 'shard' and 'shards' | Medium | ✓ | ✓ | ✗ | ✗ | ✗ | ✓ |
| Implement cross-system issue synchronization<br>Shared mutable default in dataclass timestamp | Medium | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ |
| Reorganize incident creation / issue occurrence logic<br>Using stale config variable instead of updated one | High | ✓ | ✗ | ✓ | ✗ | ✗ | ✓ |
| Add ability to use queues to manage parallelism<br>Invalid queue.ShutDown exception handling | High | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| Add hook for producing occurrences from the stateful detector<br>Incomplete implementation (only contains pass) | High | ✓ | ✗ | ✗ | ✓ | ✗ | ✓|
| **Total Catches** | - | **8/10** | **4/10** | **3/10** | **4/10** | **0/10** | **8/10** |

本项目测评结果：
[https://github.com/zju-sxf-code-review/discourse/pulls](https://github.com/zju-sxf-code-review/discourse/pulls)
