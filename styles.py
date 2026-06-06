"""
Versysmon - Global Stylesheet

Defines the core design system for Versysmon using Qt Style Sheets (QSS).
Contains dark mode variables, card components, smooth scrollbar styling,
and standardized UI elements.
"""

WINDOW_STYLE = "QMainWindow { background-color: rgba(18, 18, 18, 150); }"
CARD_STYLE = """
    QFrame {
        background-color: rgba(255, 255, 255, 10);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 20);
    }
    QLabel { background-color: transparent; border: none; color: #e0e0e0; }
"""

                            
BUTTON_STYLE = """
    QPushButton {
        background-color: rgba(255, 255, 255, 10);
        color: #e0e0e0;
        border: 1px solid rgba(255, 255, 255, 20);
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
    }
    QPushButton:hover {
        background-color: rgba(255, 255, 255, 20);
    }
    QPushButton:pressed {
        background-color: rgba(255, 255, 255, 5);
    }
"""

                             
DATE_EDIT_STYLE = """
    QDateEdit {
        background-color: rgba(0, 0, 0, 50);
        color: white;
        border: 1px solid rgba(255, 255, 255, 20);
        border-radius: 4px;
        padding: 4px;
    }
    QDateEdit::drop-down {
        border: none;
    }
"""

                           
DETAIL_STYLE = """
    QTableWidget {
        background-color: rgba(0, 0, 0, 40);
        color: white;
        gridline-color: rgba(255, 255, 255, 10);
        border: 1px solid rgba(255, 255, 255, 15);
        border-radius: 8px;
        alternate-background-color: rgba(255, 255, 255, 5);
    }
    QHeaderView::section {
        background-color: rgba(255, 255, 255, 10);
        color: #888888;
        padding: 4px;
        border: none;
        font-weight: bold;
    }
    QTableWidget::item:selected {
        background-color: rgba(33, 150, 243, 40);
    }
    QScrollBar:vertical {
        background: rgba(0, 0, 0, 20);
        width: 8px;
        border-radius: 4px;
    }
    QScrollBar::handle:vertical {
        background: rgba(255, 255, 255, 30);
        border-radius: 4px;
        min-height: 20px;
    }
    QScrollBar::handle:vertical:hover {
        background: rgba(255, 255, 255, 50);
    }
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
        height: 0px;
    }
"""

                              
STATUS_BAR_STYLE = """
    QFrame {
        background-color: rgba(255, 255, 255, 5);
        border-radius: 6px;
        border: 1px solid rgba(255, 255, 255, 10);
    }
    QLabel { background-color: transparent; border: none; }
"""