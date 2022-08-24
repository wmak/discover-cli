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
        for index, header in enumerate(self.headers):
            line_edit = ttk.TTkLineEdit(text=header, border=True)
            self.column_editor_area.layout().addWidget(line_edit, row=index, col=0, colspan=2)
            def create_edited_function(index):
                @ttk.pyTTkSlot(str)
                def edited(text):
                    self.headers[index] = text

                return edited
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

    def create_table(self):
        self.table = ttk.TTkFancyTable()
        table_header = Header()
        self.table._tableView._header = table_header
        self.table._tableView.layout().addWidget(table_header,0,0)
        table_header.activated.connect(self.header_clicked)
        self.table.setHeader = table_header.setHeader
        self.table.activated.connect(self.cell_clicked)
        self.load_table_data()

    def create_search(self):
        self.search = ttk.TTkLineEdit(text=self.query)
        self.search.returnPressed.connect(self.run_search)

    def create_split(self):
        """ The section between graph and table """
        self.split = ttk.TTkWidget(layout=ttk.TTkGridLayout(), maxHeight=5)
        column_button = ttk.TTkButton(border=False, text="Columns")
        self.split.layout().addWidget(ttk.TTkLabel(text="Results"), row=0, col=0)
        self.split.layout().addWidget(column_button, row=0, col=3)
        self.split.layout().addWidget(ttk.TTkWidget(), row=1, col=3)
        column_button.clicked.connect(self.debug_button_clicked)

    def load_graph_data(self):
        assert self.graph, "graph needs to be initialized first"
        graph_width, _ = self.graph.size()
        if graph_width == 0:
            return
        interval = int(86400 / (graph_width * 2))
        url = URL_BASE.format(
            organization_slug="sentry",
            endpoint="events-stats",
            params=f"?interval={interval}s&partial=1&project=1&query={self.query}&referrer=api.discover.default-chart&statsPeriod=24h&yAxis=eps%28%29",
        )
        if url == self.graph_url:
            return
        self.graph_url = url
        if exists("graph.json") and self.first_graph_load:
            with open("graph.json") as jsonfile:
                jsondata = json.load(jsonfile)
            if self.last_opened and datetime.now() - self.last_opened > timedelta(seconds=interval):
                self.load_graph_delta(interval)
        else:
            response = self.http.request(
                "GET",
                url,
                headers=self.http_headers
            )
            assert response.status == 200, f"Not authenticated {response.status}{url}"
            response_data = response.data.decode('utf-8')
            jsondata = json.loads(response_data)
            with open("graph.json", "w") as jsonfile:
                jsonfile.write(response_data)
        self.first_graph_load = False

        data = {
            item[0]: item[1][0]["count"]
            for item in jsondata["data"]
        }
        self.graph._data = [[0]]
        for key, value in data.items():
            self.graph.addValue([value])

    def load_graph_delta(self, interval):
        url = URL_BASE.format(
            organization_slug="sentry",
            endpoint="events-stats",
            params=f"?interval={interval}s&partial=1&project=1&query={self.query}&referrer=api.discover.default-chart&start={self.last_opened}&end={datetime.now().isoformat()}&yAxis=eps%28%29",
        )
        response = self.http.request(
            "GET",
            url,
            headers=self.http_headers
        )
        assert response.status == 200, f"Not authenticated {response.status}{response.data}"
        response_data = response.data.decode('utf-8')
        jsondata = json.loads(response_data)
        data = {
            item[0]: item[1][0]["count"]
            for item in jsondata["data"]
        }
        for value in data.values():
            self.pending_graph_data.append(value)
        self.timer.start(self.delay)

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
        if exists("table.json") and self.first_table_load:
            with open("table.json") as jsonfile:
                jsondata = json.load(jsonfile)
        else:
            response = self.http.request(
                "GET",
                url,
                headers=self.http_headers
            )
            assert response.status == 200, f"{response.status}{response.data}{url}"
            response_data = response.data.decode('utf-8')
            jsondata = json.loads(response_data)
            with open("table.json", "w") as jsonfile:
                jsonfile.write(response_data)
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
        self.table.setColumnSize([-1 for _ in headers])
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

    @ttk.pyTTkSlot(ttk.TTkKeyEvent)
    def key_pressed(self, key_event):
        self.last_key = key_event.key

    @ttk.pyTTkSlot()
    def column_added(self):
        if len(self.headers) < 20:
            self.headers.append("transaction")
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
                "last_opened": datetime.now().isoformat()
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
        self.last_opened = None
        if exists("query.json"):
            with open("query.json") as jsonfile:
                saved_query = json.load(jsonfile)
                self.query = saved_query["query"]
                self.headers = saved_query["headers"]
                self.sort_dir = saved_query["sort_dir"]
                self.sort_column = saved_query["sort_column"]
                if "last_opened" in saved_query:
                    self.last_opened = datetime.fromisoformat(saved_query["last_opened"])
        else:
            self.query = "event.type:transaction"
            self.headers = ["transaction", "count()", "failure_count()"]
            self.sort_dir = "-"
            self.sort_column = self.headers[-1]
            self.save()

        # http setup
        self.http = urllib3.PoolManager()
        self.http_headers = {
            "Authorization": f"Bearer {secrets.CLIENT_SECRET}"
        }

        # ttk setup
        self.root = ttk.TTk()
        self.delay = 0.1
        self.timer = ttk.TTkTimer()
        self.timer.timeout.connect(self.timer_event)

        self.last_key = None
        self.root.eventKeyPress.connect(self.key_pressed)
        self.root.setLayout(ttk.TTkVBoxLayout())
        self.frame = ttk.TTkWindow(parent=self.root, title="Discover", layout=ttk.TTkGridLayout())

        # Create the widgets
        self.create_split()
        self.create_column_editor()
        self.create_search()
        self.create_graph()
        self.create_table()

        # Setup the layout
        self.frame.layout().addWidget(self.search, row=0, col=0)
        self.frame.layout().addWidget(self.graph, row=1, col=0)
        self.frame.layout().addWidget(self.split, row=2, col=0)
        self.frame.layout().addWidget(self.table, row=3, col=0)

        self.root.mainloop()


Discover()
