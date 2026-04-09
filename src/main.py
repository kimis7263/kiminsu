import sys
import os
import json
import pandas as pd
import numpy as np
import pyqtgraph as pg
import pyqtgraph.exporters
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QFileDialog,
                               QListWidget, QComboBox, QSplitter, QAbstractItemView, 
                               QMessageBox, QSpinBox, QDoubleSpinBox, QCheckBox, 
                               QRadioButton, QButtonGroup, QColorDialog, QGroupBox,
                               QTableWidget, QTableWidgetItem, QHeaderView, QInputDialog, QMenu,
                               QDialog, QFormLayout, QLineEdit)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont, QColor, QAction

# ==========================================
# 1. 커스텀 인터랙티브 범례(Legend)
# ==========================================
class FloatingLegend(QWidget):
    def __init__(self, parent_widget, main_window):
        super().__init__(parent_widget)
        self.main_window = main_window
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(5)
        self.dragPos = None
        self.has_moved = False
        self.hide()
        self.apply_style()

    def apply_style(self):
        if self.main_window.is_dark_mode:
            self.setStyleSheet("FloatingLegend { background-color: rgba(43, 43, 43, 220); border: 1px solid #555; border-radius: 8px; }")
        else:
            self.setStyleSheet("FloatingLegend { background-color: rgba(255, 255, 255, 230); border: 1px solid #aaa; border-radius: 8px; }")

    def update_legend(self, lines):
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.layout():
                while item.layout().count():
                    sub = item.layout().takeAt(0)
                    if sub.widget(): sub.widget().deleteLater()
                item.layout().deleteLater()

        visible_lines = [l for l in lines if l['visible']]
        if not visible_lines:
            self.hide()
            return
            
        self.show()
        for line in visible_lines:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            
            color_box = QLabel()
            color_box.setFixedSize(14, 14)
            border_col = '#fff' if self.main_window.is_dark_mode else '#000'
            color_box.setStyleSheet(f"background-color: {line['color']}; border: 1px solid {border_col}; border-radius: 2px;")
            
            edit = QLineEdit(line['name'])
            edit.setMinimumWidth(120)
            if self.main_window.is_dark_mode:
                edit.setStyleSheet("color: #ecf0f1; background: transparent; border: none; font-weight: bold; font-size: 13px;")
            else:
                edit.setStyleSheet("color: #2c3e50; background: transparent; border: none; font-weight: bold; font-size: 13px;")
                
            edit.textChanged.connect(lambda text, l=line: self.main_window.update_line_name(l, text))
            
            row.addWidget(color_box)
            row.addWidget(edit)
            self.layout.addLayout(row)
        
        self.adjustSize()
        if not self.has_moved and self.parent():
            self.move(self.parent().width() - self.width() - 20, 20)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            self.dragPos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.RightButton and self.dragPos is not None:
            self.move(event.globalPosition().toPoint() - self.dragPos)
            self.has_moved = True

# ==========================================
# 2. 플로팅 아이콘 (미니모드)
# ==========================================
class FloatingButton(QWidget):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.FramelessWindowHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.resize(70, 70)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.btn = QPushButton("📊\nAI Log")
        self.btn.setStyleSheet("QPushButton { background-color: #2c3e50; color: white; border-radius: 35px; font-weight: bold; font-size: 12px; } QPushButton:hover { background-color: #34495e; }")
        self.btn.setFixedSize(70, 70)
        self.btn.clicked.connect(self.restore_main)
        layout.addWidget(self.btn)
        self.dragPos = QPoint()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.dragPos)

    def restore_main(self):
        self.hide()
        self.main_window.show()
        self.main_window.activateWindow()

