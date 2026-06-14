"""Domain pattern compilation for DNS interception.

Converts server config domain patterns to compiled regexes
for matching DNS query names.
"""
import re


def compile_patterns(domains):
    """Compile server config domain patterns to regexes.

    Args:
        domains: List of dicts from server config, each with:
            - "pattern": str (e.g., ".steamcontent.com" or "dist.blizzard.com")
            - "block_https": bool (optional, default False)

    Returns:
        Tuple of (domain_patterns, block_https_patterns) where each is a list
        of compiled regex objects.
    """
    domain_patterns = []
    block_https_patterns = []

    for entry in domains:
        pattern = entry["pattern"]

        if pattern.startswith("."):
            # ".steamcontent.com" matches "steamcontent.com" and all subdomains
            regex = re.compile(rf"^(.*\.)?{re.escape(pattern[1:])}$")
        else:
            # "steamcontent.com" matches only "steamcontent.com"
            regex = re.compile(rf"^{re.escape(pattern)}$")

        domain_patterns.append(regex)
        if entry.get("block_https", False):
            block_https_patterns.append(regex)

    return domain_patterns, block_https_patterns


def matches_any(domain, patterns):
    """Check if a domain matches any of the compiled patterns.

    Args:
        domain: Domain name string (no trailing dot)
        patterns: List of compiled regex objects

    Returns:
        True if domain matches any pattern
    """
    for pattern in patterns:
        if pattern.match(domain):
            return True
    return False
