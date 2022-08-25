from datetime import datetime, timedelta
from graph import Graph
from os.path import exists
from tableHeader import Header
import math
import TermTk as ttk
import json
import secrets
import urllib3


URL_BASE = "https://sentry.io/api/0/organizations/{organization_slug}/{endpoint}/{params}"


class COLOURS():
    GRAPH = ttk.TTkColor.fg('#444674')


class Discover():
    def create_column_editor(self):
        self.column_editor = ttk.TTkWindow(parent=self.root, title="Co[l]umn Editor", layout=ttk.TTkGridLayout())
        self.column_editor.setVisible(False)
        text_widget=ttk.TTkTextEdit(
            document=ttk.TTkTextDocument(text="""To group events, add functions f(x) that may take in additional parameters. Tag and field columns will help you view more details about the events (i.e. title)."""),
            maxHeight=3,
        )
        text_widget.setLineWrapMode(ttk.TTkK.WidgetWidth)
        text_widget.setReadOnly(ttk)
        self.column_editor.layout().addWidget(
            text_widget,
            row=0,
            col=0,
            colspan=2,
        )
        self.column_editor_area = ttk.TTkWidget(layout=ttk.TTkGridLayout())
        self.column_editor.layout().addWidget(self.column_editor_area, row=1, col=0, colspan=2)
        add_button = ttk.TTkButton(border=False, text="[A]dd", maxHeight=3)
        add_button.clicked.connect(self.column_added)
        self.column_editor.layout().addWidget(add_button, row=2, col=0)

        exit_button = ttk.TTkButton(border=False, text="Co[n]firm", maxHeight=3)
        exit_button.clicked.connect(self.column_button_clicked)
        self.column_editor.layout().addWidget(exit_button, row=2, col=1)

    def render_column_editor_rows(self):
        layout = self.column_editor_area.layout()
        self.line_edits = []
        self.line_deletes = []
        for item in layout.zSortedItems:
            layout.removeItem(item)
            del(item)
        for index, header in enumerate(self.current_headers):
            line_edit = ttk.TTkLineEdit(text=header, border=True)
            if self.column_mode:
                layout.addWidget(
                    ttk.TTkLabel(text=f"[{chr(97 + index)}]", maxWidth=3),
                    row=index,
                    col=0,
                    colspan=1
                )
                line_delete = ttk.TTkButton(border=False, text=f"x[{chr(65 + index)}]")
                offset = 1
            else:
                line_delete = ttk.TTkButton(border=False, text="x")
                offset = 0
            layout.addWidget(line_edit, row=index, col=offset, colspan=10)
            layout.addWidget(line_delete, row=index, col=11, colspan=2)
            def create_edited_function(index):
                @ttk.pyTTkSlot(str)
                def edited(text):
                    self.current_headers[index] = text

                return edited
            def create_delete_function(index):
                @ttk.pyTTkSlot()
                def delete():
                    self.current_headers.pop(index)
                    self.render_column_editor_rows()

                return delete
            delete_function = create_delete_function(index)
            line_delete.clicked.connect(delete_function)
            line_edit.textEdited.connect(create_edited_function(index))
            self.line_edits.append(line_edit)
            self.line_deletes.append(delete_function)
        self.last_line_edit = line_edit
        self.column_editor.setVisible(False)
        self.column_editor.setVisible(True)

    def create_graph(self):
        self.graph = Graph(color=COLOURS.GRAPH, align=ttk.TTkK.BOTTOM)
        self.graph.resizeEvent = self.graph_resize

    def graph_resize(self, width, height):
        if abs(width - self.graph_width) > 20:
            self.graph_width = width
            self.load_graph_data()

    def table_resize(self, width, height):
        column_width = width//len(self.headers)
        self.table.setColumnSize([column_width for _ in self.headers])

    def create_table(self):
        self.table = ttk.TTkFancyTable()
        table_header = Header()
        self.table._tableView._header = table_header
        self.table._tableView.layout().addWidget(table_header,0,0)
        table_header.activated.connect(self.header_clicked)
        self.table.setHeader = table_header.setHeader
        self.table.activated.connect(self.cell_clicked)
        self.load_table_data()
        self.table.resizeEvent = self.table_resize

    def create_search(self):
        self.search_container = ttk.TTkWidget(layout=ttk.TTkGridLayout(), maxHeight=1)
        layout = self.search_container.layout()
        layout.addWidget(ttk.TTkLabel(text="S[e]arch: ", maxWidth=10), row=0, col=0, colspan=1)
        self.search = ttk.TTkLineEdit(text=self.query)
        layout.addWidget(self.search, row=0, col=1, colspan=20)
        self.search.returnPressed.connect(self.run_search)

    def create_header(self):
        self.header = ttk.TTkWidget(layout=ttk.TTkGridLayout(), maxHeight=2)
        layout = self.header.layout()

        quit_button = ttk.TTkButton(border=False, text="[C]Quit")
        quit_button.clicked.connect(self.quit)
        layout.addWidget(quit_button, row=0, col=5, colspan=1)

        layout.addWidget(ttk.TTkWidget(), row=1, col=2, colspan=3)

        project_edit_area = ttk.TTkWidget(layout=ttk.TTkGridLayout())
        layout.addWidget(project_edit_area, row=0, col=0, colspan=1)

        self.project_edit = ttk.TTkLineEdit(text=self.project_id)
        self.project_edit.returnPressed.connect(self.update_project_id)
        project_edit_area.layout().addWidget(ttk.TTkLabel(text="[P]roject"), row=0, col=0, colspan=1)
        project_edit_area.layout().addWidget(self.project_edit, row=0, col=1, colspan=3)

    def create_split(self):
        """ The section between graph and table """
        self.split = ttk.TTkWidget(layout=ttk.TTkGridLayout(), maxHeight=2)
        column_button = ttk.TTkButton(border=False, text="Colum[n]s")
        column_button.clicked.connect(self.debug_button_clicked)

        self.yAxis_edit = ttk.TTkLineEdit(text=self.yAxis)
        self.yAxis_edit.returnPressed.connect(self.update_yAxis)

        self.split.layout().addWidget(ttk.TTkLabel(text="Results"), row=1, col=0, colspan=2)
        self.sort_display = ttk.TTkLabel(text=f"So[r]t: {self.sort_label()}")
        self.split.layout().addWidget(self.sort_display, row=1, col=2, colspan=2)
        self.split.layout().addWidget(column_button, row=1, col=3)

        self.chart_picker = ttk.TTkButton(border=False, text=f"[D]isplay: {self.chart_mode.capitalize()}")
        self.chart_picker.clicked.connect(self.toggle_chart)
        self.split.layout().addWidget(self.chart_picker, row=0, col=2)

        axis_picker = ttk.TTkWidget(layout=ttk.TTkGridLayout(), maxHeight=1)
        axis_picker.layout().addWidget(ttk.TTkLabel(text="Y-A[x]is: ", maxWidth=10), row=0, col=1)
        axis_picker.layout().addWidget(self.yAxis_edit, row=0, col=2)
        self.split.layout().addWidget(axis_picker, row=0, col=3)

    def create_error(self):
        self.error_window = ttk.TTkWindow(pos=(0,0), size=(30, 10), title="error", layout=ttk.TTkGridLayout())

    def load_graph_data(self):
        assert self.graph, "graph needs to be initialized first"
        graph_width, _ = self.graph.size()
        graph_width -= 1
        if graph_width == 0:
            return
        interval = int(86400 / (graph_width * 2))
        url = URL_BASE.format(
            organization_slug="sentry",
            endpoint="events-stats",
            params=f"?interval={interval}s&partial=1&project={self.project_id}&query={self.query}&referrer=api.discover.default-chart&statsPeriod=24h&yAxis={self.yAxis}",
        )
        if url == self.graph_url:
            return
        self.graph_url = url
        response = self.http.request(
            "GET",
            url,
            headers=self.http_headers
        )
        if response.status != 200:
            self.debug.setText(f"{response.status}{response.data}")
            return
        response_data = response.data.decode('utf-8')
        jsondata = json.loads(response_data)

        self.graph_data = {
            item[0]: item[1][0]["count"]
            for item in jsondata["data"]
        }
        self.render_graph()

    def load_table_data(self):
        assert self.table, "table needs to be initialized first"
        fields = "&".join(f"field={item}" for item in self.headers)

        # If the sort is no longer in headers pick the first function
        if self.sort_column not in self.headers:
            for col in self.headers[::-1]:
                if col.endswith(")"):
                    self.sort_column = col

        # Sort still not in headers, pick the last column
        if self.sort_column not in self.headers:
            # If the sort is no longer in headers pick the first function
            self.sort_column = self.headers[-1]

        url = URL_BASE.format(
            organization_slug="sentry",
            endpoint="events",
            params=f"?project={self.project_id}&query={self.query}&referrer=api.discover.table&statsPeriod=24h&{fields}&sort={self.sort_dir}{self.sort_column}",
        )
        if url == self.table_url:
            return
        self.table_url = url
        response = self.http.request(
            "GET",
            url,
            headers=self.http_headers
        )
        if response.status != 200:
            self.debug.setText(f"{response.status}{response.data}")
            return
        response_data = response.data.decode('utf-8')
        self.table_data = json.loads(response_data)
        self.render_table()

    def render_graph(self):
        self.graph._data = [[0]]
        for key, value in self.graph_data.items():
            if self.chart_mode == "area":
                self.graph.addValue([value])
            elif self.chart_mode == "line":
                self.graph.addValue([0, value])

    def render_table(self):
        # Reset table data
        tableView = self.table._tableView._tableView
        tableView._tableDataId = []
        tableView._tableDataText = []
        tableView._tableDataWidget = []

        # Prep the header
        headers = []
        prefix_char = 97
        self.sort_display.setText(f"So[r]t: {self.sort_label()}")
        for header in self.headers:
            prefix = f"[{chr(prefix_char)}]" if self.sort_mode else ""
            if header == self.sort_column:
                headers.append(f"{prefix}{self.sort_label()}")
            else:
                headers.append(f"{prefix}{header}")
            prefix_char += 1

        # Set the headers & data
        table_width, _ = self.table.size()
        if table_width > 0:
            column_width = table_width//len(headers)
        else:
            column_width = -1
        self.table.setColumnSize([column_width for _ in headers])
        self.table.setAlignment([
            ttk.TTkK.LEFT_ALIGN for _ in headers
        ])
        self.table.setHeader(headers)
        self.table._tableView._header.paintEvent()
        for item in self.table_data["data"]:
            self.table.appendItem([str(item[key]) for key in self.headers])

    def sort_label(self):
        if self.sort_dir == "-":
            return f"{self.sort_column}▼"
        else:
            return f"{self.sort_column}▲"

    @ttk.pyTTkSlot(int)
    def cell_clicked(self, number):
        if number in self.table_data:
            self.table_data[number]

    @ttk.pyTTkSlot(int)
    def header_clicked(self, number):
        column = self.headers[number]

        if self.sort_column == column:
            self.sort_dir = "-" if self.sort_dir == "" else ""
        else:
            self.sort_column = column

        self.save()
        self.load_table_data()

    @ttk.pyTTkSlot()
    def run_search(self):
        new_query = self.search.text()
        if self.query != new_query:
            self.query = new_query
            self.save()
            self.load_graph_data()
            self.load_table_data()

    @ttk.pyTTkSlot()
    def update_yAxis(self):
        new_axis = self.yAxis_edit.text()
        if self.yAxis != new_axis:
            self.yAxis = new_axis
            self.save()
            self.load_graph_data()

    @ttk.pyTTkSlot()
    def update_project_id(self):
        new_project = self.project_edit.text()
        if new_project != self.project_id:
            self.project_id = new_project
            self.save()
            self.load_graph_data()
            self.load_table_data()


    @classmethod
    def select_line_edit(cls, line_edit):
        line_edit.setFocus()
        txtPos = len(line_edit._text)
        line_edit._cursorPos     = txtPos
        line_edit._selectionFrom = txtPos
        line_edit._selectionTo   = txtPos
        line_edit._pushCursor()

    @ttk.pyTTkSlot()
    def toggle_chart(self):
        self.chart_mode = "line" if self.chart_mode == "area" else "area"
        self.chart_picker.text = f"[D]isplay: {self.chart_mode.capitalize()}"
        self.render_graph()
        self.save()

    @ttk.pyTTkSlot(ttk.TTkKeyEvent)
    def key_pressed(self, key_event):
        self.last_key = key_event.key
        self.last_keys.append(self.last_key)
        self.last_keys = self.last_keys[-12:]
        if key_event.mod == 67108864:
            # ctrl-e
            if self.last_key == 69:
                self.select_line_edit(self.search)
            # ctrl-n
            elif self.last_key == 78:
                self.column_button_clicked()
            # ctrl-a
            elif self.editing_columns and self.last_key == 65:
                self.column_added()
                self.select_line_edit(self.line_edits[-1])
            # ctrl-x
            elif self.last_key == 88:
                self.select_line_edit(self.yAxis_edit)
            # ctrl-o
            elif self.last_key == 76:
                if not self.editing_columns:
                    self.column_button_clicked()
                self.column_mode = True
                self.render_column_editor_rows()
                self.root.setFocus()
            elif self.last_key == 82:
                self.sort_mode = True
                self.render_table()
                self.root.setFocus()
            elif self.last_key == 68:
                self.toggle_chart()
            elif self.last_key == 80:
                self.select_line_edit(self.project_edit)
        elif self.column_mode:
            try:
                char = ord(self.last_key)
            except Exception:
                return
            if (char >= 65 and char <= 90) or (char >= 97 and char <= 122):
                self.column_mode = False
                self.render_column_editor_rows()
                if char >= 97 and char - 97 < len(self.headers):
                    self.select_line_edit(self.line_edits[char-97])
                    # unset the key so we don't append something random
                    key_event.key = ""
                if char >= 65 and char - 65 < len(self.headers):
                    self.line_deletes[char-65]()
        elif self.sort_mode:
            try:
                char = ord(self.last_key)
            except Exception:
                return
            if (char >= 65 and char <= 90) or (char >= 97 and char <= 122):
                self.sort_mode = False
                new_dir = self.sort_dir
                new_sort = self.sort_column
                if char >= 97 and char - 97 < len(self.headers):
                    new_dir = "-"
                    new_sort = self.headers[char - 97]
                elif char >= 65 and char - 65 < len(self.headers):
                    new_dir = ""
                    new_sort = self.headers[char - 65]
                if new_dir != self.sort_dir or new_sort != self.sort_column:
                    self.sort_dir = new_dir
                    self.sort_column = new_sort
                    self.save()
                    self.load_table_data()
                else:
                    self.render_table()
        if not hasattr(self, "counter") and self.last_keys == [16777235, 16777235, 16777237, 16777237, 16777234, 16777236, 16777234, 16777236, 'b', 'a']:
            # some easter egg
            self.counter = 0
            for i in self.graph_data:
                self.graph.addValue([0])
            self.timer = ttk.TTkTimer()
            self.timer.timeout.connect(self.timer_event)
            self.timer.start(self.delay)
        # self.debug.setText(str(self.last_key))

    @ttk.pyTTkSlot()
    def timer_event(self):
        self.graph.addValue([math.sin(self.counter / 100) + 1, math.sin(self.counter / 100 + 3.14) + 1])
        self.counter += 1
        self.timer.start(self.delay)

    @ttk.pyTTkSlot()
    def column_added(self):
        if len(self.current_headers) < 20:
            self.current_headers.append("transaction")
            self.save()
            self.render_column_editor_rows()

    @ttk.pyTTkSlot()
    def debug_button_clicked(self):
        self.column_button_clicked()

    @ttk.pyTTkSlot()
    def column_button_clicked(self):
        self.editing_columns = not self.editing_columns
        if self.editing_columns:
            self.current_headers = self.headers[:]
            self.render_column_editor_rows()
        elif not self.editing_columns:
            if self.current_headers != self.headers:
                self.headers = self.current_headers[:]
                self.load_table_data()

        self.save()
        self.column_editor.setVisible(self.editing_columns)
        self.frame.setVisible(False)
        self.frame.setVisible(True)

    def quit(self):
        self.save()
        self.root.quit()

    def save(self):
        with open("query.json", "w") as jsonfile:
            jsonfile.write(json.dumps({
                "query": self.query,
                "headers": self.headers,
                "sort_dir": self.sort_dir,
                "sort_column": self.sort_column,
                "yAxis": self.yAxis,
                "chart_mode": self.chart_mode,
            }))

    def __init__(self):
        # State
        self.editing_columns = False
        self.column_mode = False
        self.line_edits = []
        self.sort_mode = False
        self.graph_width = 0
        self.graph_url = ""
        self.table_url = ""
        self.table_data = None

        # Discover setup
        if exists("query.json"):
            with open("query.json") as jsonfile:
                saved_query = json.load(jsonfile)
                self.query = saved_query.get("query", "event.type:transaction")
                self.headers = saved_query.get("headers", ["transaction", "count"])
                self.sort_dir = saved_query.get("sort_dir", "-")
                self.sort_column = saved_query.get("sort_column", self.headers[-1])
                self.yAxis = saved_query.get("yAxis", "epm()")
                self.chart_mode = saved_query.get("chart_mode", "area")
                self.project_id = saved_query.get("project_id", "1")
        else:
            self.query = "event.type:transaction"
            self.headers = ["transaction", "count()", "failure_count()"]
            self.sort_dir = "-"
            self.sort_column = self.headers[-1]
            self.yAxis = "epm()"
            self.chart_mode = "area"
            self.project_id = "1"
            self.save()

        # http setup
        self.http = urllib3.PoolManager()
        self.http_headers = {
            "Authorization": f"Bearer {secrets.CLIENT_SECRET}"
        }

        # ttk setup
        self.root = ttk.TTk()
        self.delay = 0.01

        self.last_key = None
        self.last_keys = []
        self.root.eventKeyPress.connect(self.key_pressed)
        self.root.setLayout(ttk.TTkVBoxLayout())
        self.frame = ttk.TTkWindow(parent=self.root, title="Discover", layout=ttk.TTkGridLayout())
        self.tabs = ttk.TTkTabWidget(parent=self.frame)

        # Create the widgets
        self.create_header()
        self.create_split()
        self.create_column_editor()
        self.create_search()
        self.create_graph()
        self.create_table()
        self.create_error()
        self.debug = ttk.TTkTextDocument(text="test")
        debug_widget = ttk.TTkTextEdit(
            document=self.debug,
            maxHeight=1,
        )
        self.root.layout().addWidget(debug_widget)

        # Setup the layout
        # self.main_tab = ttk.TTkWidget(layout=ttk.TTkGridLayout())
        layout = self.frame.layout()
        layout.addWidget(self.header, row=0, col=0, colspan=6)
        layout.addWidget(self.search_container, row=1, col=0, colspan=6)
        layout.addWidget(self.graph, row=2, col=0, colspan=6)
        layout.addWidget(self.split, row=3, col=0, colspan=6)
        layout.addWidget(self.table, row=4, col=0, colspan=6)

        self.comparison_tab = ttk.TTkWidget(layout=ttk.TTkGridLayout())
        layout = self.comparison_tab.layout()
        # layout.addWidget(self.search, row=0, col=0)
        # layout.addWidget(self.graph, row=1, col=0)
        # layout.addWidget(self.split, row=2, col=0)
        # layout.addWidget(self.table, row=3, col=0)

        # Tab setup
        # self.tabs.addTab(self.main_tab, "main")
        # self.tabs.addTab(self.comparison_tab, "comparison")

        self.root.mainloop()


Discover()
