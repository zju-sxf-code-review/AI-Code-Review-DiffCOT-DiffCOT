"""Shared review rules and filtering criteria for code review.

This module contains:
1. Hard exclusion rules for false positive filtering
2. Signal quality criteria for validating findings
3. Static defect patterns to check for
4. Logic defect patterns to check for
"""

# ============ False Positive Filtering Rules ============

HARD_EXCLUSION_RULES = """HARD EXCLUSIONS - Automatically exclude findings matching these patterns:
1. Denial of Service (DOS) vulnerabilities or resource exhaustion attacks
2. Secrets/credentials stored on disk (these are managed separately)
3. Rate limiting concerns or service overload scenarios (services don't need to implement rate limiting)
4. Memory consumption or CPU exhaustion issues
5. Lack of input validation on non-security-critical fields without proven security impact
6. GitHub Action workflow vulnerabilities without concrete, specific attack paths (most are not exploitable in practice)
7. A lack of hardening measures. Code is not expected to implement all security best practices, just avoid obvious vulnerabilities.
8. Theoretical race conditions or timing attacks without practical exploitation paths. Only report race conditions with concrete security or data integrity impact.
9. Vulnerabilities related to outdated third-party libraries. These are managed separately and should not be reported here.
10. Memory safety issues such as buffer overflows or use-after-free-vulnerabilities are impossible in rust. Do not report memory safety issues in rust code.
11. Files that are only unit tests or only used as part of running tests.
12. Log spoofing concerns. Outputing un-sanitized user input to logs is not a vulnerability.
13. SSRF vulnerabilities that only control the path. SSRF is only a concern if it can control the host or protocol.
14. Including user-controlled content in AI system prompts is not a vulnerability. In general, the inclusion of user input in an AI prompt is not a vulnerability.
15. Do not report issues related to adding a dependency to a project that is not available from the relevant package repository. Depending on internal libraries that are not publicly available is not a vulnerability.
16. Do not report issues that cause the code to crash, but are not actually a vulnerability. E.g. a variable that is undefined or null is not a vulnerability."""

SIGNAL_QUALITY_CRITERIA = """SIGNAL QUALITY CRITERIA - For remaining findings, assess:
1. Is there a concrete, exploitable vulnerability with a clear attack path?
2. Does this represent a real security risk vs theoretical best practice?
3. Are there specific code locations and reproduction steps?
4. Would this finding be actionable for a security team?"""

PRECEDENTS = """PRECEDENTS - Apply these established rules:
1. Logging high value secrets in plaintext is a vulnerability. Otherwise, do not report issues around theoretical exposures of secrets. Logging URLs is assumed to be safe. Logging request headers is assumed to be dangerous since they likely contain credentials.
2. UUIDs can be assumed to be unguessable and do not need to be validated. If a vulnerabilities requires guessing a UUID, it is not a valid vulnerability.
3. Audit logs are not a critical security feature and should not be reported as a vulnerability if they are missing or modified.
4. Environment variables and CLI flags are trusted values. Attackers are not able to modify them in a secure environment. Any attack that relies on controlling an environment variable is invalid.
5. Resource management issues such as memory or file descriptor leaks are not valid SECURITY vulnerabilities. However, they may be reported as code quality issues (static_defect type) if they cause functional problems.
6. Subtle or low impact web vulnerabilities such as tabnabbing, XS-Leaks, prototype pollution, and open redirects are not valid.
7. React is generally secure against XSS. React does not need to sanitize or escape user input unless it is using dangerouslySetInnerHTML or similar methods. Do not report XSS vulnerabilities in React components or tsx files unless they are using unsafe methods.
8. A lack of permission checking or authentication in client-side TS code is not a vulnerability. Client-side code is not trusted and does not need to implement these checks, they are handled on the server-side. The same applies to all flows that send untrusted data to the backend, the backend is responsible for validating and sanitizing all inputs.
9. Only include MEDIUM findings if they are obvious and concrete issues.
10. Most vulnerabilities in ipython notebooks (*.ipynb files) are not exploitable in practice. Before validating a notebook vulnerability ensure it is concrete and has a very specific attack path.
11. Logging non-PII data is not a vulnerability even if the data may be sensitive. Only report logging vulnerabilities if they expose sensitive information such as secrets, passwords, or personally identifiable information (PII).
12. Command injection vulnerabilities in shell scripts are generally not exploitable in practice since shell scripts generally do not run with untrusted user input. Only report command injection vulnerabilities in shell scripts if they are concrete and have a very specific attack path for untrusted input.
13. SSRF (Server-Side Request Forgery) vulnerabilities in client-side JavaScript/TypeScript files (.js, .ts, .tsx, .jsx) are not valid since client-side code cannot make server-side requests that would bypass firewalls or access internal resources. Only report SSRF in server-side code (e.g. Python or JS that is known to run on the server-side). The same logic applies to path-traversal attacks, they are not a problem in client-side JS.
14. Path traversal attacks using ../ are generally not a problem when triggering HTTP requests. These are generally only relevant when reading files where the ../ may allow accessing unintended files.
15. Injecting into log queries is generally not an issue. Only report this if the injection will definitely lead to exposing sensitive data to external users.
16. Race conditions: Only report race conditions that have concrete, practical exploitation paths with real security or data integrity impact. Theoretical timing attacks or minor race windows are not valid."""


