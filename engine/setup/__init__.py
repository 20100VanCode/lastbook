"""First-run setup and later library changes: hardware, manifest, downloads, unpacking, switching. See docs/SETUP-API.md.

download.py is the only module in Lastbook that opens a network connection, and only for a download the person started or resumed
(or the one manifest GET when setup is opened).
"""
