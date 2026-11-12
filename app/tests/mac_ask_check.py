"""Drives the Ask screen of a running, packaged Lastbook.app from outside through Accessibility. Never packaged.

  python -B mac_ask_check.py PID read                 print the window's text
  python -B mac_ask_check.py PID press "Look again"   press a link or button holding that text
  python -B mac_ask_check.py PID button "fridge"      press a button holding that text
  python -B mac_ask_check.py PID ask "question" [SECS]  type a question, send it, wait for the answer, print the window's text
"""
import sys
import time

import objc

import mac_ax

_f = {}
objc.loadBundleFunctions(mac_ax._b, _f, [('AXUIElementSetAttributeValue', b'i^{__AXUIElement=}@@')])


def nodes(pid):
    return mac_ax.tree(pid)


def answer_text(pid):
    return mac_ax.text(nodes(pid))


def main():
    pid, what = int(sys.argv[1]), sys.argv[2]
    if not mac_ax.trusted():
        sys.exit('This program is not allowed to use Accessibility.')
    if what == 'read':
        print(answer_text(pid))
    elif what == 'press':
        print(mac_ax.press(nodes(pid), sys.argv[3]))
    elif what == 'button':   # a button only: starter questions share their words with old chats in the list
        print(mac_ax.press([n for n in nodes(pid) if n['role'] == 'AXButton'], sys.argv[3]))
    elif what == 'ask':
        q, secs = sys.argv[3], float(sys.argv[4]) if len(sys.argv) > 4 else 120
        box = next((n for n in nodes(pid) if n['role'] == 'AXTextArea'), None)
        if not box:
            sys.exit('no question box on screen')
        print('set', _f['AXUIElementSetAttributeValue'](box['el'], 'AXValue', q))
        print('send', mac_ax.press(nodes(pid), 'Send'))
        t0, seen = time.time(), ''
        while time.time() - t0 < secs:
            time.sleep(2)
            words = answer_text(pid)
            if 'Copy' in words and 'Sources (' in words or 'Here are the pages that best match' in words:
                break
            state = next((l.strip() for l in words.splitlines() if 'Starting the local AI' in l or 'Writing the answer' in l or 'Searching' in l or 'Thinking' in l), '')
            if state and state != seen:
                seen = state
                print(f'{time.time() - t0:5.1f}s {state[:120]}', flush=True)
        print(f'--- after {time.time() - t0:.1f}s')
        print(answer_text(pid))


if __name__ == '__main__':
    main()
