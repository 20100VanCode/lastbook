"""Prints the value of every slider in the app (e.g. a video's position, in seconds). Never packaged.  linux_at_value.py APP"""
import sys
import pyatspi
import linux_at
for n in linux_at.nodes(sys.argv[1]):
    if n['role'] == pyatspi.ROLE_SLIDER:
        try:
            v = n['acc'].queryValue()
            print(f"slider {n['name']!r}: {v.currentValue:.1f} of {v.maximumValue:.1f}")
        except Exception as e:
            print('slider without value', e)
