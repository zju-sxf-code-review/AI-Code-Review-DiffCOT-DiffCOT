# DiffCoT Benchmark

以下将对比本方法与官方指定的**5种语言*10个案例的50案例数据集**中各个工具的Bug检测结果。
> 实验步骤：1)Fork 5个仓库; 2)正确填写并运行自动拉取pr脚本，50个PR即可保存至到仓库; 3)配置好（详见readme.md，注意填写正确的apikey和**权限足够**的github token）运行本项目diffCoT，点击Start Analysis，分析完毕后Comment on GitHub，并根据是否找出核心逻辑错误来评判正误。
>> 判断标准:明确的**逐行PR评论**，指向有错误的代码并解释其影响，仅总结性的提及不算数。

## 1. 案例严重程度分布统计
| Library | Critical | High | Medium | Low| Total|
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SENTRY** | 2, 4, 5 | 1, 8, 9, 10 | 6, 7 | 3 | **10** |
| **CAL.COM** | 2, 4, 7 | 5, 8, 9 | 3, 6 | 1, 10 | **10** |
| **GRAFANA** | 3, 4, 9 | 1, 2, 8, 10 | 5, 6 | 7 | **10** |
| **KEYCLOAK** | 2, 8, 10 | 3, 5, 6 | 1, 4, 9 | 7 | **10** |
| **DISCOURSE**| 3, 4, 10 | 2, 8, 9 | 1, 6 | 5, 7 | **10** |
| **TOTAL** | **15** | **17** | **11** | **7** | **50** |

## 2. 所有工具在不同严重程度案例上的检测性能对比
### 基于检测个数
| 工具                  | Critical 15  | High 17      |  Medium 11   | Low 7        |Total 50|
|-----------------------|--------------|--------------|--------------|--------------|-------|
| Greptile              | 11 |14 |10 | 6 | 41  |
| Copilot               | 8  |7  |7  | 4 | 26  |
| CodeRabbit            | 5 | 6  |6 | 5 | 22  |
| Cursor                | 9 |9 |7 | 4 | 29  |
| Graphite              | 1 |0  |1 | 1 | 3  |
| **DiffCoT(本方案)**   | 13 |14  |6 | 5 | 38 |

### 基于监测率

| 工具                  | Critical 15  | High 17      | Medium 11    | Low 7        | Total 50 |
|-----------------------|--------------|--------------|--------------|--------------|----------|
| Greptile              | *73.33%*      | **82.35%**       | **90.91%**       | **85.71%**       | **82.00%**   |
| Copilot               | 53.33%       | 41.18%       | *63.64%*       | 57.14%       | 52.00%   |
| CodeRabbit            | 33.33%       | 35.29%       | 54.55%       | *71.43%*       | 44.00%   |
| Cursor                | 60.00%       | 52.94%       | 63.64%       | 57.14%       | 58.00%   |
| Graphite              | 6.67%        | 0.00%        | 9.09%        | 14.29%       | 6.00%    |
| **DiffCoT(本方案)**   | **86.67%**      | **82.35%**       | 54.55%       | *71.43%*       | *76.00%*   |

### 说明
- 严重程度:Critical/High/Medium/Low
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
|----------------------|----------|----------|---------|------------|--------|----------|---------|
| Enhanced Pagination Performance for High-Volume Audit Logs <br> Importing non-existent OptimizedCursorPaginator | High | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Optimize spans buffer insertion with eviction during insert<br>  Negative offset cursor manipulation bypasses pagination boundaries| Critical | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| Support upsampled error count with performance optimizations <br> sample_rate = 0.0 is falsy and skipped| Low | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| GitHub OAuth Security Enhancement <br> Null reference if github_authenticated_user state is missing| Critical | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| Replays Self-Serve Bulk Delete System <br> Breaking changes in error response format| Critical | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Span Buffer Multiprocess Enhancement with Health Monitoring <br> Inconsistent metric tagging with 'shard' and 'shards'| Medium | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| Implement cross-system issue synchronization <br> Shared mutable default in dataclass timestamp| Medium | ✅ | ✅  | ✅  | ✅ | ❌ | ✅ |
| Reorganize incident creation / issue occurrence logic <br> Using stale config variable instead of updated one| High | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Add ability to use queues to manage parallelism <br> Invalid queue.ShutDown exception handling| High | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| Add hook for producing occurrences from the stateful detector <br> Incomplete implementation (only contains pass)| High | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| **Total Catches** | - | **8/10** | **4/10** | **3/10** | **4/10** | **0/10** | **8/10** |


