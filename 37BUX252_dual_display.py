import sys
import threading
import time

import cv2
import imagingcontrol4 as ic4
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QDoubleSpinBox, QFormLayout, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMessageBox, QPushButton, QSlider, QTabWidget,
    QVBoxLayout, QWidget
)
from PySide6.QtGui import QCloseEvent


# ─────────────────────────────────────────
#  Camera Selection Dialog
# ─────────────────────────────────────────
class CameraSelectionDialog(QDialog):
    """
    啟動時讓使用者選擇相機。
    支援：
      • 雙相機模式（預設，當找到 ≥2 台時）
      • 單相機雙畫面模式（Single Camera / Dual Display）
    """

    def __init__(self, devices, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.selected_indices = None      # tuple: (i0, i1)  或 (i0,) 代表 single
        self.single_mode = (len(devices) < 2)
        self._build_ui()

    def _build_ui(self):
        self.setWindowTitle("Select Camera(s)")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)

        title = QLabel("🎥  Please select camera(s)")
        title.setStyleSheet("font-size: 16px; font-weight: bold; padding: 5px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)

        info = QLabel(f"Found {len(self.devices)} device(s).")
        info.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(info)

        # ── Single-camera mode toggle ──────────────────────────────
        self.chk_single = QCheckBox(
            "Single camera mode (show the same stream on both views)"
        )
        self.chk_single.setChecked(self.single_mode)
        self.chk_single.toggled.connect(self._on_mode_toggled)
        # 如果只有 1 台相機，強制單相機模式
        if len(self.devices) < 2:
            self.chk_single.setChecked(True)
            self.chk_single.setEnabled(False)
        layout.addWidget(self.chk_single)

        # ── Camera selectors ───────────────────────────────────────
        form = QFormLayout()
        self.combo_0 = QComboBox()
        self.combo_1 = QComboBox()
        for i, dev in enumerate(self.devices):
            label = f"[{i}] {dev.model_name}  (S/N: {dev.serial})"
            self.combo_0.addItem(label, i)
            self.combo_1.addItem(label, i)
        if len(self.devices) >= 2:
            self.combo_1.setCurrentIndex(1)

        self._label_cam0 = QLabel("Camera 0:")
        self._label_cam1 = QLabel("Camera 1:")
        form.addRow(self._label_cam0, self.combo_0)
        form.addRow(self._label_cam1, self.combo_1)
        layout.addLayout(form)

        # ── OK / Cancel ────────────────────────────────────────────
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self._on_mode_toggled(self.chk_single.isChecked())

    def _on_mode_toggled(self, checked):
        """切換單/雙相機模式時隱藏第二個下拉選單。"""
        self.single_mode = checked
        self._label_cam1.setVisible(not checked)
        self.combo_1.setVisible(not checked)
        if checked:
            self._label_cam0.setText("Camera:")
        else:
            self._label_cam0.setText("Camera 0:")

    def _on_accept(self):
        i0 = self.combo_0.currentData()
        if self.single_mode:
            self.selected_indices = (i0,)
            self.accept()
            return
        i1 = self.combo_1.currentData()
        if i0 == i1:
            QMessageBox.warning(
                self, "Duplicate Selection",
                "Camera 0 and Camera 1 cannot be the same device.\n"
                "Use Single Camera mode if you only want one camera."
            )
            return
        self.selected_indices = (i0, i1)
        self.accept()


# ─────────────────────────────────────────
#  SliderWithValue
# ─────────────────────────────────────────
class SliderWithValue(QWidget):
    valueChanged = QtCore.Signal(float)

    def __init__(self, minimum, maximum, value,
                 decimals=2, step=1.0, parent=None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._step = step
        self._decimals = decimals
        self._updating = False
        self._build_ui(value)

    def _build_ui(self, initial_value):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider(QtCore.Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(self._float_to_tick(self._maximum))
        self._slider.setValue(self._float_to_tick(initial_value))
        self._slider.setMinimumWidth(160)

        self._spinbox = QDoubleSpinBox()
        self._spinbox.setDecimals(self._decimals)
        self._spinbox.setMinimum(self._minimum)
        self._spinbox.setMaximum(self._maximum)
        self._spinbox.setSingleStep(self._step)
        self._spinbox.setValue(initial_value)
        self._spinbox.setFixedWidth(110)

        layout.addWidget(self._slider, stretch=1)
        layout.addWidget(self._spinbox, stretch=0)

        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

    def _float_to_tick(self, val):
        return int(round((val - self._minimum) / self._step))

    def _tick_to_float(self, tick):
        return round(self._minimum + tick * self._step, self._decimals)

    def _on_slider_changed(self, tick):
        if self._updating:
            return
        self._updating = True
        fval = self._tick_to_float(tick)
        self._spinbox.setValue(fval)
        self.valueChanged.emit(fval)
        self._updating = False

    def _on_spinbox_changed(self, fval):
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(self._float_to_tick(fval))
        self.valueChanged.emit(fval)
        self._updating = False

    def value(self):
        return self._spinbox.value()

    def setValue(self, val):
        self._spinbox.setValue(val)

    def setEnabled(self, enabled):
        self._slider.setEnabled(enabled)
        self._spinbox.setEnabled(enabled)


# ─────────────────────────────────────────
#  Guided Control Panel
# ─────────────────────────────────────────
class GuidedPanel(QWidget):
    STEP_DESCRIPTIONS = [
        ("Step 1️⃣", "把 Gain 調到最低",
         "首先將 Gain 設為最小值（0 dB 或 minimum），確保影像雜訊最低。\n"
         "點擊下方按鈕自動重設。"),
        ("Step 2️⃣", "增加光源亮度 (最有效！)",
         "請先嘗試增加環境光源或補光燈亮度 —— 這是提升畫面品質最有效的方法。\n"
         "調整好後按「下一步」。"),
        ("Step 3️⃣", "慢慢提高 Exposure Time",
         "光源已足夠但畫面仍偏暗時,逐步拉高曝光時間。\n"
         "⚠ 注意：過高會導致動態模糊且降低實際 FPS。"),
        ("Step 4️⃣", "畫面還是不夠亮？才考慮提高 Gain",
         "如果已到最長可接受的曝光時間，畫面仍暗，才開始提高 Gain。\n"
         "Gain 會放大雜訊，請盡量少用。"),
        ("Step 5️⃣", "Gain 越低越好 —— 完成！",
         "✅ 調整完成。請確認：\n"
         "   • Gain 是否已調到可接受的最低值\n"
         "   • 畫面亮度與雜訊是否平衡"),
    ]

    def __init__(self, property_map, cam_name=""):
        super().__init__()
        self.property_map = property_map
        self.cam_name = cam_name
        self._current_step = 0
        self._init_ui()
        self._update_step_ui()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        step_box = QGroupBox("🧭 Adjustment Guide")
        step_lay = QVBoxLayout(step_box)

        self._step_title = QLabel()
        self._step_title.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #88C0D0;"
        )
        self._step_desc = QLabel()
        self._step_desc.setWordWrap(True)
        self._step_desc.setStyleSheet("font-size: 12px; padding: 4px;")

        step_lay.addWidget(self._step_title)
        step_lay.addWidget(self._step_desc)

        nav_row = QHBoxLayout()
        self._btn_prev = QPushButton("◀ Prev")
        self._btn_next = QPushButton("Next ▶")
        self._btn_reset = QPushButton("⟲ Restart")
        self._btn_prev.clicked.connect(self._prev_step)
        self._btn_next.clicked.connect(self._next_step)
        self._btn_reset.clicked.connect(self._reset_step)
        nav_row.addWidget(self._btn_prev)
        nav_row.addWidget(self._btn_next)
        nav_row.addWidget(self._btn_reset)
        step_lay.addLayout(nav_row)

        root.addWidget(step_box)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        root.addWidget(line)

        param_box = QGroupBox("⚙ Parameters")
        form = QFormLayout(param_box)
        form.setLabelAlignment(QtCore.Qt.AlignRight)

        gain_prop = self.property_map[ic4.PropId.GAIN]
        self._gain_min = float(gain_prop.minimum)
        self._gain_max = float(gain_prop.maximum)
        self.gain_widget = SliderWithValue(
            minimum=self._gain_min, maximum=self._gain_max,
            value=float(gain_prop.value), decimals=2, step=0.1,
        )
        self.gain_widget.valueChanged.connect(self._change_gain)
        form.addRow("Gain (dB)", self.gain_widget)

        exp_prop = self.property_map[ic4.PropId.EXPOSURE_TIME]
        self.exposure_widget = SliderWithValue(
            minimum=float(exp_prop.minimum), maximum=float(exp_prop.maximum),
            value=float(exp_prop.value), decimals=1, step=1.0,
        )
        self.exposure_widget.valueChanged.connect(self._change_exposure)
        form.addRow("Exposure Time (µs)", self.exposure_widget)

        try:
            fps_prop = self.property_map[ic4.PropId.ACQUISITION_FRAME_RATE]
            self.fps_widget = SliderWithValue(
                minimum=float(fps_prop.minimum), maximum=float(fps_prop.maximum),
                value=float(fps_prop.value), decimals=1, step=1.0,
            )
            self.fps_widget.valueChanged.connect(self._change_fps)
            form.addRow("Frame Rate (fps)", self.fps_widget)
        except Exception:
            self.fps_widget = None

        root.addWidget(param_box)

        action_row = QHBoxLayout()
        self._btn_set_min_gain = QPushButton("🔽 Set Gain → Minimum")
        self._btn_set_min_gain.clicked.connect(self._action_set_min_gain)
        action_row.addWidget(self._btn_set_min_gain)
        root.addLayout(action_row)

        root.addStretch(1)

    def _update_step_ui(self):
        idx = self._current_step
        title, subtitle, desc = self.STEP_DESCRIPTIONS[idx]
        self._step_title.setText(f"{title}  {subtitle}")
        self._step_desc.setText(desc)

        self._btn_prev.setEnabled(idx > 0)
        self._btn_next.setEnabled(idx < len(self.STEP_DESCRIPTIONS) - 1)

        self.gain_widget.setEnabled(True)
        self.exposure_widget.setEnabled(True)
        if self.fps_widget:
            self.fps_widget.setEnabled(True)

        self._btn_set_min_gain.setVisible(idx == 0)

        if idx == 2:
            self.gain_widget.setEnabled(False)

    def _next_step(self):
        if self._current_step < len(self.STEP_DESCRIPTIONS) - 1:
            self._current_step += 1
            self._update_step_ui()

    def _prev_step(self):
        if self._current_step > 0:
            self._current_step -= 1
            self._update_step_ui()

    def _reset_step(self):
        self._current_step = 0
        self._update_step_ui()

    def _action_set_min_gain(self):
        self.gain_widget.setValue(self._gain_min)
        print(f"[{self.cam_name}] Gain reset to minimum ({self._gain_min}).")

    def _change_exposure(self, val):
        ok = self.property_map.try_set_value(ic4.PropId.EXPOSURE_TIME, val)
        if not ok:
            print(f"[{self.cam_name}] Failed to set Exposure = {val}")

    def _change_gain(self, val):
        ok = self.property_map.try_set_value(ic4.PropId.GAIN, val)
        if not ok:
            print(f"[{self.cam_name}] Failed to set Gain = {val}")

    def _change_fps(self, val):
        ok = self.property_map.try_set_value(
            ic4.PropId.ACQUISITION_FRAME_RATE, val
        )
        if not ok:
            print(f"[{self.cam_name}] Failed to set FPS = {val}")


# ─────────────────────────────────────────
#  Queue-Sink Listener
# ─────────────────────────────────────────
class CameraListener(ic4.QueueSinkListener):
    def __init__(self, video_writer, frame_callback):
        super().__init__()
        self._video_writer = video_writer
        self._frame_callback = frame_callback
        self._lock = threading.Lock()
        self._do_write = False
        self._counter = 0
        self.first_frame_arrived = False

    def sink_connected(self, sink, image_type, min_buffers_required):
        self.image_type = image_type
        return True

    def frames_queued(self, sink):
        buffer = sink.pop_output_buffer()
        img = buffer.numpy_wrap().copy()

        if not self.first_frame_arrived:
            self.first_frame_arrived = True
            print("First frame arrived")

        if self._frame_callback is not None:
            self._frame_callback(img)

        with self._lock:
            if self._do_write:
                self._video_writer.add_frame(buffer)
                self._counter += 1

    def enable_recording(self, enable):
        with self._lock:
            if enable:
                self._counter = 0
            self._do_write = enable

    @property
    def frames_written(self):
        with self._lock:
            return self._counter


# ─────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────
class MainWindow(QMainWindow):
    new_frame_0 = QtCore.Signal(object)
    new_frame_1 = QtCore.Signal(object)

    _DISPLAY_INTERVAL = 1 / 24

    def __init__(self, devices):
        """
        devices: list of ic4 device info
            len == 1 → single-camera (dual display) mode
            len == 2 → dual-camera mode
        """
        super().__init__()
        assert 1 <= len(devices) <= 2
        self._devices = devices
        self._single_mode = (len(devices) == 1)

        self._inc = 0
        self._ocv = True
        self._recording = False
        self._last_display_0 = 0.0
        self._last_display_1 = 0.0

        self._init_grabbers()
        self._init_listeners()
        self._configure_cameras()
        self._start_streams()
        self._create_ui()

        print(f"Initialisation complete. "
              f"Mode = {'SINGLE (dual display)' if self._single_mode else 'DUAL'}")

    # ── Camera setup ──────────────────────────────────────────────────────────
    def _init_grabbers(self):
        self.grabber_0 = ic4.Grabber(self._devices[0])
        self.prop_map_0 = self.grabber_0.device_property_map
        self._writer_0 = ic4.VideoWriter(ic4.VideoWriterType.MP4_H264)

        if self._single_mode:
            # 單相機：第二組全部指向 None 或 alias
            self.grabber_1 = None
            self.prop_map_1 = None
            self._writer_1 = None
        else:
            self.grabber_1 = ic4.Grabber(self._devices[1])
            self.prop_map_1 = self.grabber_1.device_property_map
            self._writer_1 = ic4.VideoWriter(ic4.VideoWriterType.MP4_H264)

        self._frame_rate = float(
            self.prop_map_0[ic4.PropId.ACQUISITION_FRAME_RATE].value
        )

    def _init_listeners(self):
        self.new_frame_0.connect(self._update_label_0)
        self.new_frame_1.connect(self._update_label_1)

        if self._single_mode:
            # 單相機：同一幀同時發射兩個 signal → 兩邊 QLabel 各自更新
            def _emit_both(img):
                self.new_frame_0.emit(img)
                self.new_frame_1.emit(img)

            self._listener_0 = CameraListener(
                self._writer_0, frame_callback=_emit_both
            )
            self._listener_1 = None
        else:
            self._listener_0 = CameraListener(
                self._writer_0,
                frame_callback=lambda img: self.new_frame_0.emit(img),
            )
            self._listener_1 = CameraListener(
                self._writer_1,
                frame_callback=lambda img: self.new_frame_1.emit(img),
            )

    def _apply_camera_settings(self, prop_map):
        prop_map.try_set_value(ic4.PropId.WIDTH, 1280)
        prop_map.try_set_value(ic4.PropId.HEIGHT, 720)
        prop_map.try_set_value(ic4.PropId.ACQUISITION_FRAME_RATE, 240)
        prop_map.try_set_value(ic4.PropId.EXPOSURE_TIME, 60.0)
        gain_prop = prop_map[ic4.PropId.GAIN]
        prop_map.try_set_value(ic4.PropId.GAIN, float(gain_prop.minimum))

    def _configure_cameras(self):
        self._apply_camera_settings(self.prop_map_0)
        if not self._single_mode:
            self._apply_camera_settings(self.prop_map_1)

    def _start_streams(self):
        self._sink_0 = ic4.QueueSink(self._listener_0)
        self.grabber_0.stream_setup(self._sink_0)
        if not self._single_mode:
            self._sink_1 = ic4.QueueSink(self._listener_1)
            self.grabber_1.stream_setup(self._sink_1)
        else:
            self._sink_1 = None

    # ── UI ────────────────────────────────────────────────────────────────────
    def _create_ui(self):
        if self._single_mode:
            self.setWindowTitle(
                f"IC4 Single Camera (Dual Display)  |  "
                f"{self._devices[0].model_name}"
            )
        else:
            self.setWindowTitle(
                f"IC4 Dual Camera  |  "
                f"Cam0: {self._devices[0].model_name}  |  "
                f"Cam1: {self._devices[1].model_name}"
            )

        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        video_row = QtWidgets.QHBoxLayout()

        if self._single_mode:
            titles = [
                f"View 1 — {self._devices[0].model_name}",
                f"View 2 — {self._devices[0].model_name}",
            ]
        else:
            titles = [
                f"Camera 0 — {self._devices[0].model_name}",
                f"Camera 1 — {self._devices[1].model_name}",
            ]

        for attr, title in zip(("win1", "win2"), titles):
            cam_box = QVBoxLayout()
            cam_label_title = QLabel(title)
            cam_label_title.setAlignment(QtCore.Qt.AlignCenter)
            cam_label_title.setStyleSheet("font-weight: bold;")
            lbl = self._make_video_label()
            setattr(self, attr, lbl)
            cam_box.addWidget(cam_label_title)
            cam_box.addWidget(lbl)
            video_row.addLayout(cam_box)

        # 控制面板
        tabs = QTabWidget()
        tabs.addTab(
            GuidedPanel(self.prop_map_0, "Camera 0"),
            "Camera 0 Controls"
        )
        if not self._single_mode:
            tabs.addTab(
                GuidedPanel(self.prop_map_1, "Camera 1"),
                "Camera 1 Controls"
            )

        btn_row = QHBoxLayout()
        self._btn_record = QPushButton("⏺  Record")
        self._btn_stop = QPushButton("⏹  Stop")
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setAlignment(QtCore.Qt.AlignCenter)

        self._btn_record.clicked.connect(self._record_video)
        self._btn_stop.clicked.connect(self._stop_recording)
        btn_row.addWidget(self._btn_record)
        btn_row.addWidget(self._btn_stop)
        btn_row.addWidget(self._status_lbl)

        root_layout.addLayout(video_row, stretch=3)
        root_layout.addWidget(tabs, stretch=3)
        root_layout.addLayout(btn_row, stretch=0)

    @staticmethod
    def _make_video_label():
        lbl = QLabel("No signal")
        lbl.setMinimumSize(640, 480)
        lbl.setAlignment(QtCore.Qt.AlignCenter)
        lbl.setScaledContents(True)
        return lbl

    # ── Frame display ─────────────────────────────────────────────────────────
    def _update_label_0(self, frame):
        now = time.time()
        if now - self._last_display_0 < self._DISPLAY_INTERVAL:
            return
        self._last_display_0 = now
        self._render_frame(self.win1, frame)

    def _update_label_1(self, frame):
        now = time.time()
        if now - self._last_display_1 < self._DISPLAY_INTERVAL:
            return
        self._last_display_1 = now
        self._render_frame(self.win2, frame)

    def _render_frame(self, label, frame):
        if not self._ocv:
            return
        raw = frame[:, :, 0] if frame.ndim == 3 else frame
        bgr = cv2.cvtColor(raw, cv2.COLOR_BayerRG2BGR)
        h, w, ch = bgr.shape
        qimg = QtGui.QImage(
            bgr.data, w, h, ch * w, QtGui.QImage.Format_RGB888
        )
        label.setPixmap(QtGui.QPixmap.fromImage(qimg))

    # ── Recording ─────────────────────────────────────────────────────────────
    def _record_video(self):
        if not self._listener_0.first_frame_arrived:
            self._status_lbl.setText("⚠ Stream not ready yet.")
            return
        if self._recording:
            self._stop_recording()

        self._frame_rate = float(
            self.prop_map_0[ic4.PropId.ACQUISITION_FRAME_RATE].value
        )

        name_0 = f"video_{self._inc}_cam0.mp4"
        self._writer_0.begin_file(
            name_0, self._sink_0.output_image_type, self._frame_rate
        )
        self._listener_0.enable_recording(True)
        recorded_names = [name_0]

        if not self._single_mode:
            name_1 = f"video_{self._inc}_cam1.mp4"
            self._writer_1.begin_file(
                name_1, self._sink_1.output_image_type, self._frame_rate
            )
            self._listener_1.enable_recording(True)
            recorded_names.append(name_1)

        self._inc += 1
        self._recording = True

        msg = "Recording → " + ", ".join(recorded_names)
        self._status_lbl.setText(f"⏺ {msg}")
        print(msg)

    def _stop_recording(self):
        if not self._recording:
            return
        self._listener_0.enable_recording(False)
        self._writer_0.finish_file()

        if not self._single_mode:
            self._listener_1.enable_recording(False)
            self._writer_1.finish_file()

        self._recording = False

        if self._single_mode:
            msg = f"Saved. Cam0: {self._listener_0.frames_written} frames."
        else:
            msg = (
                f"Saved. "
                f"Cam0: {self._listener_0.frames_written} frames, "
                f"Cam1: {self._listener_1.frames_written} frames."
            )
        self._status_lbl.setText(f"⏹ {msg}")
        print(msg)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    def closeEvent(self, ev):
        self._ocv = False
        if self._recording:
            self._stop_recording()

        grabbers = [self.grabber_0]
        if not self._single_mode:
            grabbers.append(self.grabber_1)
        for g in grabbers:
            if g is not None and g.is_streaming:
                g.stream_stop()
        ev.accept()


# ─────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────
STYLE_SHEET = """
QMainWindow  { background-color: #2E3440; }
QDialog      { background-color: #2E3440; }
QWidget      { background-color: #2E3440; }
QLabel       { color: #ECEFF4; font-size: 13px; }
QPushButton  { background-color: #5E81AC; color: white;
               border-radius: 6px; padding: 5px 15px;
               font-weight: bold; }
QPushButton:hover    { background-color: #81A1C1; }
QPushButton:disabled { background-color: #4C566A; color: #7a8290; }
QCheckBox    { color: #ECEFF4; padding: 4px; }
QComboBox {
    background-color: #3B4252; color: #ECEFF4;
    border: 1px solid #88C0D0; border-radius: 4px;
    padding: 4px 6px;
}
QComboBox QAbstractItemView {
    background-color: #3B4252; color: #ECEFF4;
    selection-background-color: #5E81AC;
}
QDoubleSpinBox {
    background-color : #3B4252;
    color            : #ECEFF4;
    border           : 1px solid #88C0D0;
    border-radius    : 4px;
    padding          : 2px 4px;
}
QSlider::groove:horizontal {
    height: 8px; background: #4C566A; border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #88C0D0; width: 18px;
    border-radius: 9px; margin: -5px 0;
}
QSlider::handle:horizontal:disabled { background: #4C566A; }
QTabBar::tab {
    background: #4C566A; color: #D8DEE9;
    padding: 8px 15px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QTabBar::tab:selected { background: #5E81AC; }
QGroupBox {
    border: 2px solid #88C0D0; border-radius: 8px;
    margin-top: 16px; padding-top: 8px;
    color: #ECEFF4; font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
}
"""


def main():
    ic4.Library.init(
        api_log_level=ic4.LogLevel.INFO,
        log_targets=ic4.LogTarget.STDERR,
    )
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("ic4-dual-cam")
        app.setStyle("fusion")
        app.setStyleSheet(STYLE_SHEET)

        devices = ic4.DeviceEnum.devices()
        if len(devices) < 1:
            QMessageBox.critical(
                None, "No Camera",
                "No camera detected. Please connect at least one camera."
            )
            return

        dlg = CameraSelectionDialog(devices)
        if dlg.exec() != QDialog.Accepted:
            print("User cancelled camera selection.")
            return

        indices = dlg.selected_indices
        selected = [devices[i] for i in indices]

        if len(selected) == 1:
            print(f"Selected SINGLE camera: [{indices[0]}]")
        else:
            print(f"Selected cameras: [{indices[0]}] & [{indices[1]}]")

        w = MainWindow(selected)
        w.show()
        app.exec()
    finally:
        ic4.Library.exit()


if __name__ == "__main__":
    main()