# ============ Static Defect Detection Rules ============

STATIC_DEFECT_RULES = """STATIC DEFECT DETECTION - Check for these code quality issues:
1. **Missing Imports**: Variables, classes, functions, or modules used but not imported or defined in scope
   - Look for NameError-prone code: using identifiers that are never imported or defined
   - Check if all type annotations reference imported types
   - Verify decorators are properly imported before use
   - **CRITICAL: Check function arguments for undefined identifiers** - e.g., calling `func(ctx, undefinedVar, req.Field)` where `undefinedVar` is never declared
   - In Go: Check for undefined constants, variables, or package-level identifiers passed to functions

2. **Importing Non-Existent Modules/Classes** (CRITICAL - Cross-file validation):
   - **When a PR adds an import statement, verify the imported class/function ACTUALLY EXISTS in the source module**
   - Example: `from sentry.api.paginator import OptimizedCursorPaginator` - check if `OptimizedCursorPaginator` is actually defined in `sentry.api.paginator`
   - Even if a PR creates a new file that supposedly defines the class, verify that file actually contains the definition
   - Watch for "phantom imports" - imports that look valid but reference classes that don't exist in the codebase
   - This will cause ImportError at runtime

3. **Undefined Variables**: Variables used before assignment or declaration
   - Variables referenced but never assigned a value
   - Using variables outside their scope (e.g., loop variables used after the loop in some languages)
   - **Function call arguments that reference non-existent variables** - This will cause compilation errors
   - Constants or endpoint names used but never defined (e.g., `endpointQueryData`, `endpointCallResource` used without declaration)

4. **API Contract Violations** (CRITICAL - Method signature validation):
   - **When calling a method, verify ALL parameters exist in the method's actual signature**
   - Example: `self.paginate(..., enable_advanced_features=True)` - check if `paginate` method actually accepts `enable_advanced_features` parameter
   - Calling methods with wrong number of arguments
   - Passing keyword arguments that don't exist in the function signature (causes TypeError)
   - Using deprecated or removed API methods
   - **Cross-reference the method definition to validate parameter names**

5. **Dead Code**: Unreachable code or unused definitions
   - Code after unconditional return/raise/break statements
   - Functions or methods that are defined but never called
   - Variables assigned but never used

6. **Type Mismatches** (when types are annotated):
   - Returning wrong type from functions
   - Passing wrong argument types to functions
   - Assigning incompatible types to typed variables

7. **Resource Handling Issues**:
   - Opening files/connections without proper closing (missing context manager)
   - Database connections or cursors not properly managed
   - Missing error handling for resource acquisition

8. **Double Semicolon and Empty Statement Errors** (CRITICAL):
   - **Double semicolons `;;`** - redundant semicolons indicating copy-paste or merge errors:
     - Example: `new GroupRepresentation();;` - object creation with double semicolon
     - Example: `int x = 5;;` - variable declaration with double semicolon
     - Example: `doSomething();;` - method call with double semicolon
     - Example: `return value;;` - return statement with double semicolon

   - **Multiple consecutive semicolons `;;;`** (ERROR severity):
     - Three or more semicolons in sequence: `statement;;;` or `};;;`
     - Often indicates severe copy-paste errors or corrupted merge

   - **Semicolon after opening brace `{;`** (ERROR severity):
     - Pattern: `if (condition) {;` or `class Foo {;`
     - This creates an empty statement at block start, likely unintended

   - **Empty statement after control structures** (ERROR severity - CRITICAL BUG):
     - `if (condition);` - the semicolon makes the if-body empty!
     - `while (condition);` - creates an infinite empty loop or no-op
     - `for (...);` - the loop body is empty, loop does nothing
     - These are almost always bugs where the developer forgot to remove the semicolon
     - Example bug: `if (user.isAdmin());` followed by `grantAccess();` - access is ALWAYS granted!

   - **Language-specific patterns**:
     - Java/C/C++/C#: Check all `;;` patterns, exclude legitimate `for(;;)` infinite loops
     - TypeScript/JavaScript: Check `;;` but exclude `for` loop syntax
     - Go: Double semicolons are syntax errors (Go uses newlines)
     - Python: Any semicolon is usually unnecessary (INFO level), but `;;` is always wrong

   - **Why this matters**:
     1. Copy-paste errors where code was duplicated
     2. Merge conflicts that were incorrectly resolved
     3. Incomplete code cleanup after refactoring
     4. **Empty statements after control structures are LOGIC BUGS** - the control structure does nothing!

   - **Watch for these patterns**:
     - `statement;;` - double semicolon at end
     - `});;}` - double semicolon in closures
     - `};;` - double semicolon after block
     - `if(x);` / `while(x);` / `for(...);` - empty control structure bodies"""


