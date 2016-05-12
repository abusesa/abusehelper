# Rule System

Package `abusehelper.core.rules` implements AbuseHelper's event matching system.

```python
>>> from abusehelper.core import rules, events
>>> rule = rules.parse("cc = FI and type = malware")
>>> rule.match(events.Event(cc="FI", type="malware"))
True
>>> rule.match(events.Event(cc="FI", type="c&c"))
False
```

In the above example __cc = FI and type = malware__ is a *rule string*, a string adhering to the rule language described later in this document. The `rule` variable contains a *rule object* parsed from the rule string. The rule object's `match` method can then be used to test whether events match to the rule.


## Top-level functions

 * `abusehelper.core.rules.parse(...)` parses rule strings into rule objects. Raises `ValueError` if the string is not a valid rule.

 ```python
 >>> from abusehelper.core import rules
 >>> rules.parse("cc = FI")
 Match(u'cc', u'FI')
 >>> rules.rule("cc equals FI")
 Traceback (most recent call last):
    ...
 ValueError: could not parse 'cc equals FI'
 ```

 `parse` expects unicode (`u"..."`) input, but will also try to convert byte strings (`"..."`) to unicode using Python's default 7-bit ASCII encoding.

 * `abusehelper.core.rules.rule(...)` accepts both rule objects and rule strings. If the input is a rule object, then it's returned as-is. If the input is a rule string it's run through `parse(...)` and the resulting rule object is returned. This function can be used to write e.g. functions that accept both rule objects and strings as arguments.

 ```python
 >>> from abusehelper.core import rules
 >>> rules.rule(rules.Match("cc", "FI"))
 Match(u'cc', u'FI')
 >>> rules.rule("cc = FI")
 Match(u'cc', u'FI')
 ```

 * `abusehelper.core.rules.format(...)` turns a rule object into a rule string. Note that the round trip `format(parse(s))` might not return the original string `s`, but the result will be semantically equal.

 ```python
 >>> from abusehelper.core import rules
 >>> rules.format(rules.parse("cc = FI or cc = SE"))
 u'cc=SE or cc=FI'
 ```


## Rule Language


### Key Patterns

 * Star __*__ for "any key"

 * Quoted string: __"..."__

 * Unquoted string: all other pattern that does not contain whitespace or any of the characters `\`, `(`, `)`, `"`, `*`, `!`, `=`, `/`


### Value Patterns

 * Star __*__ for "any value"

 * IP range: __192.0.2.0-192.0.2.127__, __192.0.2.0/24__, __192.0.2.0__
   * Explicit range: __192.0.2.0-192.0.2.127__, inclusive so __192.0.2.0__ and __192.0.2.127__ belong to the range too
   * CIDR: __192.0.2.0/24__ is equal to __192.0.2.0-192.0.2.255__
   * Single IP address: __192.0.2.0__ is equal to __192.0.2.0-192.0.2.0__ and __192.0.2.0/32__
   * Both IPv4 and IPv6 supported

 * Domain name pattern: __example.com__, __test.example.com__, __*.example.com__
   * Case-insensitive: __example.com__ matches to __EXAMPLE.COM__ and vice versa
   * IDNA: __xn--4caaa.example.com__ matches to __äää.example.com__ and vice versa
   * Wildcards: __*.example.com__ matches any subdomain of *example.com* but not the domain *example.com* itself
     * A wildcard label can only contain the `*`, so no patterns like __test*.example__ or __**.example__
     * The wildcards can be located only in the beginning of the pattern (so no __test.*.example__) and a pattern must contain at least one non-wildcard label (so no __*.*.*__)

 * Regular expression: __/.../__
   * Not anchored by default, __/b/__ matches to __abba__, anchoring is explicit: __/^b/__, __/b$/__, __/^b$/__
   * Case-insensitivity with __/.../i__
   * `/` inside the regexp needs to be escaped: __/^http:\/\/example.com/i__

 * Quoted string: __"..."__

 * Unquoted string: all other pattern that does not contain whitespace or any of the characters `\`, `(`, `)`, `"`, `*`, `!`, `=`, `/`


