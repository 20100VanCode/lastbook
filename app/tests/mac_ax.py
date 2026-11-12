"""Reads and presses things in one app's window through macOS Accessibility, from outside, without activating it. Never packaged."""
import objc
from Foundation import NSBundle

_b = NSBundle.bundleWithIdentifier_('com.apple.ApplicationServices') or NSBundle.bundleWithPath_('/System/Library/Frameworks/ApplicationServices.framework')
_f = {}
objc.loadBundleFunctions(_b, _f, [('AXUIElementGetTypeID', b'Q')])
objc.registerCFSignature('AXUIElementRef', b'^{__AXUIElement=}', _f['AXUIElementGetTypeID']())
objc.loadBundleFunctions(_b, _f, [('AXIsProcessTrusted', b'Z'), ('AXUIElementCreateApplication', b'^{__AXUIElement=}i'),
                                  ('AXUIElementCopyAttributeValue', b'i^{__AXUIElement=}@o^@'), ('AXUIElementPerformAction', b'i^{__AXUIElement=}@')])


def attr(el, name):
    err, value = _f['AXUIElementCopyAttributeValue'](el, name, None)
    return value if err == 0 else None


def walk(el, depth=0, limit=9000, out=None):
    out = [] if out is None else out
    if len(out) >= limit or depth > 60:
        return out
    url = attr(el, 'AXURL')
    out.append({'el': el, 'depth': depth, 'role': str(attr(el, 'AXRole') or ''), 'title': str(attr(el, 'AXTitle') or ''), 'value': str(attr(el, 'AXValue') or '')[:300], 'desc': str(attr(el, 'AXDescription') or ''), 'url': str(url.absoluteString()) if url is not None else ''})
    for child in attr(el, 'AXChildren') or []:
        walk(child, depth + 1, limit, out)
    return out


def tree(pid):
    """The app's windows only. The menu bar is left out on purpose: its Apple menu lists the user's recent files."""
    out = []
    for window in attr(_f['AXUIElementCreateApplication'](pid), 'AXWindows') or []:
        walk(window, 0, 9000, out)
    return out


def text(nodes):
    lines = []
    for n in nodes:
        words = ' | '.join(x for x in (n['title'], n['value'], n['desc'], n['url']) if x)
        if words or n['role'] in ('AXWebArea', 'AXWindow'):
            lines.append('  ' * min(n['depth'], 12) + f"{n['role']}: {words}")
    roles = {}
    for n in nodes:
        roles[n['role']] = roles.get(n['role'], 0) + 1
    return '\n'.join(lines + [f'roles: {roles}'])


def press(nodes, wanted):
    """Presses the first link or button whose words hold this text. Returns what it pressed, or None."""
    for n in nodes:
        words = ' '.join((n['title'], n['value'], n['desc'], n['url']))
        if n['role'] in ('AXLink', 'AXButton') and wanted in words:
            return {'pressed': words[:200], 'err': _f['AXUIElementPerformAction'](n['el'], 'AXPress')}
    return None


trusted = _f['AXIsProcessTrusted']