# ============ Logic Defect Detection Rules ============

LOGIC_DEFECT_RULES = """LOGIC DEFECT DETECTION - Check for these logical issues:
1. **Intent vs Implementation Mismatch**:
   - Code comments claim to do X but the implementation does Y
   - Function/method name suggests one behavior but code does another
   - TODO/FIXME comments indicating incomplete implementation
   - Docstrings that describe functionality not present in the code

2. **Incomplete Implementation**:
   - Empty function/method bodies (pass, NotImplementedError placeholders)
   - Commented-out critical code sections
   - Stub implementations that should be complete
   - Missing error handling branches (empty except/catch blocks)

3. **Control Flow Issues**:
   - Conditions that are always true or always false
   - Unreachable branches in if/switch statements
   - Loop conditions that never terminate or never execute
   - Early returns that skip necessary cleanup code

4. **Data Flow Issues**:
   - Variables overwritten before being read
   - Redundant assignments (assigning same value twice)
   - Using stale data after updates should have been applied
   - Missing null/undefined checks before dereferencing

5. **Boundary Condition Issues**:
   - Off-by-one errors in loops and array access
   - Missing edge case handling (empty arrays, null inputs, zero values)
   - Integer overflow/underflow potential
   - String index out of bounds

6. **Concurrency Issues** (when applicable):
   - Shared mutable state without synchronization
   - Race conditions in multi-threaded code
   - Deadlock potential from lock ordering

7. **Error Handling Gaps**:
   - Catching exceptions but not handling them (silent failures)
   - Rethrowing exceptions without preserving stack trace
   - Missing finally blocks for cleanup
   - Ignoring return values that indicate errors

8. **Cache Logic Asymmetry** (Security-Critical):
   - Asymmetric trust for cached positive vs negative results (e.g., trusting cached grants but ignoring cached denials)
   - Cache hit/miss handling that differs between allow and deny paths
   - Stale cache entries that could grant access to revoked permissions
   - Missing cache invalidation for security-sensitive state changes
   - Inconsistent caching strategies that could lead to privilege escalation
   - **CRITICAL PATTERN**: Code that returns early on `if allowed { return }` but falls through on denial
     - Example bug: `allowed, err := checkPermission(...); if allowed { return granted }` - denial case ignored
     - This causes: cached denials are re-checked against DB, metrics show false cache misses
     - Correct pattern: return early for BOTH allowed and denied when cache hit occurs

9. **State Consistency Issues**:
   - Code paths that update one cache/store but not related caches
   - Missing synchronization between positive and negative caches
   - Partial updates that leave system in inconsistent state

10. **Falsy Value Confusion** (CRITICAL):
   - Using `if value:` when `0`, `0.0`, or empty string `""` are valid inputs
     - Example: `if client_sample_rate:` will be False for 0.0, use `if client_sample_rate is not None:` instead
   - Confusing `None` with `0` or `False` in boolean contexts
   - Using `or` for default values when 0/False are valid: `x = value or default` fails when value is 0
   - Not distinguishing between "not set" (None) and "explicitly set to zero/false"
   - In Python: `if x:` vs `if x is not None:` vs `if x != 0:`
   - Watch for rate limits, sample rates, counts, or thresholds where 0 is a meaningful value

11. **Mutable Default Argument Pitfall** (CRITICAL - Python):
   - Using mutable objects (list, dict, set) as default arguments: `def func(items=[])`
   - Using function calls as default values in dataclass/class fields: `queued: datetime = timezone.now()`
     - This evaluates ONCE at class definition time, not at instance creation time
     - All instances will share the SAME timestamp (or mutable object)
   - Correct pattern: use `field(default_factory=list)` or `field(default_factory=timezone.now)`
   - In regular functions: use `None` as default and initialize inside: `items = items or []`
   - Watch for datetime, uuid, or any function call as default values in dataclasses

12. **Modified Variable Not Used** (CRITICAL):
   - Creating a copy/modified version of a variable but returning/using the original
     - Example: `config = original.copy(); config['key'] = value; return original` - should return `config`
   - Assigning to a new variable but continuing to use the old variable name
   - Modifying a copy when intending to modify the original (or vice versa)
   - Watch for `.copy()`, `dict()`, `list()`, spread operators creating new objects that are then ignored
   - Pattern: variable assigned -> modified -> original used instead of modified version

13. **Inconsistent Naming/Typos** (CRITICAL):
   - Same semantic value used with different key names in similar contexts
     - Example: `tags={"shard": shard_tag}` in one place, `tags={"shards": shard_tag}` in another
   - Singular vs plural inconsistency for the same concept
   - Typos in string literals that should be consistent (metric names, tag keys, config keys)
   - Near-identical string constants that might be copy-paste errors
   - Watch for: metric tags, config keys, event names, cache keys, header names
   - These cause silent failures: metrics not aggregating, configs not matching, events not correlating

14. **Standard Library API Misuse** (CRITICAL):
   - Calling methods that don't exist on standard library types
     - Example: `list.add()` doesn't exist, use `list.append()`
     - Example: `set.append()` doesn't exist, use `set.add()`
     - Example: `Lock.is_locked()` doesn't exist, use `Lock.locked()`
   - Using APIs that only exist in specific Python versions
     - Example: `Queue.shutdown()` was added in Python 3.13
   - Iterating over dict expecting key-value pairs without `.items()`
     - Example: `for k, v in data:` should be `for k, v in data.items():`
   - Confusing similar methods across different types (add vs append, locked vs is_locked)

15. **Nullish/Undefined Access After Destructuring** (CRITICAL - TypeScript/JavaScript):
   - Destructuring from nullish coalescing with empty array fallback
     - Example: `const [first] = arr ?? [];` - if arr is null, first is undefined
     - Then accessing `first.property` causes TypeError
   - Pattern to watch: `const [item] = possiblyNullArray ?? [];` followed by `item.something`
   - Fix: Add null check `if (item)` before accessing properties, or use optional chaining `item?.property`
   - This is especially dangerous because the `?? []` gives false confidence that the code handles null
   - Similar issues with object destructuring: `const {prop} = obj ?? {};` then `prop.method()`

16. **Localization/i18n Language Mismatch** (CRITICAL):
   - **Wrong language content in locale files**:
     - Example: Italian text "Installa una delle seguenti applicazioni sul tuo cellulare" in Lithuanian file `messages_lt.properties`
     - The filename suffix (e.g., `_lt`, `_de`, `_fr`) indicates the target language
     - Content must match the target language, not copied from another locale

   - **Common patterns to detect**:
     - Italian in non-Italian files: "Installa", "applicazioni", "cellulare", "seguenti", "sul tuo"
     - Spanish in non-Spanish files: "Instale", "aplicaciones", "celular", "siguientes"
     - French in non-French files: "Installez", "applications", "portable", "suivantes"
     - German in non-German files: "Installieren", "Anwendungen", "Handy"
     - English in non-English files: untranslated English text in localized files

   - **File naming conventions**:
     - `messages_lt.properties` = Lithuanian (not Italian!)
     - `messages_it.properties` = Italian
     - `messages_de.properties` = German
     - `messages_fr.properties` = French
     - `messages_es.properties` = Spanish

   - **Why this matters** (CRITICAL USER IMPACT):
     1. Completely breaks user experience for that locale's users
     2. Users see incomprehensible text in wrong language
     3. Often copy-paste errors from similar-looking locale codes (lt vs it)
     4. May indicate systematic translation process failures

   - **Common causes**:
     - Copy-paste from wrong source locale file
     - Confusing similar locale codes (lt=Lithuanian vs it=Italian)
     - Merge conflicts resolved incorrectly
     - Translation tool misconfiguration

   - **Watch for in PR reviews**:
     - Changes to `*_XX.properties` files where XX is a locale code
     - Text that doesn't match the expected language for that locale
     - Especially: lt (Lithuanian) getting Italian content, de (German) getting Dutch content"""


