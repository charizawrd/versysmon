"""
Versysmon - Main User Interface

This module initializes the main PyQt6 application, sets up the dynamic 
dashboard grid, and handles all front-end routing between the CPU, RAM, 
Network, Disk, and Battery detail views. It manages UI state, smooth 
window animations, and the global background update timers.
"""
import sys
import sqlite3
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QTableWidget, 
                             QPushButton, QDateEdit, QHeaderView, QTableWidgetItem,
                             QStackedWidget, QDoubleSpinBox, QComboBox, 
                             QSystemTrayIcon, QStyle, QGridLayout, QProgressBar,
                             QMenu)
from PyQt6.QtGui import QAction, QIcon, QPixmap, QColor
from PyQt6.QtCore import Qt, QTimer, QDate, QSharedMemory, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve
import pywinstyles

import styles
from sys_logic import (get_sys_stats, get_detailed_ram, get_top_ram_hogs, kill_process, clean_memory,
                       DiskTracker, get_disk_partitions, get_battery_info, get_system_info)
from net_logic import NetTracker, AppTrackerThread, get_adapter_info
from db_logic import DB_NAME


class RamWorkerThread(QThread):
    """Background thread that fetches RAM data without freezing the UI."""
    result_ready = pyqtSignal(dict, list)

    def run(self):
        try:
            ram_data = get_detailed_ram()
            hogs = get_top_ram_hogs()
            self.result_ready.emit(ram_data, hogs)
        except Exception:
            pass

class StatCard(QFrame):
    """Standard card for CPU & RAM"""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setStyleSheet(styles.CARD_STYLE)
        layout = QVBoxLayout(self)
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #888888;")
        self.val_lbl = QLabel("0")
        self.val_lbl.setStyleSheet("font-size: 28px; font-weight: bold; color: #ffffff;")
        self.val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_lbl)
        layout.addStretch()
        layout.addWidget(self.val_lbl)
        layout.addStretch()