### Simple Rules

 * Matches: __*x* = *y*__, Does-Not-Match: __*x* != *y*__
   * Also __*x* == *y*__ works (for us programmers out there)
   * Key can be:
     * Star: __* = FI__
     * Quoted string: __"source cc" = FI__
     * Unquoted string: __cc = FI__
   * Value can be:
     * Star: __malware = *__
     * Regular expressions: __"email address" = /@example.com$/i__
     * Quoted strings: __country = "Puerto Rico"__ (exact case-sensitive match)
     * Unquoted strings: __cc = PR__ (exact case-sensitive match)

 * Contains: __*x* in *y*__, Does-Not-Contain: __*x* not in *y*__
   * Key can be:
     * Star: __* in 192.0.2.0/24__
     * Quoted string: __"domain name" in example.com__
     * Unquoted string: __ip in 192.0.2.0/24__
   * Value can be:
     * IP range: __ip in 192.0.2.0/24__
     * Domain name pattern: __"domain name" in example.com__

 * Fuzzy matching: Any value pattern can be used by itself for fuzzy matching
    * Star: __*__ matches to any event
    * IP range: __192.0.2.0/24__ is the same thing as __* in 192.0.2.0/24__
    * Domain name pattern: __example.com__ is the same thing as __* in example.com__
    * Regular expression: __/.../__ is the same thing as __* = /.../__
    * Quoted string: __"country code"__ matches case-insensitively to any key or value containing the string "country code"
    * Unquoted string: __cc__ matches case-insensitively to any key or value containing the string "cc"


### Composite Rules: Logical Operators & Grouping

 * __*x* AND *y*__: Event has to match to both to rules __*x*__ and __*y*__
   * __cc = FI AND type = malware__ matches to events that contain both __cc__ value __FI__ *and* an __type__ value __malware__: *"Events about malware in Finland."*

 * __*x* OR *y*__: Event has to match to __*x*__ or __*y*__ or both
   * __cc = FI OR cc = SE__ matches to events that either contain __cc__ value __FI__ *or* __cc__ value __SE__ *or* both: *Events about Finland or Sweden.*

 * __NO *x*__: Match to any event that does *not* match to rule __*y*__
   * __NO type = *__ matches to events that do not have any values for key __type__: *"Events whose type we don't know."*

 * Grouping with __(...)__
   * __(cc = FI AND type = malware) OR cc = SE__: *"Events about malware in Finland or about Sweden in general."*


## Constructing Rule Objects

Apart from using rule strings and `abusehelper.core.rules.parse(...)`, rule objects can also be constructed "by hand". Indeed this is the recommended way if you're creating rules dynamically in code. Instead of going `rule = rules.parse("ip in " + ip_range)` you should build the rule object: `rule = rules.Match("ip", rules.IP(ip_range))`. Why? Imagine what happens if somehow `ip_range` is `"* or *"`.

However, dynamically built rules are often *combinations* of some static & unchanging part and a part that is determined at runtime. It's okay to keep the unchanging part as a rule string for readability and just combine it with a dynamically constructed part:

```python
rule = rules.And(
    rules.parse("cc = FI AND type = malware"),
    rules.Match("ip", rules.IP(ip_range))
)
```


### Key & Value Patterns

There are counterparts for each rule language key & value pattern in `abusehelper.core.rules`:

 * Star: `rules.Anything()` for __*__

 * (Quoted/unquoted) string: `rules.String("domain name")` for __"domain name"__, `rules.String("cc")` for __cc__

 * Regular expression: `rules.RegExp("pattern")` for __/pattern/__, `rules.RegExp("pattern", ignore_case=True)` for __/pattern/i__

 * IP range: `rules.IP(...)`
   * `rules.IP("192.0.2.0")` for __192.0.2.0__
   * `rules.IP("192.0.2.0-192.0.2.127")` or `rules.IP("192.0.2.0", "192.0.2.127")` for __192.0.2.0-192.0.2.127__
   * `rules.IP("192.0.2.0/24")` or `rules.IP("192.0.2.0", 24)` for __192.0.2.0/24__

 * Domain name: `rules.DomainName("*.example.com")` for __*.example.com__