# ============ Code Style and Encapsulation Rules ============

STYLE_ENCAPSULATION_RULES = """CODE STYLE AND ENCAPSULATION - Check for these design issues:
1. **Encapsulation Violations**:
   - Test code directly accessing internal/private fields instead of public APIs
     - E.g., `service.internalStore.Method()` instead of `service.PublicMethod()`
     - Accessing fields prefixed with underscore (`_privateField`) from outside the class
     - In Go: accessing unexported fields (lowercase) from test files in different packages
   - Breaking abstraction layers by reaching into implementation details
   - Bypassing getter/setter methods to directly manipulate private state
   - **CRITICAL Go Pattern**: Test code accessing internal fields through chained access
     - Bad: `anonService.anonStore.ListDevices(...)` - directly accessing `anonStore` field
     - Good: `anonService.ListDevices(...)` - using public API on the service
     - Watch for patterns like `$service.$internalField.$method()` in test files
     - Common internal field suffixes: Store, Cache, Client, Repo, DB, Handler, Manager, Impl

2. **Test Code Quality Issues**:
   - Tests that rely on implementation details rather than public behavior
   - Tests accessing internal struct fields that should use exported methods
   - Mock implementations that expose internal state unnecessarily
   - Test helpers that break encapsulation boundaries
   - **Test setup contradicting implementation contracts**:
     - Setting cache/state values that the implementation never produces (e.g., setting `cache[key] = false` when implementation only stores `true` values, key absence means no permission)
     - Test assumptions that violate data invariants (e.g., testing with invalid enum values)
     - Mock data that couldn't exist in production (impossible state combinations)
     - Test comments claiming to test behavior X but setup actually tests behavior Y

3. **API Design Issues**:
   - Exposing internal implementation details in public interfaces
   - Missing abstraction layers between components
   - Leaking internal types through public APIs
   - Tight coupling between modules that should be independent

4. **Naming Convention Violations**:
   - Public methods/fields that should be private (implementation details exposed)
   - Private methods/fields accessed from outside their intended scope
   - Inconsistent visibility modifiers across similar components
   - Go: exported names (uppercase) for internal-only functionality

5. **Dependency Direction Issues**:
   - Higher-level modules depending on lower-level implementation details
   - Circular dependencies between packages/modules
   - Test code importing internal packages when public APIs exist
   - Production code depending on test utilities"""