class Versysmon(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("versysmon")
        self.setFixedSize(1050, 275)
        self.expanded = False
        self.net_tracker = NetTracker()
        self.disk_tracker = DiskTracker()
        
        self.setStyleSheet(styles.WINDOW_STYLE)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.dash_layout = QHBoxLayout()
        
        self.cpu_card = QFrame()
        self.cpu_card.setStyleSheet(styles.CARD_STYLE)
        self.cpu_card.setFixedHeight(200)
        cpu_vbox = QVBoxLayout(self.cpu_card)
        
        cpu_title = QLabel("CPU")
        cpu_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #888888;")
        self.cpu_val_lbl = QLabel("0%")
        self.cpu_val_lbl.setStyleSheet("font-size: 28px; font-weight: bold; color: #ffffff;")
        self.cpu_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.cpu_footer = QLabel(" ")
        self.cpu_footer.setStyleSheet("font-size: 12px; font-weight: bold; color: transparent;")
        
        cpu_btn_layout = QHBoxLayout()
        self.btn_cpu_expand = QPushButton("Details")
        self.btn_cpu_expand.setStyleSheet(styles.BUTTON_STYLE)
        self.btn_cpu_expand.setCursor(Qt.CursorShape.PointingHandCursor)
        cpu_btn_layout.addWidget(self.btn_cpu_expand)
        
        cpu_vbox.addWidget(cpu_title)
        cpu_vbox.addStretch()
        cpu_vbox.addWidget(self.cpu_val_lbl)
        cpu_vbox.addStretch()
        cpu_vbox.addWidget(self.cpu_footer)
        cpu_vbox.addLayout(cpu_btn_layout)
                                  
        self.ram_card = QFrame()
        self.ram_card.setStyleSheet(styles.CARD_STYLE)
        self.ram_card.setFixedHeight(200)
        ram_vbox = QVBoxLayout(self.ram_card)
        
        ram_title = QLabel("RAM")
        ram_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #888888;")
        self.ram_val_lbl = QLabel("0 / 0 GB")
        self.ram_val_lbl.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff;") 
        self.ram_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.ram_footer = QLabel(" ")
        self.ram_footer.setStyleSheet("font-size: 12px; font-weight: bold; color: transparent;")
        
        ram_btn_layout = QHBoxLayout()
        self.btn_ram_manage = QPushButton("Manage")
        self.btn_ram_manage.setStyleSheet(styles.BUTTON_STYLE)
        self.btn_ram_manage.setCursor(Qt.CursorShape.PointingHandCursor)
        ram_btn_layout.addWidget(self.btn_ram_manage)
        
        ram_vbox.addWidget(ram_title)
        ram_vbox.addStretch()
        ram_vbox.addWidget(self.ram_val_lbl)
        ram_vbox.addStretch()
        ram_vbox.addWidget(self.ram_footer)
        ram_vbox.addLayout(ram_btn_layout)
        
        self.net_card = QFrame()
        self.net_card.setStyleSheet(styles.CARD_STYLE)
        net_vbox = QVBoxLayout(self.net_card)

        self.cpu_card.setFixedHeight(200)
        self.ram_card.setFixedHeight(200)
        self.net_card.setFixedHeight(200)
        
        net_title = QLabel("NETWORK")
        net_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #888888;")
        self.up_lbl = QLabel("↑ 0.00 MB/s")
        self.up_lbl.setStyleSheet("font-size: 18px; color: #4CAF50; font-weight: bold;")
        self.down_lbl = QLabel("↓ 0.00 MB/s")
        self.down_lbl.setStyleSheet("font-size: 18px; color: #2196F3; font-weight: bold;")
        
        btn_layout = QHBoxLayout()
        self.btn_info = QPushButton("Info")
        self.btn_usage = QPushButton("Usage per app")
        
        for btn in [self.btn_info, self.btn_usage]:
            btn.setStyleSheet(styles.BUTTON_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn_layout.addWidget(btn)
            
        self.net_today_footer = QLabel("Today: 0.00 MB")
        self.net_today_footer.setStyleSheet("font-size: 12px; font-weight: bold; color: #a0a0a0;")
        self.net_today_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        net_vbox.addWidget(net_title)
        net_vbox.addStretch()
        net_vbox.addWidget(self.up_lbl)
        net_vbox.addWidget(self.down_lbl)
        net_vbox.addStretch()
        net_vbox.addWidget(self.net_today_footer)
        net_vbox.addLayout(btn_layout)
        
        self.disk_card = QFrame()
        self.disk_card.setStyleSheet(styles.CARD_STYLE)
        self.disk_card.setFixedHeight(200)
        disk_vbox = QVBoxLayout(self.disk_card)
        
        disk_title = QLabel("DISK")
        disk_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #888888;")
        self.disk_read_lbl = QLabel("R: 0.00 MB/s")
        self.disk_read_lbl.setStyleSheet("font-size: 18px; color: #4CAF50; font-weight: bold;")
        self.disk_write_lbl = QLabel("W: 0.00 MB/s")
        self.disk_write_lbl.setStyleSheet("font-size: 18px; color: #FF9800; font-weight: bold;")
        
        self.disk_footer = QLabel(" ")
        self.disk_footer.setStyleSheet("font-size: 12px; font-weight: bold; color: transparent;")
        self.disk_footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        disk_btn_layout = QHBoxLayout()
        self.btn_disk_details = QPushButton("Details")
        self.btn_disk_details.setStyleSheet(styles.BUTTON_STYLE)
        self.btn_disk_details.setCursor(Qt.CursorShape.PointingHandCursor)
        disk_btn_layout.addWidget(self.btn_disk_details)
        
        disk_vbox.addWidget(disk_title)
        disk_vbox.addStretch()
        disk_vbox.addWidget(self.disk_read_lbl)
        disk_vbox.addWidget(self.disk_write_lbl)
        disk_vbox.addStretch()
        disk_vbox.addWidget(self.disk_footer)
        disk_vbox.addLayout(disk_btn_layout)
        
        self.bat_card = QFrame()
        self.bat_card.setStyleSheet(styles.CARD_STYLE)
        self.bat_card.setFixedHeight(200)
        bat_vbox = QVBoxLayout(self.bat_card)
        
        bat_title = QLabel("BATTERY")
        bat_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #888888;")
        self.bat_icon_lbl = QLabel("🔋")
        self.bat_icon_lbl.setStyleSheet("font-size: 28px; background: transparent;")
        self.bat_icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bat_val_lbl = QLabel("--")
        self.bat_val_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff;")
        self.bat_val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bat_status_lbl = QLabel("")
        self.bat_status_lbl.setStyleSheet("font-size: 12px; color: #a0a0a0;")
        self.bat_status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        bat_btn_layout = QHBoxLayout()
        self.btn_bat_details = QPushButton("Details")
        self.btn_bat_details.setStyleSheet(styles.BUTTON_STYLE)
        self.btn_bat_details.setCursor(Qt.CursorShape.PointingHandCursor)
        bat_btn_layout.addWidget(self.btn_bat_details)
        
        bat_vbox.addWidget(bat_title)
        bat_vbox.addStretch()
        bat_vbox.addWidget(self.bat_icon_lbl)
        bat_vbox.addWidget(self.bat_val_lbl)
        bat_vbox.addStretch()
        bat_vbox.addWidget(self.bat_status_lbl)
        bat_vbox.addLayout(bat_btn_layout)
        
        self.dash_layout.addWidget(self.cpu_card)
        self.dash_layout.addWidget(self.ram_card)
        self.dash_layout.addWidget(self.net_card)
        self.dash_layout.addWidget(self.disk_card)
        self.dash_layout.addWidget(self.bat_card)
        self.main_layout.addLayout(self.dash_layout)
             
        self.status_bar_widget = QFrame()
        self.status_bar_widget.setStyleSheet(styles.STATUS_BAR_STYLE)
        self.status_bar_widget.setFixedHeight(28)
        status_bar_layout = QHBoxLayout(self.status_bar_widget)
        status_bar_layout.setContentsMargins(10, 0, 10, 0)
        
        self.uptime_lbl = QLabel("⏱ Up: --")
        self.uptime_lbl.setStyleSheet("font-size: 11px; color: #a0a0a0; font-weight: bold;")
        self.proc_count_lbl = QLabel("📊 -- processes")
        self.proc_count_lbl.setStyleSheet("font-size: 11px; color: #a0a0a0; font-weight: bold;")
        self.boot_time_lbl = QLabel("🖥 Booted: --")
        self.boot_time_lbl.setStyleSheet("font-size: 11px; color: #a0a0a0; font-weight: bold;")
        
        sep1 = QLabel("•")
        sep1.setStyleSheet("font-size: 11px; color: #555555;")
        sep2 = QLabel("•")
        sep2.setStyleSheet("font-size: 11px; color: #555555;")
        
        status_bar_layout.addStretch()
        status_bar_layout.addWidget(self.uptime_lbl)
        status_bar_layout.addWidget(sep1)
        status_bar_layout.addWidget(self.proc_count_lbl)
        status_bar_layout.addWidget(sep2)
        status_bar_layout.addWidget(self.boot_time_lbl)
        status_bar_layout.addStretch()
        
        self.main_layout.addWidget(self.status_bar_widget)
        
        self.details = QFrame()
        detail_layout = QVBoxLayout(self.details)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QStackedWidget()
        detail_layout.addWidget(self.stack)
            
        self.usage_widget = QWidget()
        usage_layout = QVBoxLayout(self.usage_widget)
        
        self.total_usage_lbl = QLabel("Total Usage: 0.00 MB")
        self.total_usage_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        
        top_usage_row = QHBoxLayout()
        self.total_usage_lbl = QLabel("Total Usage: 0.00 MB")
        self.total_usage_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
                   
        self.warning_lbl = QLabel("⚠️ Limit Reached!")
        self.warning_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #ff4444;")
        self.warning_lbl.hide()
        
        self.btn_set_limit = QPushButton("Set Data Limit")
        self.btn_set_limit.setStyleSheet(styles.BUTTON_STYLE)
        self.btn_set_limit.setCursor(Qt.CursorShape.PointingHandCursor)
             
        self.limit_container = QWidget()
        limit_layout = QHBoxLayout(self.limit_container)
        limit_layout.setContentsMargins(0, 0, 0, 0)
        
        self.limit_spin = QDoubleSpinBox()
        self.limit_spin.setRange(0.1, 9999.0)
        self.limit_spin.setValue(1.5)
        self.limit_spin.setStyleSheet(styles.DATE_EDIT_STYLE)                       
        
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["MB", "GB"])
        self.limit_combo.setStyleSheet(styles.DATE_EDIT_STYLE)
        
        self.btn_apply_limit = QPushButton("✓")
        self.btn_apply_limit.setStyleSheet(styles.BUTTON_STYLE)
        self.btn_apply_limit.setCursor(Qt.CursorShape.PointingHandCursor)
        
        limit_layout.addWidget(self.limit_spin)
        limit_layout.addWidget(self.limit_combo)
        limit_layout.addWidget(self.btn_apply_limit)
        self.limit_container.hide()

        top_usage_row.addWidget(self.total_usage_lbl)
        top_usage_row.addStretch()                                             
        top_usage_row.addWidget(self.warning_lbl)
        top_usage_row.addWidget(self.limit_container)
        top_usage_row.addWidget(self.btn_set_limit)
        
        usage_layout.addLayout(top_usage_row)
                 
        self.daily_limit_bytes = None
        self.limit_notified = False
        
        self.tray = QSystemTrayIcon(self)

        tray_pixmap = QPixmap(64, 64)
        tray_pixmap.fill(QColor("#2196F3"))                 
        self.tray.setIcon(QIcon(tray_pixmap))
        
        self.tray_menu = QMenu()
        self.action_show = QAction("Open Versysmon")
        self.action_quit = QAction("Quit")
        
        self.action_show.triggered.connect(self.show_window)
        self.action_quit.triggered.connect(self.quit_app)
        
        self.tray_menu.addAction(self.action_show)
        self.tray_menu.addSeparator()
        self.tray_menu.addAction(self.action_quit)
        
        self.tray.setContextMenu(self.tray_menu)
        
        self.tray.activated.connect(self.tray_icon_clicked)
        self.tray.show()
        
        controls_layout = QHBoxLayout()
        self.btn_today = QPushButton("Today")
        self.btn_yesterday = QPushButton("Yesterday")
        self.btn_month = QPushButton("This Month")
        self.btn_last_month = QPushButton("Last Month")
        self.btn_custom = QPushButton("Custom Range")
        
        for btn in [self.btn_today, self.btn_yesterday, self.btn_month, self.btn_last_month, self.btn_custom]:
            btn.setStyleSheet(styles.BUTTON_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            controls_layout.addWidget(btn)
        
        self.date_container = QWidget()
        date_layout = QHBoxLayout(self.date_container)
        date_layout.setContentsMargins(10, 0, 0, 0)
        
        self.date_from = QDateEdit(QDate.currentDate())
        self.date_from.setCalendarPopup(True)
        self.date_from.setStyleSheet(styles.DATE_EDIT_STYLE)
        
        self.date_to = QDateEdit(QDate.currentDate())
        self.date_to.setCalendarPopup(True)
        self.date_to.setStyleSheet(styles.DATE_EDIT_STYLE)
        
        self.btn_submit_range = QPushButton("✓ Apply")
        self.btn_submit_range.setStyleSheet(styles.BUTTON_STYLE)
        self.btn_submit_range.setCursor(Qt.CursorShape.PointingHandCursor)
        
        date_layout.addWidget(QLabel("From:", styleSheet="color: #a0a0a0;"))
        date_layout.addWidget(self.date_from)
        date_layout.addWidget(QLabel("To:", styleSheet="color: #a0a0a0;"))
        date_layout.addWidget(self.date_to)
        date_layout.addWidget(self.btn_submit_range)
        
        self.date_container.hide() 
        controls_layout.addWidget(self.date_container)
        controls_layout.addStretch() 
        usage_layout.addLayout(controls_layout)
        
        self.table = QTableWidget(0, 3) 
        self.table.setHorizontalHeaderLabels(["App", "Usage", "Date"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(styles.DETAIL_STYLE)
        self.table.setAlternatingRowColors(True)
        self.table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)
        usage_layout.addWidget(self.table)
        
        self.stack.addWidget(self.usage_widget)                          

        self.info_widget = QWidget()
        self.info_layout = QVBoxLayout(self.info_widget)
        self.info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.stack.addWidget(self.info_widget)                          

        self.main_layout.addWidget(self.details)
        self.details.hide()

        self.ram_widget = QWidget()
        ram_layout = QVBoxLayout(self.ram_widget)
        
        ram_top_row = QHBoxLayout()
        ram_header = QLabel("Top Memory Hogs")
        ram_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        
        self.btn_mem_reduct = QPushButton("🧹 Clean Memory")
        self.btn_mem_reduct.setStyleSheet("""
            QPushButton { background-color: rgba(33, 150, 243, 40); color: #64B5F6; 
            border: 1px solid rgba(33, 150, 243, 60); border-radius: 6px; padding: 6px 12px; font-weight: bold; }
            QPushButton:hover { background-color: rgba(33, 150, 243, 60); }
        """)
        self.btn_mem_reduct.setCursor(Qt.CursorShape.PointingHandCursor)
        
        ram_top_row.addWidget(ram_header)
        ram_top_row.addStretch()
        ram_top_row.addWidget(self.btn_mem_reduct)
        ram_layout.addLayout(ram_top_row)
        
        self.ram_bar_layout = QHBoxLayout()
        self.ram_bar_layout.setSpacing(0)
        
        bar_text_style = "color: #ffffff; font-size: 11px; font-weight: bold;"

        self.bar_used = QLabel()
        self.bar_used.setStyleSheet(f"background-color: #ff5252; {bar_text_style} border-top-left-radius: 4px; border-bottom-left-radius: 4px;")
        self.bar_used.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.bar_cached = QLabel()
        self.bar_cached.setStyleSheet(f"background-color: #ffd600; {bar_text_style} color: #000000;")                            
        self.bar_cached.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.bar_free = QLabel()
        self.bar_free.setStyleSheet(f"background-color: #4CAF50; {bar_text_style} border-top-right-radius: 4px; border-bottom-right-radius: 4px;")
        self.bar_free.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.bar_used.setFixedHeight(18)
        self.bar_cached.setFixedHeight(18)
        self.bar_free.setFixedHeight(18)
        
        self.ram_bar_layout.addWidget(self.bar_used)
        self.ram_bar_layout.addWidget(self.bar_cached)
        self.ram_bar_layout.addWidget(self.bar_free)
        ram_layout.addLayout(self.ram_bar_layout)
        
        legend = QLabel("🔴 In Use   🟡 Cached / Standby   🟢 Free")
        legend.setStyleSheet("font-size: 11px; color: #a0a0a0; margin-bottom: 5px;")
        ram_layout.addWidget(legend)
        
        self.ram_table = QTableWidget(0, 4)
        self.ram_table.setHorizontalHeaderLabels(["App Name", "PID", "RAM Usage", "Action"])
        self.ram_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.ram_table.setStyleSheet(styles.DETAIL_STYLE)
        self.ram_table.setAlternatingRowColors(True)
        self.ram_table.setVerticalScrollMode(QTableWidget.ScrollMode.ScrollPerPixel)                    
        ram_layout.addWidget(self.ram_table)
        
        self.stack.addWidget(self.ram_widget)                          
        
        self._ram_worker = None
        self._pending_kill_pids = set()                                              

        self.cpu_widget = QWidget()
        cpu_layout = QVBoxLayout(self.cpu_widget)
        cpu_layout.setContentsMargins(0, 25, 0, 0)

        cpu_btn_row = QHBoxLayout()
        self.btn_cpu_info = QPushButton("Hardware Info")
        self.btn_cpu_usage = QPushButton("Per-Core Usage")
        
        for btn in [self.btn_cpu_info, self.btn_cpu_usage]:
            btn.setStyleSheet(styles.BUTTON_STYLE)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            cpu_btn_row.addWidget(btn)
        cpu_btn_row.addStretch()
        cpu_layout.addLayout(cpu_btn_row)
        
        self.cpu_stack = QStackedWidget()
        cpu_layout.addWidget(self.cpu_stack)
        
        self.cpu_info_widget = QWidget()
        self.cpu_info_layout = QVBoxLayout(self.cpu_info_widget)
        self.cpu_info_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.cpu_stack.addWidget(self.cpu_info_widget)
        
        self.cpu_usage_widget = QWidget()
        self.cpu_usage_layout = QGridLayout(self.cpu_usage_widget) 
        self.cpu_usage_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.core_bars = []                                            
        self.cpu_stack.addWidget(self.cpu_usage_widget)
        
        self.stack.addWidget(self.cpu_widget)                               

        self.disk_detail_widget = QWidget()
        disk_detail_layout = QVBoxLayout(self.disk_detail_widget)
        disk_detail_layout.setContentsMargins(0, 15, 0, 0)
        
        disk_header = QLabel("Storage Partitions")
        disk_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        disk_detail_layout.addWidget(disk_header)
        
        self.disk_bars_layout = QVBoxLayout()
        disk_detail_layout.addLayout(self.disk_bars_layout)
        disk_detail_layout.addStretch()
        
        self.stack.addWidget(self.disk_detail_widget)                               

        self.bat_detail_widget = QWidget()
        bat_detail_layout = QVBoxLayout(self.bat_detail_widget)
        bat_detail_layout.setContentsMargins(0, 15, 0, 0)
        
        bat_header = QLabel("Battery & Power Info")
        bat_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        bat_detail_layout.addWidget(bat_header)
        
        self.bat_info_layout = QVBoxLayout()
        bat_detail_layout.addLayout(self.bat_info_layout)
        bat_detail_layout.addStretch()
        
        self.stack.addWidget(self.bat_detail_widget)                               

        self.btn_usage.clicked.connect(lambda: self.toggle_view(0))
        self.btn_info.clicked.connect(lambda: self.toggle_view(1))

        self.btn_custom.clicked.connect(self.toggle_custom_dates)
        self.btn_today.clicked.connect(lambda: self.load_data("Today"))
        self.btn_yesterday.clicked.connect(lambda: self.load_data("Yesterday"))
        self.btn_month.clicked.connect(lambda: self.load_data("This Month"))
        self.btn_last_month.clicked.connect(lambda: self.load_data("Last Month"))
        self.btn_submit_range.clicked.connect(self.apply_custom_range)
        self.btn_set_limit.clicked.connect(self.toggle_limit_input)
        self.btn_apply_limit.clicked.connect(self.apply_data_limit)

        self.btn_ram_manage.clicked.connect(lambda: self.toggle_view(2))               
        self.btn_mem_reduct.clicked.connect(self.trigger_mem_reduct)
                               
        self.btn_cpu_expand.clicked.connect(lambda: self.toggle_view(3))
        self.btn_disk_details.clicked.connect(lambda: self.toggle_view(4))
        self.btn_bat_details.clicked.connect(lambda: self.toggle_view(5))
        
                              
        self.btn_cpu_info.clicked.connect(lambda: self.switch_cpu_tab(0))
        self.btn_cpu_usage.clicked.connect(lambda: self.switch_cpu_tab(1))

        self.bg_tracker = AppTrackerThread()
        self.bg_tracker.start()
        
        self.load_data("Today")

                                                          
        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
         
        self.ram_timer = QTimer()
        self.ram_timer.timeout.connect(self.refresh_ram_page)
        
        self._height_anim = QPropertyAnimation(self, b"minimumHeight")
        self._height_anim.setDuration(200)
        self._height_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._width_anim = QPropertyAnimation(self, b"maximumHeight")
        self._width_anim.setDuration(200)
        self._width_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def populate_adapter_info(self):
        """Builds the UI cards for active network adapters."""
        
        while self.info_layout.count():
            item = self.info_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
                
        title = QLabel("Active Network Adapters")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff; margin-bottom: 10px;")
        self.info_layout.addWidget(title)
        
        adapters = get_adapter_info()
        
        if not adapters:
            no_lbl = QLabel("No active adapters found.")
            no_lbl.setStyleSheet("color: #a0a0a0;")
            self.info_layout.addWidget(no_lbl)
            return

        for adp in adapters:
            card = QFrame()
            card.setStyleSheet(styles.CARD_STYLE)
            card.setMinimumHeight(100)
            card_layout = QVBoxLayout(card)
            
                                  
            name_lbl = QLabel(adp["name"])
            name_lbl.setStyleSheet("font-size: 14px; font-weight: bold; color: #2196F3;")
            card_layout.addWidget(name_lbl)
            
                                                                           
            if adp["wifi"]:
                w = adp["wifi"]
                ssid = w.get("ssid", "Unknown")
                band = w.get("band", "")
                radio = w.get("radio", "")
                
                wifi_str = f"Network: {ssid}"
                if band or radio:
                    wifi_str += f"  ({band} - {radio})"
                    
                wifi_lbl = QLabel(wifi_str)
                wifi_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #4CAF50;")                       
                card_layout.addWidget(wifi_lbl)
            
                              
            ip_lbl = QLabel(f"IPv4: {adp['ipv4']}")
            ip_lbl.setStyleSheet("font-size: 13px; color: #e0e0e0;")
            
            mac_lbl = QLabel(f"MAC: {adp['mac']}")
            mac_lbl.setStyleSheet("font-size: 12px; color: #888888;")
            
            card_layout.addWidget(ip_lbl)
            card_layout.addWidget(mac_lbl)
            
            self.info_layout.addWidget(card)
            
        self.info_layout.addStretch()

    def toggle_view(self, page_index):
        """Expands/contracts the window and flips to the correct page."""
        if self.expanded and self.stack.currentIndex() == page_index:
                                                    
            self.expanded = False
            self.details.hide()
            self._manage_ram_timer()
            self.adjust_window_height()
        else:
                                    
            self.stack.setCurrentIndex(page_index)
            
            if page_index == 1:
                self.populate_adapter_info()
                                           
            if page_index == 2:
                self.refresh_ram_page()
                      
            if page_index == 4:
                self.refresh_disk_page()
 
            if page_index == 5:
                self.refresh_bat_page()
                
            self.expanded = True
            self.details.show()
            self._manage_ram_timer()
            self.adjust_window_height()

    def _manage_ram_timer(self):
        """Start/stop the RAM timer based on whether the RAM tab is active."""
        if self.expanded and self.stack.currentIndex() == 2:
            if not self.ram_timer.isActive():
                self.ram_timer.start(2500)
        else:
            self.ram_timer.stop()
    
    def switch_cpu_tab(self, index):
        """Changes the CPU sub-page and forces a window resize."""
        self.cpu_stack.setCurrentIndex(index)
        self.adjust_window_height()

    def toggle_custom_dates(self):
        if self.date_container.isHidden():
            self.date_container.show()
        else:
            self.date_container.hide()

    def refresh(self):
        stats = get_sys_stats()
        self.cpu_val_lbl.setText(f"{stats['cpu_perc']}%")
        self.refresh_cpu_page(stats['cpu_perc'])
        self.ram_val_lbl.setText(f"{stats['ram_gb']:.1f} / {stats['ram_total_gb']:.1f} GB")
        
                               
        up, down = self.net_tracker.get_speeds()
        self.up_lbl.setText(f"↑ {up:.2f} MB/s")
        self.down_lbl.setText(f"↓ {down:.2f} MB/s")
                        
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(bytes_used) FROM app_network_logs WHERE log_date=?", (today,))
            total = cursor.fetchone()[0]
            conn.close()
            
            if total is not None:
                mb = total / (1024 * 1024)
                self.net_today_footer.setText(f"Today: {mb:.2f} MB")
                
                                              
                if self.daily_limit_bytes and total >= self.daily_limit_bytes:
                    self.warning_lbl.show()
                                                                  
                    if not self.limit_notified:
                        self.tray.showMessage(
                            "versysmon Alert", 
                            "⚠️ Daily data limit reached!", 
                            QSystemTrayIcon.MessageIcon.Warning, 
                            5000                      
                        )
                        self.limit_notified = True
                elif self.daily_limit_bytes and total < self.daily_limit_bytes:
                                                                   
                    self.warning_lbl.hide()
                    self.limit_notified = False
            else:
                self.net_today_footer.setText("Today: 0.00 MB")
                
        except sqlite3.OperationalError:
            pass

        read_speed, write_speed = self.disk_tracker.get_speeds()
        self.disk_read_lbl.setText(f"R: {read_speed:.2f} MB/s")
        self.disk_write_lbl.setText(f"W: {write_speed:.2f} MB/s")
       
        bat_info = get_battery_info()
        if bat_info:
            pct = bat_info["percent"]
            plugged = bat_info["plugged"]
            if pct > 60:
                color = "#4CAF50"
            elif pct > 20:
                color = "#FF9800"
            else:
                color = "#ff5252"
            icon = "🔌" if plugged else "🔋"
            self.bat_icon_lbl.setText(icon)
            self.bat_val_lbl.setText(f"{pct:.0f}%")
            self.bat_val_lbl.setStyleSheet(f"font-size: 22px; font-weight: bold; color: {color};")
            if plugged:
                self.bat_status_lbl.setText("Charging" if pct < 100 else "Full")
            elif bat_info["secs_left"] > 0:
                hrs = bat_info["secs_left"] // 3600
                mins = (bat_info["secs_left"] % 3600) // 60
                self.bat_status_lbl.setText(f"{int(hrs)}h {int(mins)}m left")
            else:
                self.bat_status_lbl.setText("Discharging")
        else:
            self.bat_icon_lbl.setText("🖥")
            self.bat_val_lbl.setText("N/A")
            self.bat_val_lbl.setStyleSheet("font-size: 22px; font-weight: bold; color: #888888;")
            self.bat_status_lbl.setText("No Battery")
            self.btn_bat_details.hide()

                              
        sys_info = get_system_info()
        self.uptime_lbl.setText(f"⏱ Up: {sys_info['uptime_str']}")
        self.proc_count_lbl.setText(f"📊 {sys_info['process_count']} processes")
        self.boot_time_lbl.setText(f"🖥 Booted: {sys_info['boot_time']}")

                              
    def load_data(self, filter_type, start_date=None, end_date=None):
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            today_str = datetime.now().strftime("%Y-%m-%d")
            query_date_label = ""
            
            if filter_type == "Today":
                query = "SELECT app_name, SUM(bytes_used), log_date FROM app_network_logs WHERE log_date=? GROUP BY app_name ORDER BY SUM(bytes_used) DESC"
                params = (today_str,)
                query_date_label = "Today"
                
            elif filter_type == "Yesterday":
                yesterday_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
                query = "SELECT app_name, SUM(bytes_used), log_date FROM app_network_logs WHERE log_date=? GROUP BY app_name ORDER BY SUM(bytes_used) DESC"
                params = (yesterday_str,)
                query_date_label = "Yesterday"
                
            elif filter_type == "This Month":
                month_str = datetime.now().strftime("%Y-%m")
                query = "SELECT app_name, SUM(bytes_used), 'This Month' FROM app_network_logs WHERE log_date LIKE ? GROUP BY app_name ORDER BY SUM(bytes_used) DESC"
                params = (f"{month_str}-%",)
                query_date_label = "This Month"
                
            elif filter_type == "Last Month":
                first_day = datetime.now().replace(day=1)
                last_month_str = (first_day - timedelta(days=1)).strftime("%Y-%m")
                query = "SELECT app_name, SUM(bytes_used), 'Last Month' FROM app_network_logs WHERE log_date LIKE ? GROUP BY app_name ORDER BY SUM(bytes_used) DESC"
                params = (f"{last_month_str}-%",)
                query_date_label = "Last Month"
                
            elif filter_type == "Custom Range":
                query = "SELECT app_name, SUM(bytes_used), ? FROM app_network_logs WHERE log_date BETWEEN ? AND ? GROUP BY app_name ORDER BY SUM(bytes_used) DESC"
                date_range_str = f"{start_date} to {end_date}"
                params = (date_range_str, start_date, end_date)
                query_date_label = date_range_str

            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()

            total_bytes = sum(row[1] for row in rows) if rows else 0
            total_mb = total_bytes / (1024 * 1024)
            self.total_usage_lbl.setText(f"Total Usage ({query_date_label}): {total_mb:.2f} MB")

            self.table.setRowCount(0) 
            for row_idx, row_data in enumerate(rows):
                self.table.insertRow(row_idx)
                app_name, bytes_used, date_val = row_data
                mb_used = bytes_used / (1024 * 1024)
                
                item_app = QTableWidgetItem(app_name)
                item_usage = QTableWidgetItem(f"{mb_used:.2f} MB")
                item_date = QTableWidgetItem(date_val)
                
                item_usage.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item_date.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                
                self.table.setItem(row_idx, 0, item_app)
                self.table.setItem(row_idx, 1, item_usage)
                self.table.setItem(row_idx, 2, item_date)
                
        except sqlite3.OperationalError:
            pass 

    def apply_custom_range(self):
        start_date = self.date_from.date().toString("yyyy-MM-dd") 
        end_date = self.date_to.date().toString("yyyy-MM-dd")     
        self.load_data("Custom Range", start_date, end_date)

    def toggle_limit_input(self):
        """Shows the MB/GB dropdowns and hides the Set Limit button."""
        self.btn_set_limit.hide()
        self.limit_container.show()

    def apply_data_limit(self):
        """Converts the input to bytes and sets the tracker limit."""
        val = self.limit_spin.value()
        unit = self.limit_combo.currentText()
        
        if unit == "MB":
            self.daily_limit_bytes = val * 1024 * 1024
        else:
            self.daily_limit_bytes = val * 1024 * 1024 * 1024
            
        self.limit_notified = False                            
        
                                                    
        self.limit_container.hide()
        self.btn_set_limit.setText(f"Limit: {val} {unit}")
        self.btn_set_limit.show()

    def trigger_mem_reduct(self):
        """Fires the Windows API sweep and updates the button text."""
        freed = clean_memory()
        self.btn_mem_reduct.setText(f"✓ Swept {freed} Apps")
        QTimer.singleShot(3000, lambda: self.btn_mem_reduct.setText("🧹 Clean Memory"))

    def handle_kill_process(self, pid, app_name):
        """Triggered when the red X is clicked in the RAM table."""
        self._pending_kill_pids.add(pid)
        success = kill_process(pid)
        if success:
                                                                            
            for row in range(self.ram_table.rowCount()):
                item = self.ram_table.item(row, 1)
                if item and int(item.text()) == pid:
                    self.ram_table.removeRow(row)
                    break

    def refresh_ram_page(self):
        """Dispatches the heavy work to a background thread."""
        if self.stack.currentIndex() != 2 or not self.expanded:
            return
        
                               
        if self._ram_worker is not None and self._ram_worker.isRunning():
            return
        
        self._ram_worker = RamWorkerThread()
        self._ram_worker.result_ready.connect(self._apply_ram_data)
        self._ram_worker.start()

    def _apply_ram_data(self, ram_data, hogs):
        """Applies fetched RAM data to the UI — runs on the main thread."""
                                          
        total = ram_data["total"]
        if total <= 0:
            return
        
        used_gb = ram_data["used"] / (1024**3)
        cached_gb = ram_data["cached"] / (1024**3)
        free_gb = ram_data["free"] / (1024**3)
        
        self.bar_used.setText(f"{used_gb:.1f} GB")
        self.bar_cached.setText(f"{cached_gb:.1f} GB")
        self.bar_free.setText(f"{free_gb:.1f} GB")
                                    
        self.ram_bar_layout.setStretchFactor(self.bar_used, max(1, int((ram_data["used"] / total) * 100)))
        self.ram_bar_layout.setStretchFactor(self.bar_cached, max(1, int((ram_data["cached"] / total) * 100)))
        self.ram_bar_layout.setStretchFactor(self.bar_free, max(1, int((ram_data["free"] / total) * 100)))
        
        if self._pending_kill_pids:
            hogs = [(app, pid, mem) for app, pid, mem in hogs if pid not in self._pending_kill_pids]
            self._pending_kill_pids.clear()
        
                                                                          
        self.ram_table.blockSignals(True)
        
        target_count = len(hogs)
        current_count = self.ram_table.rowCount()
        
                                                    
        if current_count < target_count:
            for _ in range(target_count - current_count):
                self.ram_table.insertRow(self.ram_table.rowCount())
        elif current_count > target_count:
            for _ in range(current_count - target_count):
                self.ram_table.removeRow(self.ram_table.rowCount() - 1)
        
        for row_idx, (app, pid, mem_mb) in enumerate(hogs):
                                                             
            name_item = self.ram_table.item(row_idx, 0)
            if name_item is None:
                name_item = QTableWidgetItem()
                self.ram_table.setItem(row_idx, 0, name_item)
            name_item.setText(app)
            
            pid_item = self.ram_table.item(row_idx, 1)
            if pid_item is None:
                pid_item = QTableWidgetItem()
                pid_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter)
                self.ram_table.setItem(row_idx, 1, pid_item)
            pid_item.setText(str(pid))
            
            usage_item = self.ram_table.item(row_idx, 2)
            if usage_item is None:
                usage_item = QTableWidgetItem()
                usage_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.ram_table.setItem(row_idx, 2, usage_item)
            usage_item.setText(f"{mem_mb:.1f} MB")
            
                                                                    
            existing_btn = self.ram_table.cellWidget(row_idx, 3)
            if existing_btn is None:
                kill_btn = QPushButton("✖")
                kill_btn.setStyleSheet("""
                    QPushButton { background-color: rgba(255, 68, 68, 30); color: #ff4444; border: none; border-radius: 4px; font-weight: bold;}
                    QPushButton:hover { background-color: rgba(255, 68, 68, 80); color: white;}
                """)
                kill_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                kill_btn.clicked.connect(lambda checked, p=pid, a=app: self.handle_kill_process(p, a))
                self.ram_table.setCellWidget(row_idx, 3, kill_btn)
            else:
                                                                                  
                try:
                    existing_btn.clicked.disconnect()
                except TypeError:
                    pass
                existing_btn.clicked.connect(lambda checked, p=pid, a=app: self.handle_kill_process(p, a))
        
        self.ram_table.blockSignals(False)

    def refresh_disk_page(self):
        """Populates the disk partition bars."""
                           
        while self.disk_bars_layout.count():
            item = self.disk_bars_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        partitions = get_disk_partitions()

        for part in partitions:
            row = QFrame()
            row.setStyleSheet(styles.CARD_STYLE)
            row.setFixedHeight(65)
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(10, 5, 10, 5)

            total_gb = part["total"] / (1024**3)
            used_gb = part["used"] / (1024**3)
            label = QLabel(f"{part['mountpoint']}  —  {used_gb:.1f} / {total_gb:.1f} GB ({part['percent']}%)")
            label.setStyleSheet("font-size: 13px; font-weight: bold; color: #e0e0e0; background: transparent; border: none;")

            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(int(part["percent"]))
            bar.setTextVisible(False)
            bar.setFixedHeight(8)

            if part["percent"] > 90:
                color = "#ff5252"
            elif part["percent"] > 70:
                color = "#FF9800"
            else:
                color = "#4CAF50"

            bar.setStyleSheet(f"""
                QProgressBar {{ background-color: rgba(255, 255, 255, 10); border-radius: 4px; }}
                QProgressBar::chunk {{ background-color: {color}; border-radius: 4px; }}
            """)

            row_layout.addWidget(label)
            row_layout.addWidget(bar)
            self.disk_bars_layout.addWidget(row)

    def refresh_bat_page(self):
        """Populates detailed battery information."""
        while self.bat_info_layout.count():
            item = self.bat_info_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
                
        from sys_logic import get_detailed_battery_info
        bat_details = get_detailed_battery_info()
        
        if not bat_details:
            lbl = QLabel("Detailed battery information is not available.")
            lbl.setStyleSheet("font-size: 14px; color: #888888;")
            self.bat_info_layout.addWidget(lbl)
            return
            
        card = QFrame()
        card.setStyleSheet(styles.CARD_STYLE)
        layout = QVBoxLayout(card)
        
        info_text = ""
        for key, value in bat_details.items():
            info_text += f"<b>{key}:</b> {value}<br><br>"
            
        lbl = QLabel(info_text)
        lbl.setStyleSheet("font-size: 14px; color: #e0e0e0; line-height: 1.5;")
        lbl.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(lbl)
        
        self.bat_info_layout.addWidget(card)

    def build_cpu_info_ui(self):
        """Builds the static hardware info page once."""
        from sys_logic import get_cpu_hardware_info
        
        info = get_cpu_hardware_info()
        card = QFrame()
        card.setStyleSheet(styles.CARD_STYLE)
        card.setMinimumHeight(150)
        layout = QVBoxLayout(card)
        
        name = QLabel(info['name'])
        name.setStyleSheet("font-size: 18px; font-weight: bold; color: #2196F3;")
        
        details = QLabel(
            f"Architecture: {info['arch']}\n"
            f"Physical Cores: {info['cores']}\n"
            f"Logical Threads: {info['threads']}\n"
            f"Base Clock: {info['base_clock']:.2f} GHz"
        )
        details.setStyleSheet("font-size: 14px; color: #e0e0e0; line-height: 1.8;")
        
        layout.addWidget(name)
        layout.addWidget(details)
        self.cpu_info_layout.addWidget(card)

    def build_cpu_usage_ui(self):
        """Builds the grid of progress bars for each CPU thread."""
        import psutil
        threads = psutil.cpu_count(logical=True)
        cols = 4                        
        
        for i in range(threads):
            vbox = QVBoxLayout()
            lbl = QLabel(f"Thread {i}")
            lbl.setStyleSheet("color: #a0a0a0; font-size: 11px;")
            
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setTextVisible(False)
            bar.setFixedHeight(6)
            bar.setStyleSheet("""
                QProgressBar { background-color: rgba(255, 255, 255, 10); border-radius: 3px; }
                QProgressBar::chunk { background-color: #4CAF50; border-radius: 3px; }
            """)
            
            vbox.addWidget(lbl)
            vbox.addWidget(bar)
            
            row = i // cols
            col = i % cols
            self.cpu_usage_layout.addLayout(vbox, row, col)
            self.core_bars.append(bar)

    def refresh_cpu_page(self, global_cpu_perc):
        """Updates the live CPU tabs."""
        if self.stack.currentIndex() != 3 or not self.expanded:
            return

                                                    
        if self.cpu_info_layout.count() == 0:
            self.build_cpu_info_ui()
            self.build_cpu_usage_ui()
            
                                    
        if self.cpu_stack.currentIndex() == 1:
            from sys_logic import get_cpu_core_usage
            usages = get_cpu_core_usage()
            
            for bar, usage in zip(self.core_bars, usages):
                bar.setValue(int(usage))
                
                                                          
                if usage > 85:
                    color = "#ff5252"      
                elif usage > 50:
                    color = "#ffd600"         
                else:
                    color = "#4CAF50"        
                    
                bar.setStyleSheet(f"""
                    QProgressBar {{ background-color: rgba(255, 255, 255, 10); border-radius: 3px; }}
                    QProgressBar::chunk {{ background-color: {color}; border-radius: 3px; }}
                """)
    
    def adjust_window_height(self):
        """Dynamically resizes the window with smooth animation."""
        if not self.expanded:
            target_h = 275
        else:
            current_main = self.stack.currentIndex()
            if current_main == 0:                            
                target_h = 655
            elif current_main == 1:                           
                target_h = 585
            elif current_main == 2:                
                target_h = 655
            elif current_main == 3:                    
                current_cpu = self.cpu_stack.currentIndex()
                if current_cpu == 0:                       
                    target_h = 515
                elif current_cpu == 1:                       
                    target_h = 515
                else:
                    target_h = 515
            elif current_main == 4:                   
                target_h = 515
            elif current_main == 5:                   
                target_h = 515
            else:
                target_h = 655
        
        current_h = self.height()
        if current_h == target_h:
            return
        
                                                                                       
        self.setFixedWidth(1050)
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)                                   
        
        self._height_anim.stop()
        self._height_anim.setStartValue(current_h)
        self._height_anim.setEndValue(target_h)
        
        self._width_anim.stop()
        self._width_anim.setStartValue(current_h)
        self._width_anim.setEndValue(target_h)
        
        self._height_anim.start()
        self._width_anim.start()

    def closeEvent(self, event):
        """Intercepts the 'X' button to minimize to tray instead of quitting."""
        event.ignore()                               
        self.hide()                              
        
                                                                  
        self.tray.showMessage(
            "Versysmon",
            "Running in the background. Click the tray icon to open.",
            QSystemTrayIcon.MessageIcon.Information,
            2000
        )

    def tray_icon_clicked(self, reason):
        """Handles left-clicking the tray icon."""
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def show_window(self):
        """Restores the window to the screen."""
        self.showNormal()
        self.activateWindow()

    def quit_app(self):
        """Safely kills background threads and completely exits the app."""
        self.bg_tracker.stop()
        QApplication.quit()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    app.setQuitOnLastWindowClosed(False)
    
                                  
    shared_mem = QSharedMemory("Versysmon_Background_Lock_v1")
    
    if shared_mem.attach():
        print("Versysmon is already running in the background.")
        sys.exit(0)                                  
    else:
        shared_mem.create(1) 
    
    view = Versysmon()
    pywinstyles.apply_style(view, "acrylic")
    view.show()
    sys.exit(app.exec())