本项目在**SENTRY**10个案例上的测评结果：
[https://github.com/zju-sxf-code-review/sentry/pulls](https://github.com/zju-sxf-code-review/sentry/pulls)


### CAL.COM

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|---------|
| Async import of the appStore packages <br> Async callbacks in forEach creates unhandled promise rejections | Low | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| feat: 2fa backup codes <br> Backup codes not invalidated after use | Critical | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |
| fix: handle collective multiple host on destinationCalendar <br> Null reference error if array is empty | Medium | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| feat: convert InsightsBookingService to use Prisma.sql raw queries <br> Potential SQL injection risk in raw SQL query construction | Critical | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| Comprehensive workflow reminder management for booking lifecycle events <br> Missing database cleanup when immediateDelete is true | High | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Advanced date override handling and timezone compatibility improvements <br> Incorrect end time calculation using slotStartTime instead of slotEndTime | Medium | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |
| OAuth credential sync and app integration enhancements <br> Timing attack vulnerability using direct string comparison | Critical | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| SMS workflow reminder retry count tracking <br> OR condition causes deletion of all workflow reminders | High | ❌ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Add guest management functionality to existing bookings <br> Case sensitivity bypass in email blacklist | High | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| feat: add calendar cache status and actions (#22532) <br> Inaccurate cache status tracking due to unreliable updatedAt field | Low | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| **Total Catches** | - | **8/10** | **6/10** | **4/10** | **5/10** | **0/10** | **7/10** |

本项目在**CAL.COM**10个案例上的测评结果：
[https://github.com/zju-sxf-code-review/cal.com/pulls](https://github.com/zju-sxf-code-review/cal.com/pulls)

### GRAFANA

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|---------|
| Anonymous: Add configurable device limit <br> Race condition in CreateOrUpdateDevice method | High | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| AuthZService: improve authz caching <br> Cache entries without expiration causing permanent permission denials | High | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Plugins: Chore: Renamed instrumentation middleware to metrics middleware <br> Undefined endpoint constants causing compilation errors | Critical | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Advanced Query Processing Architecture <br> Double interpolation risk | Critical | ❌ | ✅ | ❌ | ✅ | ❌ | ✅ |
| Notification Rule Processing Engine <br> Missing key prop causing React rendering issues | Medium | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Dual Storage Architecture <br> Incorrect metrics recording methods causing misleading performance tracking | Medium | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |
| Database Performance Optimizations <br> Incorrect error level logging | Low | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ |
| Frontend Asset Optimization <br> Deadlock potential during concurrent annotation deletion operations | High | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Advanced SQL Analytics Framework <br> enableSqlExpressions function always returns false, disabling SQL functionality | Critical | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Unified Storage Performance Optimizations <br> Race condition in cache locking | High | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| **Total Catches** | - | **8/10** | **5/10** | **5/10** | **7/10** | **3/10** | **8/10** |

本项目在**GRAFANA**10个案例上的测评结果：
[https://github.com/zju-sxf-code-review/grafana/pulls](https://github.com/zju-sxf-code-review/grafana/pulls)


### KEYCLOAK

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|---------|
| Fixing Re-authentication with passkeys <br> ConditionalPasskeysEnabled() called without UserModel parameter | Medium | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Add caching support for IdentityProviderStorageProvider .getForLogin operations <br> Recursive caching call using session instead of delegate | Critical | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| Add AuthzClientCryptoProvider for authorization client cryptographic operations <br> Returns wrong provider (default keystore instead of BouncyCastle) | High | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| Add rolling-updates feature flag and compatibility framework <br> Incorrect method call for exit codes | Medium | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Add Client resource type and scopes to authorization schema <br> Inconsistent feature flag bug causing orphaned permissions | High | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Add Groups resource type and scopes to authorization schema <br> Incorrect permission check in canManage() method | High | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ |
| Add HTML sanitizer for translated message resources <br> Lithuanian translation files contain Italian text | Low | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Implement access token context encoding framework <br> Wrong parameter in null check (grantType vs. rawTokenId) | Critical | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Implement recovery key support for user storage providers <br> Unsafe raw List deserialization without type safety | Medium | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ |
| Fix concurrent group access to prevent NullPointerException <br> Missing null check causing NullPointerException | Critical | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **Total Catches** | - | **8/10** | **4/10** | **5/10** | **6/10** | **0/10** | **7/10** |

本项目在**KEYCLOAK**10个案例上的测评结果：
[https://github.com/zju-sxf-code-review/keycloak/pulls](https://github.com/zju-sxf-code-review/keycloak/pulls)

### DISCOURSE

| PR / Bug Description | Severity | Greptile | Copilot | CodeRabbit | Cursor | Graphite | DiffCoT |
|----------------------|----------|----------|---------|------------|--------|----------|---------|
| FEATURE: automatically downsize large images <br> Method overwriting causing parameter mismatch | Medium | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| FEATURE: per-topic unsubscribe option in emails <br> Nil reference non-existent TopicUser | High | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Add comprehensive email validation for blocked users <br> BlockedEmail.should_block? modifies DB during read | Critical | ✅ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Enhance embed URL handling and validation system <br> SSRF vulnerability using open(url) without validation | Critical | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| Optimize header layout performance with flexbox mixins <br> Mixing float: left with flexbox causes layout issues | Low | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| UX: show complete URL path if website domain is same as instance domain <br> String mutation with << operator | Medium | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| scale-color $lightness must use $secondary for dark themes <br> Inconsistent theme color lightness affects visibility | Low | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| FIX: proper handling of group memberships <br> Race conditions in async member loading | High | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| FEATURE: Localization fallbacks (server-side) <br> Thread-safety issue with lazy @loaded_locales | High | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| FEATURE: Can edit category/host relationships for embedding <br> NoMethodError before_validation in EmbeddableHost | Critical | ✅ | ✅ | ❌ | ✅ | ❌ | ✅ |
| **Total Catches** | - | **9/10** | **7/10** | **5/10** | **7/10** | **0/10** | **8/10** |

本项目在**DISCOURSE**10个案例上的测评结果：
[https://github.com/zju-sxf-code-review/discourse/pulls](https://github.com/zju-sxf-code-review/discourse/pulls)

## 结论
1. 本方案diffCoT在Critical任务上检测率达86%**位列第1**，High任务上达82%**并列第1**，在高难任务上展现出较强的竞争力，这可能得益于本方案的意图解析（同时含解析和扩展）、优化后的四大问题通用的逻辑排查Prompt库；
2. 而本方案在中难度表现欠佳（并列第4），低难度**并列第2**，中低难度表现一般，可能受制于规则库的体量以及静态分析工具的合理性使用，需要后续考虑如何更好地权衡；
3. 总体来说，对于高难任务，本方案或许能提供良好的解决思路。


