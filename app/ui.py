import sys
import os
import traceback
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QLineEdit, QPushButton,
    QTextEdit, QLabel, QComboBox, QGridLayout, QMessageBox, QSpinBox,
    QGroupBox, QStatusBar, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import QTimer, Qt, QRunnable, pyqtSlot, QObject, pyqtSignal, QThreadPool,QSize
from PyQt6.QtGui import QMovie, QColor

from api_client import APIClient
from printer import print_file_with_settings, get_printer_capabilities

class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(tuple)

class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            self.signals.error.emit((type(e), e))
        else:
            self.signals.finished.emit(result)

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.STATUS_MESSAGES = {
            "disconnected": ("🔴 قطع", "red"),
            "connecting": ("🟡 در حال اتصال...", "#E67E22"),
            "connected": ("🟢 متصل", "green"),
            "polling": ("🔵 در حال بررسی سفارشات...", "#3498DB"),
            "error": ("🔴 خطا", "red"),
            "loading": ("🟡 در حال دریافت داده...", "#E67E22")
        }
        self.client = None
        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self.check_orders)
        self.threadpool = QThreadPool()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("کلاینت چاپ خودکار")
        self.setMinimumSize(750, 800)
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.addWidget(self._create_api_group())
        main_layout.addWidget(self._create_printer_group())
        main_layout.addWidget(self._create_orders_display_group())
        main_layout.addWidget(self._create_log_group())
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.update_status("disconnected")
        self.update_ui_state()

    def _create_api_group(self):
        api_group = QGroupBox("۱. اتصال به سرور")
        api_group.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout = QGridLayout()
        self.api_input = QLineEdit()
        self.api_input.setPlaceholderText("کلید API منحصر به فرد خود را وارد کنید")
        self.api_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.connect_button = QPushButton("اتصال")
        self.connect_button.clicked.connect(self.run_connection_worker)
        self.loading_spinner = QLabel()
        self.loading_spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_spinner.setText("در حال برقراری ارتباط...")
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel("🔑 کلید API:"), 0, 0)
        layout.addWidget(self.api_input, 0, 1, 1, 2)
        layout.addWidget(self.connect_button, 1, 1, 1, 2)
        layout.addWidget(self.loading_spinner, 2, 0, 1, 3)
        layout.addWidget(self.status_label, 3, 0, 1, 3)
        api_group.setLayout(layout)
        return api_group

    def _create_printer_group(self):
        printer_group = QGroupBox("۲. کنترل چاپ")
        printer_group.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout = QGridLayout()
        self.printer_select = QComboBox()
        self.printer_select.addItems(self.get_available_printers())
        self.printer_select.setToolTip("پرینتر مورد نظر برای چاپ سفارشات را انتخاب کنید.")
        self.poll_interval_spinbox = QSpinBox()
        self.poll_interval_spinbox.setMinimum(5)
        self.poll_interval_spinbox.setMaximum(300)
        self.poll_interval_spinbox.setValue(10)
        self.poll_interval_spinbox.setSuffix(" ثانیه")
        self.start_button = QPushButton("▶ شروع چاپ خودکار")
        self.start_button.clicked.connect(self.start_polling)
        self.stop_button = QPushButton("⏹ توقف چاپ خودکار")
        self.stop_button.clicked.connect(self.stop_polling)
        layout.addWidget(QLabel("🖨️ انتخاب پرینتر:"), 0, 0)
        layout.addWidget(self.printer_select, 0, 1, 1, 2)
        layout.addWidget(QLabel("⏱️ فاصله زمانی بررسی:"), 1, 0)
        layout.addWidget(self.poll_interval_spinbox, 1, 1, 1, 2)
        layout.addWidget(self.start_button, 2, 0, 1, 3)
        layout.addWidget(self.stop_button, 3, 0, 1, 3)
        printer_group.setLayout(layout)
        return printer_group

    def _create_orders_display_group(self):
        orders_group = QGroupBox("۳. لیست سفارشات")
        orders_group.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout = QVBoxLayout()
        self.orders_table = QTableWidget()
        self.orders_table.setColumnCount(8)
        self.orders_table.setHorizontalHeaderLabels(["شماره", "مشتری", "نام فایل", "تعداد", "رنگ", "نوع چاپ", "جهت", "وضعیت"])
        self.orders_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.orders_table.setAlternatingRowColors(True)
        header = self.orders_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.refresh_button = QPushButton("🔄 به‌روزرسانی لیست سفارشات")
        self.refresh_button.clicked.connect(self.run_fetch_orders_worker)
        layout.addWidget(self.orders_table)
        layout.addWidget(self.refresh_button)
        orders_group.setLayout(layout)
        return orders_group

    def _create_log_group(self):
        log_group = QGroupBox("گزارش فعالیت‌ها")
        log_group.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout = QVBoxLayout()
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        layout.addWidget(self.log_area)
        log_group.setLayout(layout)
        return log_group

    def run_connection_worker(self):
        api_key = self.api_input.text().strip()
        if not api_key:
            self.show_error("کلید API وجود ندارد", "لطفاً برای اتصال، کلید API خود را وارد کنید.")
            return
        self.update_ui_state(is_connecting=True)
        worker = Worker(self._perform_connection, api_key)
        worker.signals.finished.connect(self.on_connection_finished)
        worker.signals.error.connect(self.on_worker_error)
        self.threadpool.start(worker)

    def _perform_connection(self, api_key: str) -> APIClient:
        self.log("در حال تلاش برای اتصال به سرور...")
        client = APIClient(api_key)
        if client.validate():
            return client
        else:
            raise ConnectionError("کلید API نامعتبر است یا سرور در دسترس نیست.")

    def on_connection_finished(self, client: APIClient):
        self.log("✅ اتصال موفقیت‌آمیز بود.")
        self.client = client
        self.update_status("connected")
        self.run_fetch_orders_worker()

    def run_fetch_orders_worker(self):
        if not self.client:
            self.show_error("عدم اتصال", "لطفاً ابتدا به سرور متصل شوید.")
            return
        self.update_ui_state(is_loading_data=True)
        worker = Worker(self.client.get_new_orders)
        worker.signals.finished.connect(self.on_fetch_orders_finished)
        worker.signals.error.connect(self.on_worker_error)
        self.threadpool.start(worker)

    def on_fetch_orders_finished(self, all_orders: list):
        self.update_ui_state(is_connected=True)
        self.orders_table.setRowCount(0)
        status_map = {"pending": "در انتظار", "completed": "چاپ شده", "in_progress": "در حال انجام"}
        for order in all_orders:
            row = self.orders_table.rowCount()
            self.orders_table.insertRow(row)
            color_fa = "رنگی" if order.get('color') == 'ColorFull' else "سیاه‌وسفید"
            sides_fa = "دورو" if order.get('sides') == 'Double-sided' else "یک‌رو"
            layout_fa = "افقی" if order.get('layout') == 'Landscape' else "عمودی"
            status_fa = status_map.get(order.get('order_status'), order.get('order_status'))
            items = [str(order.get('id', '')), order.get('customer_name', ''), order.get('file_name', ''), str(order.get('copies', '')), color_fa, sides_fa, layout_fa, status_fa]
            for col, item_text in enumerate(items):
                self.orders_table.setItem(row, col, QTableWidgetItem(item_text))
        self.log(f"{len(all_orders)} سفارش با موفقیت دریافت و نمایش داده شد.")

    def on_worker_error(self, error_tuple):
        value, tb = error_tuple
        self.log(f"❌ خطای Worker: {tb}")
        self.update_status("error")
        self.update_ui_state()
        self.show_error("عملیات ناموفق", f"خطایی در حین انجام عملیات رخ داد:\n{tb}")
        self.client = None

    def start_polling(self):
        if not self.client:
            self.show_error("عدم اتصال", "لطفاً قبل از شروع، به سرور متصل شوید.")
            return
        interval_ms = self.poll_interval_spinbox.value() * 1000
        self.poll_timer.start(interval_ms)
        self.log(f"▶ بررسی خودکار هر {self.poll_interval_spinbox.value()} ثانیه یک‌بار آغاز شد.")
        self.update_ui_state(is_connected=True, is_polling=True)

    def stop_polling(self):
        self.poll_timer.stop()
        self.log("⏹ بررسی خودکار توسط کاربر متوقف شد.")
        self.update_status("connected")
        self.update_ui_state(is_connected=True)

    def check_orders(self):
        try:
            new_orders = self.client.get_new_orders()
            if not new_orders:
                self.log("سفارش جدیدی یافت نشد.")
                return
            self.log(f"📥 {len(new_orders)} سفارش جدید یافت شد.")
            printer_name = self.printer_select.currentText()
            printer_caps = get_printer_capabilities(printer_name)
            for order in new_orders:
                self.log(f"--- شروع پردازش سفارش شماره #{order.get('id', 'N/A')} ---")
                is_color_order = order.get('color') == 'ColorFull'
                if is_color_order and not printer_caps['is_color']:
                    self.log(f"⚠️ هشدار: سفارش #{order['id']} رنگی است، اما پرینتر '{printer_name}' سیاه‌وسفید است. از این سفارش صرف نظر می‌شود.")
                    continue
                file_id = order.get('file_id')
                if not file_id:
                    self.log(f"خطا: سفارش #{order['id']} شناسه فایل ندارد.")
                    continue
                downloaded_file_path = self.client.download_telegram_file(file_id, order['id'])
                if downloaded_file_path:
                    print_file_with_settings(file_path=downloaded_file_path, printer_name=printer_name, settings=order)
                    self.log(f"✅ سفارش #{order['id']} با موفقیت به پرینتر ارسال شد.")
                    # self.client.update_order_status(order['id'], 'completed')
                    self.log(f"وضعیت سفارش #{order['id']} در سرور به‌روز شد.")
                    self.run_fetch_orders_worker()
        except Exception as e:
            self.log(f"❌ خطای کلی در پردازش سفارشات: {e}")
            self.show_error("خطا در پردازش سفارش", f"مشکلی در چرخه اصلی پردازش سفارشات به وجود آمد.\nخطا: {e}")
            self.stop_polling()

    def update_ui_state(self, is_connected=False, is_polling=False, is_connecting=False, is_loading_data=False):
        is_busy = is_polling or is_connecting or is_loading_data
        if is_connecting:
            self.update_status("connecting")
        elif is_loading_data:
            self.update_status("loading")
        if is_busy:
            self.loading_spinner.show()
            self.status_label.hide()
        else:
            self.loading_spinner.hide()
            self.status_label.show()
        self.api_input.setEnabled(not is_busy)
        self.connect_button.setEnabled(not is_busy)
        self.printer_select.setEnabled(is_connected and not is_busy)
        self.poll_interval_spinbox.setEnabled(is_connected and not is_busy)
        self.start_button.setEnabled(is_connected and not is_busy)
        self.stop_button.setEnabled(is_connected and is_polling)
        self.refresh_button.setEnabled(is_connected and not is_busy)

    def update_status(self, status_key: str):
        message, color_hex = self.STATUS_MESSAGES.get(status_key, ("نامشخص", "black"))
        palette = self.status_label.palette()
        palette.setColor(self.status_label.foregroundRole(), QColor(color_hex))
        self.status_label.setPalette(palette)
        self.status_label.setText(f"<b>{message}</b>")
        self.status_bar.showMessage(message)

    def log(self, message: str):
        from datetime import datetime
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
        self.log_area.verticalScrollBar().setValue(self.log_area.verticalScrollBar().maximum())

    def show_error(self, title: str, message: str):
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle(title)
        msg_box.setText(message)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        msg_box.exec()

    def get_available_printers(self):
        try:
            import win32print
            printers = [printer[2] for printer in win32print.EnumPrinters(2)]
            return printers if printers else ["هیچ پرینتری یافت نشد"]
        except Exception as e:
            return ["خطا در دریافت لیست"]



    def closeEvent(self, event):
        if self.poll_timer.isActive():
            msg_box = QMessageBox(self)
            msg_box.setIcon(QMessageBox.Icon.Question)
            msg_box.setWindowTitle("تایید خروج")
            msg_box.setText("برنامه در حال بررسی سفارشات است. آیا از خروج اطمینان دارید؟")
            msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            msg_box.setDefaultButton(QMessageBox.StandardButton.No)
            msg_box.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            reply = msg_box.exec()
            if reply == QMessageBox.StandardButton.Yes:
                self.stop_polling()
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()