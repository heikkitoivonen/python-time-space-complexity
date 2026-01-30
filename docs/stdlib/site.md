# site Module

The `site` module sets up the Python path and site-specific module search paths, handling .pth files and user packages.

## Complexity Reference

| Operation | Time | Space | Notes |
|-----------|------|-------|-------|
| Site initialization | Varies | Varies | Scans site dirs, reads .pth files |
| Add paths | O(p + l) | O(l) | p = paths added, l = .pth lines |

## Site Configuration

### Understanding site Initialization

```python
import site

# Get user site packages - O(1)
user_site = site.getusersitepackages()
print(user_site)

# Get site packages - O(1)
site_packages = site.getsitepackages()
print(site_packages)

# Check if site packages enabled - O(1)
enabled = site.ENABLE_USER_SITE
```

### .pth Files

```
# Example .pth file: mypackages.pth
# Each line is added to sys.path
/home/user/mylibraries
/opt/custom/python

# Can also execute code:
import sys; sys.path.insert(0, '/some/path')
```

## Related Documentation

- [sys Module](sys.md)
- [sysconfig Module](sysconfig.md)
