from typing import List, Tuple, Dict
from functools import partial
from datetime import datetime, timedelta

from vnpy.trader.ui import QtWidgets, QtCore
from vnpy.trader.engine import MainEngine, EventEngine
from vnpy.trader.constant import Interval, Exchange
from vnpy.trader.object import BarData
from vnpy.trader.database import DB_TZ
from vnpy.trader.utility import available_timezones

from ..engine import APP_NAME, ManagerEngine, BarOverview


INTERVAL_NAME_MAP = {
    Interval.MINUTE: "Minute",
    Interval.HOUR: "Hour",
    Interval.DAILY: "Daily",
}


class ManagerWidget(QtWidgets.QWidget):
    """"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        """"""
        super().__init__()

        self.engine: ManagerEngine = main_engine.get_engine(APP_NAME)

        self.init_ui()

    def init_ui(self) -> None:
        """"""
        self.setWindowTitle("Data Management")

        self.init_tree()
        self.init_table()

        refresh_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_tree)

        import_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Import data")
        import_button.clicked.connect(self.import_data)

        update_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Update data")
        update_button.clicked.connect(self.update_data)

        download_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Download data")
        download_button.clicked.connect(self.download_data)

        hbox1: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        hbox1.addWidget(refresh_button)
        hbox1.addStretch()
        hbox1.addWidget(import_button)
        hbox1.addWidget(update_button)
        hbox1.addWidget(download_button)

        hbox2: QtWidgets.QHBoxLayout = QtWidgets.QHBoxLayout()
        hbox2.addWidget(self.tree)
        hbox2.addWidget(self.table)

        vbox: QtWidgets.QVBoxLayout = QtWidgets.QVBoxLayout()
        vbox.addLayout(hbox1)
        vbox.addLayout(hbox2)

        self.setLayout(vbox)

    def init_tree(self) -> None:
        """"""
        labels: list = [
            "Data",
            "VT symbol",
            "Symbol",
            "Exchange",
            "Volume of data",
            "Start time",
            "End time",
            "",
            "",
            "",
        ]

        self.tree: QtWidgets.QTreeWidget = QtWidgets.QTreeWidget()
        self.tree.setColumnCount(len(labels))
        self.tree.setHeaderLabels(labels)

    def init_table(self) -> None:
        """"""
        labels: list = [
            "Time",
            "Open",
            "High",
            "Low",
            "Close",
            "Volume",
            "Turnover",
            "Open interest",
        ]

        self.table: QtWidgets.QTableWidget = QtWidgets.QTableWidget()
        self.table.setColumnCount(len(labels))
        self.table.setHorizontalHeaderLabels(labels)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.ResizeToContents
        )

    def refresh_tree(self) -> None:
        """"""
        self.tree.clear()

        # Initialize the node cache dictionary
        interval_childs: Dict[Interval, QtWidgets.QTreeWidgetItem] = {}
        exchange_childs: Dict[tuple[Interval, Exchange], QtWidgets.QTreeWidgetItem] = {}

        # Query data summaries and sort them based on contract codes
        overviews: List[BarOverview] = self.engine.get_bar_overview()
        overviews.sort(key=lambda x: x.symbol)

        # Add data cycle nodes
        for interval in [Interval.MINUTE, Interval.HOUR, Interval.DAILY]:
            interval_child = QtWidgets.QTreeWidgetItem()
            interval_childs[interval] = interval_child

            interval_name: str = INTERVAL_NAME_MAP[interval]
            interval_child.setText(0, interval_name)

        # Traverse to add data nodes
        for overview in overviews:
            # Get exchange nodes
            key: tuple = (overview.interval, overview.exchange)
            exchange_child: QtWidgets.QTreeWidgetItem = exchange_childs.get(key, None)

            if not exchange_child:
                interval_child: QtWidgets.QTreeWidgetItem = interval_childs[
                    overview.interval
                ]

                exchange_child: QtWidgets.QTreeWidgetItem = QtWidgets.QTreeWidgetItem(
                    interval_child
                )
                exchange_child.setText(0, overview.exchange.value)

                exchange_childs[key] = exchange_child

            # Create data nodes
            item = QtWidgets.QTreeWidgetItem(exchange_child)

            item.setText(1, f"{overview.symbol}.{overview.exchange.value}")
            item.setText(2, overview.symbol)
            item.setText(3, overview.exchange.value)
            item.setText(4, str(overview.count))
            item.setText(5, overview.start.strftime("%Y-%m-%d %H:%M:%S"))
            item.setText(6, overview.end.strftime("%Y-%m-%d %H:%M:%S"))

            output_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Output")
            output_func = partial(
                self.output_data,
                overview.symbol,
                overview.exchange,
                overview.interval,
                overview.start,
                overview.end,
            )
            output_button.clicked.connect(output_func)

            show_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Show")
            show_func = partial(
                self.show_data,
                overview.symbol,
                overview.exchange,
                overview.interval,
                overview.start,
                overview.end,
            )
            show_button.clicked.connect(show_func)

            delete_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Delete")
            delete_func = partial(
                self.delete_data, overview.symbol, overview.exchange, overview.interval
            )
            delete_button.clicked.connect(delete_func)

            self.tree.setItemWidget(item, 7, show_button)
            self.tree.setItemWidget(item, 8, output_button)
            self.tree.setItemWidget(item, 9, delete_button)

        # Expand top-level nodes
        self.tree.addTopLevelItems(list(interval_childs.values()))

        for interval_child in interval_childs.values():
            interval_child.setExpanded(True)

    def import_data(self) -> None:
        """"""
        dialog: ImportDialog = ImportDialog()
        n: int = dialog.exec_()
        if n != dialog.Accepted:
            return

        file_path: str = dialog.file_edit.text()
        symbol: str = dialog.symbol_edit.text()
        exchange = dialog.exchange_combo.currentData()
        interval = dialog.interval_combo.currentData()
        tz_name: str = dialog.tz_combo.currentText()
        datetime_head: str = dialog.datetime_edit.text()
        open_head: str = dialog.open_edit.text()
        low_head: str = dialog.low_edit.text()
        high_head: str = dialog.high_edit.text()
        close_head: str = dialog.close_edit.text()
        volume_head: str = dialog.volume_edit.text()
        turnover_head: str = dialog.turnover_edit.text()
        open_interest_head: str = dialog.open_interest_edit.text()
        datetime_format: str = dialog.format_edit.text()

        start, end, count = self.engine.import_data_from_csv(
            file_path,
            symbol,
            exchange,
            interval,
            tz_name,
            datetime_head,
            open_head,
            high_head,
            low_head,
            close_head,
            volume_head,
            turnover_head,
            open_interest_head,
            datetime_format,
        )

        msg: str = f"\
        CSV loaded successfully\n\
        Symbol: {symbol}\n\
        Exchange: {exchange.value}\n\
        Interval: {interval.value}\n\
        Start: {start}\n\
        End: {end}\n\
        Count: {count}\n\
        "
        QtWidgets.QMessageBox.information(self, "Loaded successfully!", msg)

    def output_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> None:
        """"""
        # Get output date range
        dialog: DateRangeDialog = DateRangeDialog(start, end)
        n: int = dialog.exec_()
        if n != dialog.Accepted:
            return
        start, end = dialog.get_date_range()

        # Get output file path
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export data", "", "CSV(*.csv)"
        )
        if not path:
            return

        result: bool = self.engine.output_data_to_csv(
            path, symbol, exchange, interval, start, end
        )

        if not result:
            QtWidgets.QMessageBox.warning(
                self,
                "Export failed!",
                "The file has been opened in another program, please close the relevant program and try to export the data again.",
            )

    def show_data(
        self,
        symbol: str,
        exchange: Exchange,
        interval: Interval,
        start: datetime,
        end: datetime,
    ) -> None:
        """"""
        # Get output date range
        dialog: DateRangeDialog = DateRangeDialog(start, end)
        n: int = dialog.exec_()
        if n != dialog.Accepted:
            return
        start, end = dialog.get_date_range()

        bars: List[BarData] = self.engine.load_bar_data(
            symbol, exchange, interval, start, end
        )

        self.table.setRowCount(0)
        self.table.setRowCount(len(bars))

        for row, bar in enumerate(bars):
            self.table.setItem(
                row, 0, DataCell(bar.datetime.strftime("%Y-%m-%d %H:%M:%S"))
            )
            self.table.setItem(row, 1, DataCell(str(bar.open_price)))
            self.table.setItem(row, 2, DataCell(str(bar.high_price)))
            self.table.setItem(row, 3, DataCell(str(bar.low_price)))
            self.table.setItem(row, 4, DataCell(str(bar.close_price)))
            self.table.setItem(row, 5, DataCell(str(bar.volume)))
            self.table.setItem(row, 6, DataCell(str(bar.turnover)))
            self.table.setItem(row, 7, DataCell(str(bar.open_interest)))

    def delete_data(self, symbol: str, exchange: Exchange, interval: Interval) -> None:
        """"""
        n = QtWidgets.QMessageBox.warning(
            self,
            "Deletion confirmed",
            f"Please check if you want to delete all the data of {symbol} {exchange.value} {interval.value}.",
            QtWidgets.QMessageBox.Ok,
            QtWidgets.QMessageBox.Cancel,
        )

        if n == QtWidgets.QMessageBox.Cancel:
            return

        count: int = self.engine.delete_bar_data(symbol, exchange, interval)

        QtWidgets.QMessageBox.information(
            self,
            "Deleted successfully",
            f"Total {count} of {symbol} {exchange.value} {interval.value} have been deleted.",
            QtWidgets.QMessageBox.Ok,
        )

    def update_data(self) -> None:
        """"""
        overviews: List[BarOverview] = self.engine.get_bar_overview()
        total: int = len(overviews)
        count: int = 0

        dialog: QtWidgets.QProgressDialog = QtWidgets.QProgressDialog(
            "Historical data update in progress", "Canceled", 0, 100
        )
        dialog.setWindowTitle("Update progress")
        dialog.setWindowModality(QtCore.Qt.WindowModal)
        dialog.setValue(0)

        for overview in overviews:
            if dialog.wasCanceled():
                break

            self.engine.download_bar_data(
                overview.symbol,
                overview.exchange,
                overview.interval,
                overview.end,
                self.output,
            )
            count += 1
            progress = int(round(count / total * 100, 0))
            dialog.setValue(progress)

        dialog.close()

    def download_data(self) -> None:
        """"""
        dialog: DownloadDialog = DownloadDialog(self.engine)
        dialog.exec_()

    def show(self) -> None:
        """"""
        self.showMaximized()

    def output(self, msg: str) -> None:
        """Exporting logs during download"""
        QtWidgets.QMessageBox.warning(
            self,
            "Data download",
            msg,
            QtWidgets.QMessageBox.Ok,
            QtWidgets.QMessageBox.Ok,
        )


class DataCell(QtWidgets.QTableWidgetItem):
    """"""

    def __init__(self, text: str = "") -> None:
        super().__init__(text)

        self.setTextAlignment(QtCore.Qt.AlignCenter)


class DateRangeDialog(QtWidgets.QDialog):
    """"""

    def __init__(self, start: datetime, end: datetime, parent=None) -> None:
        """"""
        super().__init__(parent)

        self.setWindowTitle("Select data intervals")

        self.start_edit: QtWidgets.QDateEdit = QtWidgets.QDateEdit(
            QtCore.QDate(start.year, start.month, start.day)
        )
        self.end_edit: QtWidgets.QDateEdit = QtWidgets.QDateEdit(
            QtCore.QDate(end.year, end.month, end.day)
        )

        button: QtWidgets.QPushButton = QtWidgets.QPushButton("OK")
        button.clicked.connect(self.accept)

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        form.addRow("Start time", self.start_edit)
        form.addRow("End time", self.end_edit)
        form.addRow(button)

        self.setLayout(form)

    def get_date_range(self) -> Tuple[datetime, datetime]:
        """"""
        start = self.start_edit.dateTime().toPython()
        end = self.end_edit.dateTime().toPython() + timedelta(days=1)
        return start, end


class ImportDialog(QtWidgets.QDialog):
    """"""

    def __init__(self, parent=None) -> None:
        """"""
        super().__init__()

        self.setWindowTitle("Import data from CSV file")
        self.setFixedWidth(300)

        self.setWindowFlags(
            (self.windowFlags() | QtCore.Qt.CustomizeWindowHint)
            & ~QtCore.Qt.WindowMaximizeButtonHint
        )

        file_button: QtWidgets.QPushButton = QtWidgets.QPushButton("Selection of files")
        file_button.clicked.connect(self.select_file)

        load_button: QtWidgets.QPushButton = QtWidgets.QPushButton("OK")
        load_button.clicked.connect(self.accept)

        self.file_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit()
        self.symbol_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit()

        self.exchange_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        for i in Exchange:
            self.exchange_combo.addItem(str(i.name), i)

        self.interval_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        for i in Interval:
            if i != Interval.TICK:
                self.interval_combo.addItem(str(i.name), i)

        self.tz_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        self.tz_combo.addItems(available_timezones())
        self.tz_combo.setCurrentIndex(self.tz_combo.findText("Asia/Shanghai"))

        self.datetime_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("datetime")
        self.open_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("open")
        self.high_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("high")
        self.low_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("low")
        self.close_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("close")
        self.volume_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("volume")
        self.turnover_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("turnover")
        self.open_interest_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit(
            "open_interest"
        )

        self.format_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit("%Y-%m-%d %H:%M:%S")

        info_label: QtWidgets.QLabel = QtWidgets.QLabel("Information")
        info_label.setAlignment(QtCore.Qt.AlignCenter)

        head_label: QtWidgets.QLabel = QtWidgets.QLabel("Head")
        head_label.setAlignment(QtCore.Qt.AlignCenter)

        format_label: QtWidgets.QLabel = QtWidgets.QLabel("Format")
        format_label.setAlignment(QtCore.Qt.AlignCenter)

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        form.addRow(file_button, self.file_edit)
        form.addRow(QtWidgets.QLabel())
        form.addRow(info_label)
        form.addRow("Symbol", self.symbol_edit)
        form.addRow("Exchange", self.exchange_combo)
        form.addRow("Interval", self.interval_combo)
        form.addRow("Time zone", self.tz_combo)
        form.addRow(QtWidgets.QLabel())
        form.addRow(head_label)
        form.addRow("Datetime", self.datetime_edit)
        form.addRow("Open", self.open_edit)
        form.addRow("High", self.high_edit)
        form.addRow("Low", self.low_edit)
        form.addRow("Close", self.close_edit)
        form.addRow("Volume", self.volume_edit)
        form.addRow("Turnover", self.turnover_edit)
        form.addRow("Open interest", self.open_interest_edit)
        form.addRow(QtWidgets.QLabel())
        form.addRow(format_label)
        form.addRow("Time format", self.format_edit)
        form.addRow(QtWidgets.QLabel())
        form.addRow(load_button)

        self.setLayout(form)

    def select_file(self) -> None:
        """"""
        result: str = QtWidgets.QFileDialog.getOpenFileName(self, filter="CSV (*.csv)")
        filename: str = result[0]
        if filename:
            self.file_edit.setText(filename)


class DownloadDialog(QtWidgets.QDialog):
    """"""

    def __init__(self, engine: ManagerEngine, parent=None) -> None:
        """"""
        super().__init__()

        self.engine: ManagerEngine = engine

        self.setWindowTitle("Download historical data")
        self.setFixedWidth(300)

        self.setWindowFlags(
            (self.windowFlags() | QtCore.Qt.CustomizeWindowHint)
            & ~QtCore.Qt.WindowMaximizeButtonHint
        )

        self.symbol_edit: QtWidgets.QLineEdit = QtWidgets.QLineEdit()

        self.exchange_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        for i in Exchange:
            self.exchange_combo.addItem(str(i.name), i)

        self.interval_combo: QtWidgets.QComboBox = QtWidgets.QComboBox()
        for i in Interval:
            self.interval_combo.addItem(str(i.name), i)

        end_dt: datetime = datetime.now()
        start_dt: datetime = end_dt - timedelta(days=3 * 365)

        self.start_date_edit: QtWidgets.QDateEdit = QtWidgets.QDateEdit(
            QtCore.QDate(start_dt.year, start_dt.month, start_dt.day)
        )

        button: QtWidgets.QPushButton = QtWidgets.QPushButton("Download")
        button.clicked.connect(self.download)

        form: QtWidgets.QFormLayout = QtWidgets.QFormLayout()
        form.addRow("Symbol", self.symbol_edit)
        form.addRow("Exchange", self.exchange_combo)
        form.addRow("Interval", self.interval_combo)
        form.addRow("Start date", self.start_date_edit)
        form.addRow(button)

        self.setLayout(form)

    def download(self) -> None:
        """"""
        symbol: str = self.symbol_edit.text()
        exchange: Exchange = Exchange(self.exchange_combo.currentData())
        interval: Interval = Interval(self.interval_combo.currentData())

        start_date = self.start_date_edit.date()
        start: datetime = datetime(
            start_date.year(), start_date.month(), start_date.day()
        )
        start: datetime = start.replace(tzinfo=DB_TZ)

        if interval == Interval.TICK:
            count: int = self.engine.download_tick_data(
                symbol, exchange, start, self.output
            )
        else:
            count: int = self.engine.download_bar_data(
                symbol, exchange, interval, start, self.output
            )

        QtWidgets.QMessageBox.information(
            self, "End of download", f"Total data downloaded: {count} items"
        )

    def output(self, msg: str) -> None:
        """Exporting logs during download"""
        QtWidgets.QMessageBox.warning(
            self,
            "Data download",
            msg,
            QtWidgets.QMessageBox.Ok,
            QtWidgets.QMessageBox.Ok,
        )
