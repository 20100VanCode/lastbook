"""Control for the Whole PDF check: shows a PDF in an <iframe> in a bare WebKitGTK window (no Lastbook scheme, no content rules).
Never packaged.  linux_env.sh run python3 linux_pdf_control.py /path/file.pdf PAGE"""
import sys
import gi
gi.require_version('Gtk', '3.0'); gi.require_version('WebKit2', '4.1')
from gi.repository import Gtk, WebKit2
pdf, page = sys.argv[1], sys.argv[2]
w = Gtk.Window(title='PDF control'); w.set_default_size(1290, 916)
v = WebKit2.WebView(); w.add(v)
v.get_settings().set_allow_file_access_from_file_urls(True)
v.load_html(f'<body style="margin:0"><iframe style="width:944px;height:737px;margin:80px 0 0 300px" src="file://{pdf}#page={page}"></iframe></body>', 'file:///')
w.connect('destroy', Gtk.main_quit); w.show_all(); Gtk.main()
