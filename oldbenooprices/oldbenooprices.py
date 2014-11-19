#-*- coding=utf-8 -*-
from __future__ import with_statement

import sys
import os.path as p
import pygtk
pygtk.require("2.0")
import gtk
import MySQLdb

#constants
TITLE = 'В память старого "Бену"'
CONFIG_PATH = p.join(p.realpath(p.dirname(__file__)), "config")
ACTIVE = 1 << 0
AVAILABLE = 1 << 1
DEFAULT_VIEW = ACTIVE & AVAILABLE

_id = lambda x: x

#logging module


#connection module
#long timeout, reconnect through stored credentials

class Connection(object):

    def __init__(self):
        self._configure()
        self.conn = MySQLdb.Connection(
            host=self.host, db=self.database,
            user=self.user, passwd=self.password,
            charset='utf8'
        )
        self.conn.autocommit(False)

    def _configure(self):
        mandatory = ['host', 'database', 'user', 'password']
        with open(CONFIG_PATH, "r") as conf:
            for param in conf.readlines():
                param = param.rstrip()
                if param:
                    attr, val = param.split("=")
                    setattr(self, attr, val)
                    try:
                        mandatory.remove(attr)
                    except ValueError:
                        pass
            if len(mandatory):
                #TODO: log
                raise Exception()


    def get_table_data(self, opts):
        #TODO: options and buttons
        cur = self.conn.cursor()
        cur.execute(
            "SELECT s.id, s.title, ss.packsize, s.preis, s.status, " +
            "ss.ship_req_pref FROM second_osbenu_shop AS s LEFT JOIN " +
            "second_osbenu_shop_supplemental AS ss ON s.id=ss.id WHERE 1"
        )
        return cur.fetchall()

    def update_record(self, record_id, data):
        #TODO: log operations
        cur = self.conn.cursor()
        wcl = "WHERE id=%d" % record_id
        q1 = "UPDATE second_osbenu_shop SET preis=%s, status=%s %s" % (data[0], data[1], wcl)
        q2 = "UPDATE second_osbenu_shop_supplemental SET ship_req_pref='%s' %s" % (data[2], wcl)
        try:
            cur.execute(q1)
            cur.execute(q2)
            self.conn.commit()
            return True
        except Exception as e:
            print 'WUT'
            print e
            #TODO: log message
            self.conn.rollback()

        return False

#global object
conn = Connection()


class Table(gtk.VBox):
    _COLS = (
        ('ID', 0, 1),
        ('Наименование', 1, 6),
        ('Упаковка', 6, 7),
        ('Цена', 7, 8),
        ('Активен', 8, 9),
        ('Доступен', 9, 10)
    )

    _COLS_TO_LEGACY = (
        _id, _id, _id, _id, int, lambda v: "USUAL" if v else "PROHIB"
    )
    _COLS_FROM_LEGACY = (
        _id, _id, _id, _id, int, lambda v: v == "USUAL"
    )


    class Record(gtk.Table):
        #if update ok -> change values

        _CLR_OK = '#B8FF70'
        _CLR_FAIL = '#BF8080'
        _AFFECTED_FLDS = (3,4,5)

        def __init__(self, data, sgs):
            self.data = list(data)
            self.entries = []
            super(Table.Record, self).__init__(1 , 6, False)
            for i in range(len(data)):
                e = gtk.Entry()
                e.set_text(str(data[i]))
                e.set_editable(False)
                e.connect("button_press_event", self.entry_menu, data[0])
                sgs[i].add_widget(e)
                e.show()
                self.entries.append(e)
                self.attach(e, Table._COLS[i][1], Table._COLS[i][2], 0, 1)
            self.show()


        def entry_menu(self, *args, **kwargs):
            dialog = gtk.Dialog(
                parent = main_window,
                buttons = (gtk.STOCK_OK, gtk.RESPONSE_ACCEPT,
                    gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT)
            )

            value_callbacks = []

            price_e = gtk.Entry()
            price_e.set_text(self.data[3])
            price_e.set_editable(True)
            price_label = gtk.Label(Table._COLS[3][0])
            price_hbox = gtk.HBox()
            price_hbox.pack_start(price_e)
            price_hbox.pack_start(price_label)
            dialog.vbox.pack_start(price_hbox)
            price_e.show()
            price_label.show()
            price_hbox.show()
            value_callbacks.append(price_e.get_text)
            for idx in (4,5):
                chk = gtk.CheckButton(Table._COLS[idx][0])
                chk.set_active(
                    Table._COLS_FROM_LEGACY[idx](self.data[idx])
                )
                chk.show()
                dialog.vbox.pack_start(chk)
                value_callbacks.append(chk.get_active)

            dialog.connect("response",
                self.menu_action,
                zip(self._AFFECTED_FLDS, value_callbacks)
            )
            dialog.show()

        def menu_action(self, widget, response_id, data):
            update_ok = False
            if response_id == gtk.RESPONSE_ACCEPT:
                form_data = {idx: Table._COLS_TO_LEGACY[idx](cb()) for idx, cb in data}
                need_update = not all(
                    map(lambda k: form_data[k] == self.data[k], form_data)
                )
                if need_update:
                    update_ok = conn.update_record(
                        self.data[0],
                        form_data.values()
                    )
                    #TODO: log
                    if update_ok:
                        for idx, val in form_data.items():
                            self.data[idx] = val
                            self.entries[idx].set_text(str(val))

                    self._colorify_me(self._CLR_OK if update_ok else self._CLR_FAIL)

            widget.destroy()

        def _colorify_me(self, color):
            color = gtk.gdk.color_parse(color)
            for e in self.entries:
                e.modify_bg(gtk.STATE_NORMAL, color)
                e.modify_fg(gtk.STATE_NORMAL, color)
                e.modify_base(gtk.STATE_NORMAL, color)


    def __init__(self):
        #fetch_data
        #scrollable
        super(Table, self).__init__()
        self.set_homogeneous(False)
        t = gtk.Table(1, 6, False)
        self._sgs = tuple(gtk.SizeGroup(gtk.SIZE_GROUP_HORIZONTAL) for _ in range(len(Table._COLS)))
        for idx ,col in enumerate(self._COLS):
            lbl = gtk.Label(col[0])
            t.attach(lbl, col[1], col[2], 0, 1)
            self._sgs[idx].add_widget(lbl)
            lbl.show()
        t.show()
        self.pack_start(t, False, False)
        #populate and redraw data (keyed by id)
        #redraw === redraw all table
        self.vwp = gtk.ScrolledWindow()
        self.vwp.show()
        self.vwp.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.pack_start(self.vwp)
        self.render_data()
        self.show()

    #record pool
    def render_data(self):
        data = conn.get_table_data(None) #TODO: options
        table = gtk.Table(len(data), 1, False)
        self.vwp.add_with_viewport(table)
        for i, r in enumerate(data):
            table.attach(Table.Record(r, self._sgs), 0, 1, i, i+1)
        table.show()


class GUI(gtk.Window):

    def __init__(self):
        super(GUI, self).__init__(gtk.WINDOW_TOPLEVEL)
        self.connect("destroy", lambda _: gtk.main_quit() or sys.exit())
        self.resize(800,600)
        self.set_title(TITLE)
        self._draw_table()
        self.show()


    def _draw_status_pane(self):
        pass

    def _draw_table(self):
        self.add(Table())
#main loop
def main():
    gui = GUI()
    globals()["main_window"] = gui
    gtk.main()

if __name__ == '__main__':
    main()
