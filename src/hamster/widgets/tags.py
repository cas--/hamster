# - coding: utf-8 -

# Copyright (C) 2009 Toms Bauģis <toms.baugis at gmail.com>

# This file is part of Project Hamster.

# Project Hamster is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# Project Hamster is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with Project Hamster.  If not, see <http://www.gnu.org/licenses/>.

import gtk, gobject
import pango, cairo
from math import pi

from .hamster import graphics

from .hamster.configuration import runtime

class TagsEntry(gtk.Entry):
    __gsignals__ = {
        'tags-selected': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, ()),
    }

    def __init__(self):
        gtk.Entry.__init__(self)
        self.tags = None
        self.filter = None # currently applied filter string
        self.filter_tags = [] #filtered tags

        self.popup = gtk.Window(type = gtk.WINDOW_POPUP)
        self.scroll_box = gtk.ScrolledWindow()
        self.scroll_box.set_shadow_type(gtk.SHADOW_IN)
        self.scroll_box.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        viewport = gtk.Viewport()
        viewport.set_shadow_type(gtk.SHADOW_NONE)

        self.tag_box = TagBox()
        self.tag_box.connect("tag-selected", self.on_tag_selected)
        self.tag_box.connect("tag-unselected", self.on_tag_unselected)
        self.tag_box.modify_bg(gtk.STATE_NORMAL, gtk.gdk.Color(65536.0,65536.0,65536.0))


        viewport.add(self.tag_box)
        self.scroll_box.add(viewport)
        self.popup.add(self.scroll_box)

        self.connect("button-press-event", self._on_button_press_event)
        self.connect("key-press-event", self._on_key_press_event)
        self.connect("key-release-event", self._on_key_release_event)
        self.connect("focus-out-event", self._on_focus_out_event)
        self.connect("parent-set", self._on_parent_set)

        runtime.dispatcher.add_handler('new_tags_added', self.refresh_tags)
        self.show()
        self.populate_suggestions()

    def refresh_tags(self, event, data):
        self.tags = None

    def get_tags(self):
        # splits the string by comma and filters out blanks
        return [tag.strip() for tag in self.get_text().decode('utf8', 'replace').split(",") if tag.strip()]

    def on_tag_selected(self, tag_box, tag):
        tags = self.get_tags()
        tags.append(tag)

        self.tag_box.selected_tags = tags

        self.set_text(", ".join(tags))
        self.set_position(len(self.get_text()))

    def on_tag_unselected(self, tag_box, tag):
        tags = self.get_tags()
        while tag in tags: #it could be that dear user is mocking us and entering same tag over and over again
            tags.remove(tag)

        self.tag_box.selected_tags = tags

        self.set_text(", ".join(tags))
        self.set_position(len(self.get_text()))


    def hide_popup(self):
        self.popup.hide()

    def show_popup(self):
        if not self.filter_tags:
            self.popup.hide()
            return

        alloc = self.get_allocation()
        x, y = self.get_parent_window().get_origin()

        self.popup.move(x + alloc.x,y + alloc.y + alloc.height)

        w = alloc.width

        height = self.tag_box.count_height(w)

        self.scroll_box.set_size_request(w, height)
        self.popup.resize(w, height)
        self.popup.show_all()


    def complete_inline(self):
        return

    def refresh_activities(self):
        # scratch activities and categories so that they get repopulated on demand
        self.activities = None
        self.categories = None

    def populate_suggestions(self):
        self.tags = self.tags or [tag["name"] for tag in runtime.storage.get_tags(autocomplete = True)]

        cursor_tag = self.get_cursor_tag()

        self.filter = cursor_tag

        entered_tags = self.get_tags()
        self.tag_box.selected_tags = entered_tags

        self.filter_tags = [tag for tag in self.tags if (tag or "").lower().startswith((self.filter or "").lower())]

        self.tag_box.draw(self.filter_tags)



    def _on_focus_out_event(self, widget, event):
        self.hide_popup()

    def _on_button_press_event(self, button, event):
        self.populate_suggestions()
        self.show_popup()

    def _on_key_release_event(self, entry, event):
        if (event.keyval in (gtk.keysyms.Return, gtk.keysyms.KP_Enter)):
            if self.popup.get_property("visible"):
                if self.get_text():
                    self.hide_popup()
                return True
            else:
                if self.get_text():
                    self.emit("tags-selected")
                return False
        elif (event.keyval == gtk.keysyms.Escape):
            if self.popup.get_property("visible"):
                self.hide_popup()
                return True
            else:
                return False
        else:
            self.populate_suggestions()
            self.show_popup()

            if event.keyval not in (gtk.keysyms.Delete, gtk.keysyms.BackSpace):
                self.complete_inline()


    def get_cursor_tag(self):
        #returns the tag on which the cursor is on right now
        if self.get_selection_bounds():
            cursor = self.get_selection_bounds()[0]
        else:
            cursor = self.get_position()

        text = self.get_text().decode('utf8', 'replace')

        return text[text.rfind(",", 0, cursor)+1:max(text.find(",", cursor+1)+1, len(text))].strip()


    def replace_tag(self, old_tag, new_tag):
        tags = self.get_tags()
        if old_tag in tags:
            tags[tags.index(old_tag)] = new_tag

        if self.get_selection_bounds():
            cursor = self.get_selection_bounds()[0]
        else:
            cursor = self.get_position()

        self.set_text(", ".join(tags))
        self.set_position(cursor + len(new_tag)-len(old_tag)) # put the cursor back

    def _on_key_press_event(self, entry, event):
        if event.keyval == gtk.keysyms.Tab:
            if self.popup.get_property("visible"):
                #we have to replace
                if self.get_text() and self.get_cursor_tag() != self.filter_tags[0]:
                    self.replace_tag(self.get_cursor_tag(), self.filter_tags[0])
                    return True
                else:
                    return False
            else:
                return False

        return False

    def _on_parent_set(self, old_parent, user_data):
        # when parent changes to itself, that means that it has been actually deleted
        if old_parent and old_parent == self.get_toplevel():
            runtime.dispatcher.del_handler('new_tags_added', self.refresh_tags)


