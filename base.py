from datetime import datetime, timedelta
from graph import Graph
from os.path import exists
from tableHeader import Header
import TermTk as ttk
import json
import secrets
import urllib3


URL_BASE = "https://sentry.io/api/0/organizations/{organization_slug}/{endpoint}/{params}"


class COLOURS():
    GRAPH = ttk.TTkColor.fg('#444674')


class Discover():
    def create_column_editor(self):
        self.column_editor = ttk.TTkWindow(parent=self.root, title="Column Editor", layout=ttk.TTkGridLayout())
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
        add_button = ttk.TTkButton(border=False, text="Add", maxHeight=3)
        add_button.clicked.connect(self.column_added)
        self.column_editor.layout().addWidget(add_button, row=2, col=0)

        exit_button = ttk.TTkButton(border=False, text="Confirm", maxHeight=3)
        exit_button.clicked.connect(self.column_button_clicked)
        self.column_editor.layout().addWidget(exit_button, row=2, col=1)

    def render_column_editor_rows(self):
        layout = self.column_editor_area.layout()
        for item in layout.zSortedItems:
            layout.removeItem(item)
            del(item)
        for index, header in enumerate(self.current_headers):
            line_edit = ttk.TTkLineEdit(text=header, border=True)
            line_delete = ttk.TTkButton(border=False, text="x")
            layout.addWidget(line_edit, row=index, col=0, colspan=6)
            layout.addWidget(line_delete, row=index, col=9, colspan=1)
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
            line_delete.clicked.connect(create_delete_function(index))
            line_edit.textEdited.connect(create_edited_function(index))
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
        return
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
        self.search = ttk.TTkLineEdit(text=self.query)
        self.search.returnPressed.connect(self.run_search)

    def create_split(self):
        """ The section between graph and table """
        self.split = ttk.TTkWidget(layout=ttk.TTkGridLayout(), maxHeight=2)
        column_button = ttk.TTkButton(border=False, text="Columns")
        column_button.clicked.connect(self.debug_button_clicked)

        self.yAxis_edit = ttk.TTkLineEdit(text=self.yAxis)
        self.yAxis_edit.returnPressed.connect(self.update_yAxis)

        self.split.layout().addWidget(ttk.TTkLabel(text="Results"), row=1, col=0, colspan=2)
        self.split.layout().addWidget(column_button, row=1, col=3)

        axis_picker = ttk.TTkWidget(layout=ttk.TTkGridLayout(), maxHeight=1)
        axis_picker.layout().addWidget(ttk.TTkLabel(text="Y-Axis: ", maxWidth=8), row=0, col=1)
        axis_picker.layout().addWidget(self.yAxis_edit, row=0, col=2)
        self.split.layout().addWidget(axis_picker, row=0, col=3)

    def create_error(self):
        self.error_window = ttk.TTkWindow(pos=(0,0), size=(30, 10), title="error", layout=ttk.TTkGridLayout())

    def load_graph_data(self):
        assert self.graph, "graph needs to be initialized first"
        self.pending_graph_data = []
        graph_width, _ = self.graph.size()
        graph_width -= 1
        if graph_width == 0:
            return
        interval = int(86400 / (graph_width * 2))
        url = URL_BASE.format(
            organization_slug="sentry",
            endpoint="events-stats",
            params=f"?interval={interval}s&partial=1&project=1&query={self.query}&referrer=api.discover.default-chart&statsPeriod=24h&yAxis={self.yAxis}",
        )
        if url == self.graph_url:
            return
        self.graph_url = url
        response = self.http.request(
            "GET",
            url,
            headers=self.http_headers
        )
        assert response.status == 200, f"{response.status}{response.data}{url}"
        response_data = response.data.decode('utf-8')
        jsondata = json.loads(response_data)

        data = {
            item[0]: item[1][0]["count"]
            for item in jsondata["data"]
        }
        self.graph._data = [[0]]
        for key, value in data.items():
            self.graph.addValue([value])

    def timer_event(self):
        if len(self.pending_graph_data) > 0:
            self.graph.addValue([self.pending_graph_data.pop()])
            self.timer.start(self.delay)

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
            params=f"?project=1&query={self.query}&referrer=api.discover.table&statsPeriod=24h&{fields}&sort={self.sort_dir}{self.sort_column}",
        )
        if url == self.table_url:
            return
        self.table_url = url
        response = self.http.request(
            "GET",
            url,
            headers=self.http_headers
        )
        assert response.status == 200, f"{response.status}{response.data}{url}"
        response_data = response.data.decode('utf-8')
        jsondata = json.loads(response_data)
        self.first_table_load = False

        # Reset table data
        tableView = self.table._tableView._tableView
        tableView._tableDataId = []
        tableView._tableDataText = []
        tableView._tableDataWidget = []

        # Prep the header
        headers = []
        for header in self.headers:
            if header == self.sort_column:
                if self.sort_dir == "-":
                    headers.append(f"{header}▼")
                else:
                    headers.append(f"{header}▲")
            else:
                headers.append(header)

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
        self.table_data = jsondata["data"]
        for item in jsondata["data"]:
            self.table.appendItem([str(item[key]) for key in self.headers])

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

    @ttk.pyTTkSlot(ttk.TTkKeyEvent)
    def key_pressed(self, key_event):
        self.last_key = key_event.key

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

    def save(self):
        with open("query.json", "w") as jsonfile:
            jsonfile.write(json.dumps({
                "query": self.query,
                "headers": self.headers,
                "sort_dir": self.sort_dir,
                "sort_column": self.sort_column,
                "yAxis": self.yAxis,
            }))

    def __init__(self):
        # State
        self.editing_columns = False
        self.line_edits = []
        self.graph_width = 0
        self.first_table_load = True
        self.first_graph_load = True
        self.graph_url = ""
        self.table_url = ""
        self.pending_graph_data = []

        # Discover setup
        if exists("query.json"):
            with open("query.json") as jsonfile:
                saved_query = json.load(jsonfile)
                self.query = saved_query.get("query", "event.type:transaction")
                self.headers = saved_query.get("headers", ["transaction", "count"])
                self.sort_dir = saved_query.get("sort_dir", "-")
                self.sort_column = saved_query.get("sort_column", self.headers[-1])
                self.yAxis = saved_query.get("yAxis", "epm()")
        else:
            self.query = "event.type:transaction"
            self.headers = ["transaction", "count()", "failure_count()"]
            self.sort_dir = "-"
            self.sort_column = self.headers[-1]
            self.yAxis = "epm()"
            self.save()

        # http setup
        self.http = urllib3.PoolManager()
        self.http_headers = {
            "Authorization": f"Bearer {secrets.CLIENT_SECRET}"
        }

        # ttk setup
        self.root = ttk.TTk()
        self.delay = 0.001
        self.timer = ttk.TTkTimer()
        self.timer.timeout.connect(self.timer_event)

        self.last_key = None
        self.root.eventKeyPress.connect(self.key_pressed)
        self.root.setLayout(ttk.TTkVBoxLayout())
        self.frame = ttk.TTkWindow(parent=self.root, title="Discover", layout=ttk.TTkGridLayout())
        self.tabs = ttk.TTkTabWidget(parent=self.frame)

        # Create the widgets
        self.create_split()
        self.create_column_editor()
        self.create_search()
        self.create_graph()
        self.create_table()
        self.create_error()

        # Setup the layout
        self.main_tab = ttk.TTkWidget(layout=ttk.TTkGridLayout())
        layout = self.main_tab.layout()
        layout.addWidget(self.search, row=0, col=0)
        layout.addWidget(self.graph, row=1, col=0)
        layout.addWidget(self.split, row=2, col=0)
        layout.addWidget(self.table, row=3, col=0)

        self.comparison_tab = ttk.TTkWidget(layout=ttk.TTkGridLayout())
        layout = self.comparison_tab.layout()
        # layout.addWidget(self.search, row=0, col=0)
        # layout.addWidget(self.graph, row=1, col=0)
        # layout.addWidget(self.split, row=2, col=0)
        # layout.addWidget(self.table, row=3, col=0)

        # Tab setup
        self.tabs.addTab(self.main_tab, "main")
        # self.tabs.addTab(self.comparison_tab, "comparison")

        self.root.mainloop()


Discover()