### Simple Rules

Here `key` can be either `rules.Anything()` or `rules.String(...)`. `value` can be any of the value patterns listed above (`rules.Anything()`, `rules.String(...)`, `rules.RegExp(...)`, ...).

 * `rules.Match(key, value)` is used to build __*x* = *y*__ or __*x* in *y*__ rules, depending on what `value` is
  * __*x* in *y*__ if `value` is `rules.IP(...)` or `rules.DomainName(...)`
  * __*x* = *y*__ otherwise
  * Both `key` and `value` are optional arguments, defaulting to `rules.Anything()``

 * `rules.NonMatch(key, value)` works similarly to `Match(...)`, building __*x* != *y*__ or __*x* not in *y*__ rules

 * `rules.Fuzzy(value)` is used to build a fuzzy rule, working similarly to fuzzy rules outlined in the rule language

As a shorthand a plain string `"some string"` can be used in place of `rules.String("some string")`. Python's regular expression objects `re.compile("pattern")` can be used in place of `rules.RegExp("pattern")`. So `rules.Match("url", re.compile("^http://", re.I))` is equal to `rules.Match(rules.String("url"), rules.RegExp("^http://", ignore_case=True))`.


### Composite Rules

 * `rules.And(rule, [rule...])` builds __*x* AND *y*__ rules
   * `rules.And(rules.Match("cc", "FI"), rules.Match("type", "malware"))` for __cc = FI AND type = malware__

 * `rules.Or(rule, [rule...])` builds __*x* OR *y*__ rules
   * `rules.Or(rules.Match("cc", "FI"), rules.Match("domain name", rules.DomainName("*.fi")))` for __cc = FI AND "domain name" in *.fi__

 * `rules.No(rule)` builds __NO *x*__ rules
   * `rules.No(rules.Match(key="type"))` for __NO type = *__


## Pecularities

### There Are No Single IP Addresses

As noted earlier the rule system interprets the single IP address __192.0.2.0__ as the IP ranges __192.0.2.0-192.0.2.0__. This also applies to event values - all IP matching is done using ranges. Therefore rule __ip in 192.0.2.0/24__ matches to event `{"ip": ["192.0.2.0/30"]}` as well as event `{"ip": ["192.0.2.0"]}`.


### Common Pitfall: Has-Not vs. Has-Inequal-To

We're dealing with multi-value events, so there's a difference between *"key x having a value that doesn't match to y"* and *"key x having no value matching to y"*.

 * __abc != xyz__ matches only if an event key __abc__ has a value not matching __xyz__
     * `{"abc": ["xyz"]}` does not match: __abc__ has only value __xyz__
     * `{"abc": ["xyz", "123"]}` matches: __abc__ has value __123__, which is inequal to __xyz__
     * `{"abc": ["123"]}` matches: __abc__ has value __123__, which is inequal to __xyz__
     * `{}` does not match: __abc__ has no values whatsoever

 * __NO abc = xyz__ matches only if an event key __abc__ has no value matching __xyz__
     * `{"abc": ["xyz"]}` does not match: __abc__ has value __xyz__
     * `{"abc": ["xyz", "123"]}` does not match: __abc__ has value __xyz__
     * `{"abc": ["123"]}` matches: __abc__ has no value matching __xyz__
     * `{}` matches: __abc__ has no value matching __xyz__


### Star Patterns

 * Any event: __*__
 * Any non-empty event: __* = *__
 * Empty event: __no * = *__
 * Event a value or values for key __x__: __x = *__
 * Event has no values for key __x__: __no x = *__