class TagBox(graphics.Scene):
    __gsignals__ = {
        'tag-selected': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (str,)),
        'tag-unselected': (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (str,)),
    }

    def __init__(self, interactive = True):
        graphics.Scene.__init__(self)
        self.interactive = interactive
        self.hover_tag = None
        self.tags = []
        self.selected_tags = []
        self.layout = None

        self.font_size = 10 #override default font size

        if self.interactive:
            self.connect("on-mouse-over", self.on_mouse_over)
            self.connect("on-mouse-out", self.on_mouse_out)
            self.connect("on-click", self.on_tag_click)

        self.connect("on-enter-frame", self.on_enter_frame)

    def on_mouse_over(self, area, targets):
        tag = targets[0]
        tag.tag.fill = tag.graphics.colors.darker(tag.tag.fill, -20)

    def on_mouse_out(self, area, targets):
        tag = targets[0]

        if tag.text in self.selected_tags:
            tag.tag.fill = (242, 229, 97)
        else:
            tag.tag.fill = (241, 234, 170)


    def on_tag_click(self, area, event, targets):
        tag = targets[0]
        if tag.text in self.selected_tags:
            self.emit("tag-unselected", tag.text)
        else:
            self.emit("tag-selected", tag.text)
        self.on_mouse_out(area, targets) #paint
        self.redraw()

    def draw(self, tags):
        new_tags = [Tag(label) for label in tags]

        for tag in self.tags:
            self.sprites.remove(tag)

        self.add_child(*new_tags)
        self.tags = new_tags

        self.show()
        self.redraw()

    def count_height(self, width):
        # reposition tags and see how much space we take up
        self.width = width
        w, h = self.on_enter_frame(None, None)
        return h + 6

    def on_enter_frame(self, scene, context):
        cur_x, cur_y = 4, 4
        tag = None
        for tag in self.tags:
            if cur_x + tag.width >= self.width - 5:  #if we do not fit, we wrap
                cur_x = 5
                cur_y += tag.height + 6

            tag.x = cur_x
            tag.y = cur_y

            cur_x += tag.width + 6 #some padding too, please

        if tag:
            cur_y += tag.height + 2 # the last one

        return cur_x, cur_y

class Tag(graphics.Sprite):
    def __init__(self, text, interactive = True, color = "#F1EAAA"):
        graphics.Sprite.__init__(self, interactive = interactive)

        self.text = text
        label = graphics.Label(text, size = 8, color = (30, 30, 30), y = 2)

        w, h = label.width + 18, label.height + 3
        corner = h / 3
        label.x = corner + 8

        self.color = color

        self.tag = graphics.Polygon([(0, corner),
                                         (corner, 0),
                                         (w, 0),
                                         (w, h),
                                         (corner, h),
                                         (0, h - corner)],
                                        x = 0.5, y = 0.5,
                                        fill = self.color,
                                        stroke = "#b4b4b4",
                                        line_width = 1)

        self.add_child(self.tag)
        self.add_child(graphics.Circle(2, x = 5.5, y = h / 2 - 1.5,
                                       fill = "#fff",
                                       stroke = "#b4b4b4",
                                       line_width = 1))

        self.add_child(label)
        self.width, self.height = w, h

        self.graphics.set_color((0,0,0), 0)
        self.graphics.rectangle(0, 0, w, h)
        self.graphics.stroke()
