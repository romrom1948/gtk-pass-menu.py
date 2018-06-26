#!/usr/bin/env python3

import os, subprocess, gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk, GObject
from pathlib import Path
from collections import namedtuple

PassEntry = namedtuple('PassEntry', ['name','index','isDir'])

class PassStore:
    def __init__(self, store_path):
        self.store_path = Path(store_path).expanduser()
        self.current_path = Path('.')
        self.entries = []

        if not os.path.isdir(Path.resolve(self.store_path)):
            raise FileNotFoundError('invalid pass directory {0}'.format(store_path))

        self.move('.')
    
    def move(self, path):
        new_path = Path.resolve(self.store_path / self.current_path / path)

        if self.current_path.samefile(self.store_path) and path == '..':
            return False
        if not os.path.isdir(new_path):
            return False

        self.current_path = new_path
        self.entries = []

        offset = 0
        if not self.current_path.samefile(self.store_path):
            self.entries.append(PassEntry(name = '..', index = 0, isDir = True))
            offset = 1

        for index, dir_entry in enumerate(os.scandir(self.current_path)):
            if dir_entry.is_dir():
                entry = PassEntry(name = os.path.basename(dir_entry.path),
                                  index = index + offset,
                                  isDir = True)
                self.entries.append(entry)
            elif dir_entry.name.endswith(".gpg"):
                pass_name = os.path.basename(os.path.splitext(dir_entry.path)[0])
                entry = PassEntry(name = pass_name,
                                  index= index + offset,
                                  isDir = False)
                self.entries.append(entry)
    
        return True

    def get_pass(self, index):
        entry = [ e for e in self.entries if e.index == index][0]
        if entry.isDir:
            return ""
        else:
            file_path = Path.resolve(self.current_path / entry.name)
            pass_path = file_path.relative_to(Path.resolve(self.store_path))
            subprocess.check_call(["pass", "-c", pass_path])

class PassGrid(Gtk.FlowBox):
	def __init__(self):
		Gtk.FlowBox.__init__(self)
		self.set_max_children_per_line(3)
		self.set_selection_mode(Gtk.SelectionMode.SINGLE)
		self.set_activate_on_single_click(True)
		self.entries = []

	def update(self, entries):
		self.forall(self.remove)
		self.entries = []
		
		entries.sort(key=lambda e: e.index)
		for e in entries:
			label = Gtk.Label(e.name)
			self.add(label)
			self.entries.append(e)

		if len(self.entries) >= 2 and self.entries[0].name == '..':
			first = self.get_child_at_index(1)
		else:
			first = self.get_child_at_index(0)
		if not first == None: self.select_child(first)
	
	def get_selected_entry(self):
		selected_index = self.get_selected_children()[0].get_index()
		return self.entries[selected_index]
		
class PassStoreWindow(Gtk.Window):
	def __init__(self):
		Gtk.Window.__init__(self, title="pass search")

		self.store = PassStore(os.getenv('PASSWORD_STORE_DIR', '~/.password-store/'))
		self.visible_entries = self.store.entries

		self.set_position(Gtk.WindowPosition.CENTER)
		self.set_decorated(False)
		self.set_type_hint(Gdk.WindowTypeHint.POPUP_MENU)
		self.set_border_width(5)
		self.set_default_size(800,500)

		content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,spacing=50)
		self.add(content)
		self.connect("key_press_event", self.on_key_pressed)

		controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,spacing=5)
		self.filter = Gtk.Entry()
		self.filter.connect("changed", self.on_text_entered)
		controls.pack_start(self.filter, True, True, 0)

		self.grid = PassGrid()
		self.grid.connect("child-activated", self.on_entry_activated)

		scrolled = Gtk.ScrolledWindow()
		scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
		scrolled.set_propagate_natural_height(True)
		scrolled.add(self.grid)

		self.update()

		content.pack_start(controls, False, False, 0)
		content.pack_start(scrolled, False, False, 0)

	def on_key_pressed(self, widget, event):
		key = Gdk.keyval_name(event.keyval)

		if key == "Escape":
			self.destroy()
			Gtk.main_quit()
			return True

		if key == "Return":
			self.access_selected_entry()
			return True

		if key == "BackSpace" and self.filter.get_text() == "":
			self.store.move("..")
			self.visible_entries = self.store.entries
			self.update()
			return True

		return False

	def on_text_entered(self, widget):
		text = widget.get_text()
		self.visible_entries = [ e for e in self.store.entries
								 if text.upper() in e.name.upper()]
		self.update()

	def on_entry_activated(self, widget, child):
		self.access_selected_entry()

	def access_selected_entry(self):
		if self.grid.get_selected_entry().isDir:
			if self.store.move(self.grid.get_selected_entry().name):
				self.visible_entries = self.store.entries
				self.filter.set_text("")
				self.update()
		else:
			self.store.get_pass(self.grid.get_selected_entry().index)
			self.destroy()
			Gtk.main_quit()

	def update(self):
		self.grid.update(self.visible_entries)
		self.grid.show_all()
		self.filter.grab_focus()

win = PassStoreWindow()
win.show_all()
win.present()
Gtk.main()