# ============ Full Filtering Section for Review Prompt ============

def get_review_filtering_section(
    include_static_defects: bool = True,
    include_logic_defects: bool = True,
    include_style_encapsulation: bool = True
) -> str:
    """Get the complete filtering section for code review prompts.

    Args:
        include_static_defects: Whether to include static defect detection rules
        include_logic_defects: Whether to include logic defect detection rules
        include_style_encapsulation: Whether to include style and encapsulation rules

    Returns:
        Formatted filtering section string
    """
    sections = [
        HARD_EXCLUSION_RULES,
        "",
        SIGNAL_QUALITY_CRITERIA,
        "",
        PRECEDENTS,
    ]

    if include_static_defects:
        sections.extend(["", STATIC_DEFECT_RULES])

    if include_logic_defects:
        sections.extend(["", LOGIC_DEFECT_RULES])

    if include_style_encapsulation:
        sections.extend(["", STYLE_ENCAPSULATION_RULES])

    return "\n".join(sections)


def get_security_filtering_section() -> str:
    """Get filtering section for security-focused analysis (original behavior).

    Returns:
        Security-focused filtering section string
    """
    return f"""{HARD_EXCLUSION_RULES}

{SIGNAL_QUALITY_CRITERIA}

{PRECEDENTS}"""