# ==========================================
# 3. 메인 윈도우 
# ==========================================
class AILogVisualizer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI Log Visualizer - Master & Commander (V5.1)")
        self.resize(1700, 950)
        self.current_folder = ""
        self.current_filename = ""
        self.df = None
        
        self.plotted_lines = [] 
        self.annotations = [] 
        self.default_colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
        self.is_dark_mode = False 

        # 🌟 드래그 앤 드롭 활성화
        self.setAcceptDrops(True)
        
        self.init_ui()
        self.floating_btn = FloatingButton(self)
        self.apply_theme()

    # 🌟 테마 붕괴 해결: 전체 QWidget이 아닌 특정 요소만 정밀하게 타겟팅
    def apply_theme(self):
        bg, fg = ('#1e1e1e', '#ffffff') if self.is_dark_mode else ('w', 'k')
        pg.setConfigOption('background', bg)
        pg.setConfigOption('foreground', fg)
        pg.setConfigOptions(antialias=True)
        
        if self.is_dark_mode:
            self.setStyleSheet("""
                QMainWindow { background-color: #2b2b2b; }
                QLabel, QCheckBox, QRadioButton, QGroupBox { color: #ffffff; }
                QPushButton { background-color: #3c3f41; color: white; border: 1px solid #555; padding: 5px; border-radius: 4px; }
                QPushButton:hover { background-color: #505354; }
                QTableWidget, QListWidget, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox { 
                    background-color: #1e1e1e; color: white; border: 1px solid #555; 
                }
                QHeaderView::section { background-color: #3c3f41; color: white; border: 1px solid #555; }
            """)
        else:
            self.setStyleSheet("") # 빈 문자열로 두면 윈도우 기본 예쁜 테마로 완벽 복구됨
            
        if hasattr(self, 'floating_legend'):
            self.floating_legend.apply_style()
            self.floating_legend.update_legend(self.plotted_lines)
            
        if hasattr(self, 'graph_layout'): 
            self.graph_layout.setBackground(bg) 
            self.redraw_graphs()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        self.apply_theme()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        top_bar = QHBoxLayout()
        self.btn_open = QPushButton("📂 폴더 열기")
        self.btn_open.clicked.connect(self.open_folder)
        self.btn_theme = QPushButton("🌓 다크/라이트 테마")
        self.btn_theme.clicked.connect(self.toggle_theme)
        self.btn_save_preset = QPushButton("💾 프리셋 저장")
        self.btn_load_preset = QPushButton("📂 프리셋 불러오기")
        self.btn_export = QPushButton("📷 고급 내보내기")
        self.btn_export.setStyleSheet("background-color: #9b59b6; color: white; font-weight: bold;")
        self.btn_export.clicked.connect(self.export_all)
        self.btn_float = QPushButton("📌 미니모드")
        self.btn_float.setStyleSheet("background-color: #e74c3c; color: white; font-weight: bold;")
        self.btn_float.clicked.connect(self.switch_to_float)
        
        for btn in [self.btn_open, top_bar.addStretch(), self.btn_theme, self.btn_save_preset, self.btn_load_preset, self.btn_export, self.btn_float]:
            if isinstance(btn, QPushButton): top_bar.addWidget(btn)
        main_layout.addLayout(top_bar)

        splitter_main = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter_main, 1)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("📄 CSV 파일 목록"))
        self.file_list = QListWidget()
        self.file_list.itemClicked.connect(self.load_csv_preview)
        left_layout.addWidget(self.file_list)
        splitter_main.addWidget(left_widget)

        center_widget = QWidget()
        center_layout = QVBoxLayout(center_widget)
        center_layout.setContentsMargins(0, 0, 0, 0)

        group_data = QGroupBox("데이터 추가")
        data_layout = QVBoxLayout(group_data)
        data_layout.addWidget(QLabel("X축:"))
        self.combo_x = QComboBox()
        data_layout.addWidget(self.combo_x)
        data_layout.addWidget(QLabel("Y축:"))
        self.list_y = QListWidget()
        self.list_y.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list_y.setMaximumHeight(80)
        data_layout.addWidget(self.list_y)
        self.btn_add = QPushButton("➕ 선택 항목 누적 추가")
        self.btn_add.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.btn_add.clicked.connect(self.add_to_plot)
        data_layout.addWidget(self.btn_add)
        center_layout.addWidget(group_data)

        group_layers = QGroupBox("활성 그래프 관리")
        layer_layout = QVBoxLayout(group_layers)
        self.table_layers = QTableWidget(0, 4)
        self.table_layers.setHorizontalHeaderLabels(["Show", "Name", "Color", "Style"])
        self.table_layers.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_layers.itemChanged.connect(self.handle_layer_change)
        layer_layout.addWidget(self.table_layers)
        self.btn_clear = QPushButton("🗑️ 전체 지우기")
        self.btn_clear.clicked.connect(self.clear_plots)
        layer_layout.addWidget(self.btn_clear)
        center_layout.addWidget(group_layers)

        group_annot = QGroupBox("📝 그래프 메모")
        annot_layout = QVBoxLayout(group_annot)
        self.table_annot = QTableWidget(0, 3)
        self.table_annot.setHorizontalHeaderLabels(["메모 내용", "X 좌표", "Y 좌표"])
        self.table_annot.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        annot_layout.addWidget(self.table_annot)
        annot_btn_layout = QHBoxLayout()
        self.btn_add_annot = QPushButton("➕ 수동 추가")
        self.btn_add_annot.clicked.connect(self.add_annotation_manual)
        self.btn_del_annot = QPushButton("🗑️ 선택 삭제")
        self.btn_del_annot.clicked.connect(self.delete_annotation)
        annot_btn_layout.addWidget(self.btn_add_annot)
        annot_btn_layout.addWidget(self.btn_del_annot)
        annot_layout.addLayout(annot_btn_layout)
        center_layout.addWidget(group_annot)

        group_stats = QGroupBox("전체 통계 요약")
        stats_layout = QVBoxLayout(group_stats)
        self.table_stats = QTableWidget(0, 5)
        self.table_stats.setHorizontalHeaderLabels(["Name", "Min", "Max", "Mean", "Final"])
        self.table_stats.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        stats_layout.addWidget(self.table_stats)
        center_layout.addWidget(group_stats)

        splitter_main.addWidget(center_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)

        opt_layout = QHBoxLayout()
        opt_layout.addWidget(QLabel("📉 스무딩:"))
        self.spin_smooth = QSpinBox()
        self.spin_smooth.setRange(1, 100)
        self.spin_smooth.setValue(1)
        self.spin_smooth.valueChanged.connect(self.redraw_graphs)
        opt_layout.addWidget(self.spin_smooth)

        self.radio_overlay = QRadioButton("겹쳐서 보기")
        self.radio_overlay.setChecked(True)
        self.radio_split = QRadioButton("따로 분리")
        self.btn_group = QButtonGroup()
        self.btn_group.addButton(self.radio_overlay)
        self.btn_group.addButton(self.radio_split)
        self.radio_overlay.toggled.connect(self.redraw_graphs)
        opt_layout.addWidget(self.radio_overlay)
        opt_layout.addWidget(self.radio_split)

        self.chk_best = QCheckBox("Best 마커")
        self.chk_best.setChecked(True)
        self.chk_best.stateChanged.connect(self.redraw_graphs)
        opt_layout.addWidget(self.chk_best)

        right_layout.addLayout(opt_layout)

        self.graph_layout = pg.GraphicsLayoutWidget()
        right_layout.addWidget(self.graph_layout, 1)
        
        self.floating_legend = FloatingLegend(self.graph_layout, self)

        splitter_main.addWidget(right_widget)
        splitter_main.setSizes([200, 400, 1100])

    # ==========================================
    # 🌟 드래그 앤 드롭 복구 완료!
    # ==========================================
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        path = event.mimeData().urls()[0].toLocalFile()
        if os.path.isdir(path):
            self.set_working_folder(path)
        elif path.endswith('.csv'):
            self.set_working_folder(os.path.dirname(path))

    def open_folder(self):
        folder_path = QFileDialog.getExistingDirectory(self, "AI 로그 폴더 선택")
        if folder_path: self.set_working_folder(folder_path)

    def set_working_folder(self, folder_path):
        self.current_folder = folder_path
        self.file_list.clear()
        files = [f for f in os.listdir(folder_path) if f.endswith('.csv')]
        self.file_list.addItems(files)

    def load_csv_preview(self, item):
        self.current_filename = item.text()
        file_path = os.path.join(self.current_folder, self.current_filename)
        try:
            self.df = pd.read_csv(file_path)
            columns = self.df.columns.tolist()
            self.combo_x.clear()
            self.list_y.clear()
            self.combo_x.addItems(columns)
            self.list_y.addItems(columns)
            if len(columns) > 0: self.combo_x.setCurrentIndex(0)
        except Exception as e:
            QMessageBox.warning(self, "에러", f"파일 읽기 오류:\n{e}")

    def update_line_name(self, line_data, new_name):
        line_data['name'] = new_name
        self.table_layers.blockSignals(True)
        for row, line in enumerate(self.plotted_lines):
            if line is line_data:
                self.table_layers.item(row, 1).setText(new_name)
        self.table_layers.blockSignals(False)
        self.update_stats()

    def add_to_plot(self):
        if self.df is None or self.df.empty: return
        x_col = self.combo_x.currentText()
        y_items = self.list_y.selectedItems()
        for item in y_items:
            y_col = item.text()
            color = self.default_colors[len(self.plotted_lines) % len(self.default_colors)]
            line_data = {
                'name': f"{self.current_filename} - {y_col}",
                'x_data': self.df[x_col].values,
                'raw_y_data': self.df[y_col].values,
                'x_col': x_col, 'y_col': y_col,
                'color': color, 'visible': True, 'style': Qt.SolidLine, 'width': 2
            }
            self.plotted_lines.append(line_data)
            self.add_layer_row(line_data)
        
        self.floating_legend.update_legend(self.plotted_lines)
        self.redraw_graphs()

    def add_layer_row(self, line_data):
        self.table_layers.blockSignals(True)
        row = self.table_layers.rowCount()
        self.table_layers.insertRow(row)
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        chk.setCheckState(Qt.Checked)
        self.table_layers.setItem(row, 0, chk)
        name_item = QTableWidgetItem(line_data['name'])
        name_item.setFlags(Qt.ItemIsEnabled)
        self.table_layers.setItem(row, 1, name_item)
        btn_color = QPushButton("🎨")
        btn_color.setStyleSheet(f"background-color: {line_data['color']};")
        btn_color.clicked.connect(lambda _, r=row: self.change_line_color(r))
        self.table_layers.setCellWidget(row, 2, btn_color)
        btn_style = QPushButton("➖")
        btn_style.clicked.connect(lambda _, r=row: self.change_line_style(r))
        self.table_layers.setCellWidget(row, 3, btn_style)
        self.table_layers.blockSignals(False)

    def handle_layer_change(self, item):
        if item.column() == 0:
            self.plotted_lines[item.row()]['visible'] = (item.checkState() == Qt.Checked)
            self.floating_legend.update_legend(self.plotted_lines)
            self.redraw_graphs()

    def change_line_color(self, row):
        color = QColorDialog.getColor()
        if color.isValid():
            self.plotted_lines[row]['color'] = color.name()
            self.table_layers.cellWidget(row, 2).setStyleSheet(f"background-color: {color.name()};")
            self.floating_legend.update_legend(self.plotted_lines)
            self.redraw_graphs()

    def change_line_style(self, row):
        styles = {"실선": Qt.SolidLine, "점선": Qt.DashLine, "도트": Qt.DotLine}
        style_name, ok = QInputDialog.getItem(self, "선 스타일", "스타일 선택:", list(styles.keys()), 0, False)
        if ok:
            self.plotted_lines[row]['style'] = styles[style_name]
            self.table_layers.cellWidget(row, 3).setText("➖" if styles[style_name] == Qt.SolidLine else "---")
            self.redraw_graphs()

    def add_annotation_manual(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("메모 추가")
        layout = QFormLayout(dialog)
        
        txt_input = QLineEdit()
        x_input = QDoubleSpinBox(); x_input.setRange(-1e9, 1e9); x_input.setDecimals(4)
        y_input = QDoubleSpinBox(); y_input.setRange(-1e9, 1e9); y_input.setDecimals(4)
        
        if self.plotted_lines:
            x_input.setValue(self.plotted_lines[0]['x_data'].mean())
            y_input.setValue(self.plotted_lines[0]['raw_y_data'].mean())

        btn_color = QPushButton("색상 선택 (기본: 테마색)")
        annot_color = ['#ffffff' if self.is_dark_mode else '#000000']
        def pick_color():
            c = QColorDialog.getColor()
            if c.isValid(): annot_color[0] = c.name(); btn_color.setStyleSheet(f"background-color: {c.name()}; color: {'black' if self.is_dark_mode else 'white'};")
        btn_color.clicked.connect(pick_color)

        btn_submit = QPushButton("추가")
        btn_submit.clicked.connect(dialog.accept)

        layout.addRow("메모 내용:", txt_input)
        layout.addRow("X 좌표:", x_input)
        layout.addRow("Y 좌표:", y_input)
        layout.addRow("글자 색상:", btn_color)
        layout.addRow(btn_submit)

        if dialog.exec():
            text = txt_input.text()
            if not text: return
            self.annotations.append({
                'text': text, 'x': x_input.value(), 'y': y_input.value(), 'color': annot_color[0]
            })
            self.update_annot_table()
            self.redraw_graphs()

    def update_annot_table(self):
        self.table_annot.setRowCount(0)
        for ann in self.annotations:
            row = self.table_annot.rowCount()
            self.table_annot.insertRow(row)
            self.table_annot.setItem(row, 0, QTableWidgetItem(ann['text']))
            self.table_annot.setItem(row, 1, QTableWidgetItem(f"{ann['x']:.2f}"))
            self.table_annot.setItem(row, 2, QTableWidgetItem(f"{ann['y']:.2f}"))

    def delete_annotation(self):
        selected = self.table_annot.currentRow()
        if selected >= 0:
            del self.annotations[selected]
            self.update_annot_table()
            self.redraw_graphs()

    def update_stats(self):
        self.table_stats.setRowCount(0)
        smooth_window = self.spin_smooth.value()

        for line_data in self.plotted_lines:
            if not line_data['visible']: continue
            
            raw_y = line_data['raw_y_data']
            y = pd.Series(raw_y).rolling(window=smooth_window, min_periods=1).mean().values if smooth_window > 1 else raw_y
            
            if len(y) == 0: continue

            row = self.table_stats.rowCount()
            self.table_stats.insertRow(row)
            self.table_stats.setItem(row, 0, QTableWidgetItem(line_data['name']))
            self.table_stats.setItem(row, 1, QTableWidgetItem(f"{y.min():.4f}"))
            self.table_stats.setItem(row, 2, QTableWidgetItem(f"{y.max():.4f}"))
            self.table_stats.setItem(row, 3, QTableWidgetItem(f"{y.mean():.4f}"))
            self.table_stats.setItem(row, 4, QTableWidgetItem(f"{y[-1]:.4f}"))

    def redraw_graphs(self):
        self.graph_layout.clear()
        if not self.plotted_lines: 
            self.table_stats.setRowCount(0)
            return

        smooth_window = self.spin_smooth.value()
        is_split = self.radio_split.isChecked()
        plots = []

        main_plot = None
        for i, line_data in enumerate(self.plotted_lines):
            if not line_data['visible']: continue

            if is_split or main_plot is None:
                p = self.graph_layout.addPlot(title=line_data['name'] if is_split else "AI Multi-Model Tracker")
                p.showGrid(x=True, y=True, alpha=0.3)
                p.setLabel('bottom', line_data['x_col'])
                if not is_split: main_plot = p
                plots.append(p)
                if is_split and len(plots) > 1: p.setXLink(plots[0])
                if is_split and i < len(self.plotted_lines) - 1: self.graph_layout.nextRow()
            
            plot_target = p if is_split else main_plot
            raw_y = line_data['raw_y_data']
            y_data = pd.Series(raw_y).rolling(window=smooth_window, min_periods=1).mean().values if smooth_window > 1 else raw_y

            pen = pg.mkPen(color=line_data['color'], width=line_data['width'], style=line_data['style'])
            plot_target.plot(line_data['x_data'], y_data, name=line_data['name'], pen=pen)

            if self.chk_best.isChecked():
                best_idx = np.argmin(y_data) if 'loss' in line_data['y_col'].lower() else np.argmax(y_data)
                scatter = pg.ScatterPlotItem([line_data['x_data'][best_idx]], [y_data[best_idx]], size=14, symbol='star', brush=pg.mkBrush(line_data['color']))
                plot_target.addItem(scatter)

        if plots:
            target_plot = plots[0] if is_split else main_plot
            for ann in self.annotations:
                text_item = pg.TextItem(text=ann['text'], color=ann['color'], fill=pg.mkBrush(255, 255, 255, 180) if not self.is_dark_mode else pg.mkBrush(40, 40, 40, 180))
                text_item.setPos(ann['x'], ann['y'])
                font = QFont(); font.setPixelSize(14); font.setBold(True); text_item.setFont(font)
                target_plot.addItem(text_item)

        self.update_stats()

    def clear_plots(self):
        self.plotted_lines.clear()
        self.annotations.clear()
        self.table_layers.setRowCount(0)
        self.table_annot.setRowCount(0)
        self.graph_layout.clear()
        self.floating_legend.hide()
        self.table_stats.setRowCount(0)

    def export_all(self):
        if not self.plotted_lines: return
        menu = QMenu(self)
        action_png = QAction("PNG 캡처", self)
        action_svg = QAction("SVG 논문용 내보내기", self)
        action_png.triggered.connect(lambda: self._export_img("png"))
        action_svg.triggered.connect(lambda: self._export_img("svg"))
        menu.addAction(action_png)
        menu.addAction(action_svg)
        menu.exec(self.btn_export.mapToGlobal(QPoint(0, self.btn_export.height())))

    def _export_img(self, fmt):
        path, _ = QFileDialog.getSaveFileName(self, f"{fmt.upper()} 저장", f"export.{fmt}", f"{fmt.upper()} (*.{fmt})")
        if path:
            exporter = pyqtgraph.exporters.ImageExporter(self.graph_layout.scene()) if fmt == 'png' else pyqtgraph.exporters.SVGExporter(self.graph_layout.scene())
            if fmt == 'png': exporter.parameters()['width'] = 1920
            exporter.export(path)

    def switch_to_float(self):
        self.hide()
        screen_geo = QApplication.primaryScreen().availableGeometry()
        self.floating_btn.move(screen_geo.width() - 150, screen_geo.height() - 150)
        self.floating_btn.show()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AILogVisualizer()
    window.show()
    sys.exit(app.exec())