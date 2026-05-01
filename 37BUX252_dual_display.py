import sys
import threading
import time

import cv2
import imagingcontrol4 as ic4
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import (
    QApplication, QDoubleSpinBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QMainWindow, QPushButton, QSlider, QTabWidget,
    QVBoxLayout, QWidget
)
from PySide6.QtGui import QCloseEvent


# ─────────────────────────────────────────
#  SliderWithValue：Slider + 數值輸入框 組合元件
# ─────────────────────────────────────────
class SliderWithValue(QWidget):
    """
    水平 Slider + QDoubleSpinBox 組合。
    兩者雙向同步，外部可透過 valueChanged signal 監聽變化。
    
    內部以 float 為單位，Slider 會以 step=1 對應 float 的精度。
    """
    valueChanged = QtCore.Signal(float)

    def __init__(
        self,
        minimum: float,
        maximum: float,
        value: float,
        decimals: int = 2,
        step: float = 1.0,
        parent=None,
    ):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._step    = step
        self._decimals = decimals
        self._updating = False          # 防止迴圈更新

        self._build_ui(value)

    def _build_ui(self, initial_value: float):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # ── Slider ────────────────────────────────────────────────────────────
        self._slider = QSlider(QtCore.Qt.Horizontal)
        self._slider.setMinimum(0)
        self._slider.setMaximum(self._float_to_tick(self._maximum))
        self._slider.setValue(self._float_to_tick(initial_value))
        self._slider.setMinimumWidth(160)

        # ── SpinBox ───────────────────────────────────────────────────────────
        self._spinbox = QDoubleSpinBox()
        self._spinbox.setDecimals(self._decimals)
        self._spinbox.setMinimum(self._minimum)
        self._spinbox.setMaximum(self._maximum)
        self._spinbox.setSingleStep(self._step)
        self._spinbox.setValue(initial_value)
        self._spinbox.setFixedWidth(100)

        layout.addWidget(self._slider,  stretch=1)
        layout.addWidget(self._spinbox, stretch=0)

        # ── 雙向連接 ──────────────────────────────────────────────────────────
        self._slider.valueChanged.connect(self._on_slider_changed)
        self._spinbox.valueChanged.connect(self._on_spinbox_changed)

    # ── tick ↔ float 轉換 ────────────────────────────────────────────────────
    def _float_to_tick(self, val: float) -> int:
        return int(round((val - self._minimum) / self._step))

    def _tick_to_float(self, tick: int) -> float:
        return round(self._minimum + tick * self._step, self._decimals)

    # ── 事件處理（防止互相觸發）─────────────────────────────────────────────
    def _on_slider_changed(self, tick: int):
        if self._updating:
            return
        self._updating = True
        fval = self._tick_to_float(tick)
        self._spinbox.setValue(fval)
        self.valueChanged.emit(fval)
        self._updating = False

    def _on_spinbox_changed(self, fval: float):
        if self._updating:
            return
        self._updating = True
        self._slider.setValue(self._float_to_tick(fval))
        self.valueChanged.emit(fval)
        self._updating = False

    # ── 公開介面 ─────────────────────────────────────────────────────────────
    def value(self) -> float:
        return self._spinbox.value()

    def setValue(self, val: float):
        self._spinbox.setValue(val)     # spinbox → slider 會透過 signal 同步


# ─────────────────────────────────────────
#  Advanced Control Panel
# ─────────────────────────────────────────
class AdvancedPanel(QWidget):
    def __init__(self, property_map: ic4.PropertyMap, cam_name: str = ""):
        super().__init__()
        self.property_map = property_map
        self.cam_name = cam_name
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout()
        layout.setLabelAlignment(QtCore.Qt.AlignRight)

        # ── Exposure ──────────────────────────────────────────────────────────
        exp_prop  = self.property_map[ic4.PropId.EXPOSURE_TIME]
        exp_min   = float(exp_prop.minimum)
        exp_max   = float(exp_prop.maximum)
        exp_val   = float(exp_prop.value)

        self.exposure_widget = SliderWithValue(
            minimum  = exp_min,
            maximum  = exp_max,
            value    = exp_val,
            decimals = 1,
            step     = 1.0,      # µs 精度
        )
        self.exposure_widget.valueChanged.connect(self._change_exposure)
        layout.addRow("Exposure Time (µs)", self.exposure_widget)

        # ── Gain ──────────────────────────────────────────────────────────────
        gain_prop = self.property_map[ic4.PropId.GAIN]
        gain_min  = float(gain_prop.minimum)
        gain_max  = float(gain_prop.maximum)
        gain_val  = float(gain_prop.value)

        self.gain_widget = SliderWithValue(
            minimum  = gain_min,
            maximum  = gain_max,
            value    = gain_val,
            decimals = 2,
            step     = 0.1,      # dB 精度
        )
        self.gain_widget.valueChanged.connect(self._change_gain)
        layout.addRow("Gain (dB)", self.gain_widget)

        # ── Frame Rate (唯讀顯示) ─────────────────────────────────────────────
        try:
            fps_prop  = self.property_map[ic4.PropId.ACQUISITION_FRAME_RATE]
            fps_min   = float(fps_prop.minimum)
            fps_max   = float(fps_prop.maximum)
            fps_val   = float(fps_prop.value)
            self.fps_widget = SliderWithValue(
                minimum  = fps_min,
                maximum  = fps_max,
                value    = fps_val,
                decimals = 1,
                step     = 1.0,
            )
            self.fps_widget.valueChanged.connect(self._change_fps)
            layout.addRow("Frame Rate (fps)", self.fps_widget)
        except Exception:
            pass    # 若相機不支援則略過

        self.setLayout(layout)

    # ── Callbacks ─────────────────────────────────────────────────────────────
    def _change_exposure(self, val: float):
        ok = self.property_map.try_set_value(ic4.PropId.EXPOSURE_TIME, val)
        if not ok:
            print(f"[{self.cam_name}] Failed to set Exposure = {val}")

    def _change_gain(self, val: float):
        ok = self.property_map.try_set_value(ic4.PropId.GAIN, val)
        if not ok:
            print(f"[{self.cam_name}] Failed to set Gain = {val}")

    def _change_fps(self, val: float):
        ok = self.property_map.try_set_value(ic4.PropId.ACQUISITION_FRAME_RATE, val)
        if not ok:
            print(f"[{self.cam_name}] Failed to set FPS = {val}")


# ─────────────────────────────────────────
#  Queue-Sink Listener
# ─────────────────────────────────────────
class CameraListener(ic4.QueueSinkListener):
    """Thread-safe listener：轉發畫面 + 錄製 MP4。"""

    def __init__(self, video_writer: ic4.VideoWriter, frame_callback):
        super().__init__()
        self._video_writer   = video_writer
        self._frame_callback = frame_callback
        self._lock           = threading.Lock()
        self._do_write       = False
        self._counter        = 0
        self.first_frame_arrived = False

    # ── ic4 callbacks ──────────────────────────────────────────────────────────
    def sink_connected(
        self,
        sink: ic4.QueueSink,
        image_type: ic4.ImageType,
        min_buffers_required: int,
    ) -> bool:
        self.image_type = image_type
        return True

    def frames_queued(self, sink: ic4.QueueSink):
        buffer = sink.pop_output_buffer()
        img    = buffer.numpy_wrap().copy()   # 在 buffer 回收前複製

        if not self.first_frame_arrived:
            self.first_frame_arrived = True
            print("First frame arrived")

        if self._frame_callback is not None:
            self._frame_callback(img)

        with self._lock:
            if self._do_write:
                self._video_writer.add_frame(buffer)
                self._counter += 1

    # ── Public API ─────────────────────────────────────────────────────────────
    def enable_recording(self, enable: bool):
        with self._lock:
            if enable:
                self._counter = 0
            self._do_write = enable

    @property
    def frames_written(self) -> int:
        with self._lock:
            return self._counter


# ─────────────────────────────────────────
#  Main Window
# ─────────────────────────────────────────
class MainWindow(QMainWindow):
    new_frame_0 = QtCore.Signal(object)
    new_frame_1 = QtCore.Signal(object)

    _DISPLAY_INTERVAL = 1 / 24     # 顯示上限 24 fps

    def __init__(self):
        super().__init__()
        self._inc            = 0
        self._ocv            = True
        self._recording      = False
        self._last_display_0 = 0.0
        self._last_display_1 = 0.0

        self._init_grabbers()
        self._init_listeners()
        self._configure_cameras()
        self._start_streams()
        self._create_ui()

        print("Initialisation complete.")

    # ── Camera setup ──────────────────────────────────────────────────────────
    def _init_grabbers(self):
        devices = ic4.DeviceEnum.devices()
        if len(devices) < 2:
            raise RuntimeError(f"Need 2 cameras, found {len(devices)}.")

        self.grabber_0 = ic4.Grabber(devices[0])
        self.grabber_1 = ic4.Grabber(devices[1])
        self.prop_map_0: ic4.PropertyMap = self.grabber_0.device_property_map
        self.prop_map_1: ic4.PropertyMap = self.grabber_1.device_property_map

        self._frame_rate = float(
            self.prop_map_0[ic4.PropId.ACQUISITION_FRAME_RATE].value
        )
        self._writer_0 = ic4.VideoWriter(ic4.VideoWriterType.MP4_H264)
        self._writer_1 = ic4.VideoWriter(ic4.VideoWriterType.MP4_H264)

    def _init_listeners(self):
        self.new_frame_0.connect(self._update_label_0)
        self.new_frame_1.connect(self._update_label_1)

        self._listener_0 = CameraListener(
            self._writer_0,
            frame_callback=lambda img: self.new_frame_0.emit(img),
        )
        self._listener_1 = CameraListener(
            self._writer_1,
            frame_callback=lambda img: self.new_frame_1.emit(img),
        )

    def _apply_camera_settings(self, prop_map: ic4.PropertyMap):
        prop_map.try_set_value(ic4.PropId.WIDTH,                   1280)
        prop_map.try_set_value(ic4.PropId.HEIGHT,                   720)
        prop_map.try_set_value(ic4.PropId.ACQUISITION_FRAME_RATE,  240)
        prop_map.try_set_value(ic4.PropId.EXPOSURE_TIME,          60.0)
        prop_map.try_set_value(ic4.PropId.GAIN,                   60.0)

    def _configure_cameras(self):
        self._apply_camera_settings(self.prop_map_0)
        self._apply_camera_settings(self.prop_map_1)

    def _start_streams(self):
        self._sink_0 = ic4.QueueSink(self._listener_0)
        self._sink_1 = ic4.QueueSink(self._listener_1)
        self.grabber_0.stream_setup(self._sink_0)
        self.grabber_1.stream_setup(self._sink_1)

    # ── UI ────────────────────────────────────────────────────────────────────
    def _create_ui(self):
        self.setWindowTitle("IC4 Dual Camera")
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)

        # ── 影像顯示區 ────────────────────────────────────────────────────────
        video_row = QtWidgets.QHBoxLayout()

        # 每個相機區包含標題 + 影像
        for i, (attr, title) in enumerate(
            [("win1", "Camera 0"), ("win2", "Camera 1")]
        ):
            cam_box = QVBoxLayout()
            cam_label_title = QLabel(title)
            cam_label_title.setAlignment(QtCore.Qt.AlignCenter)
            lbl = self._make_video_label()
            setattr(self, attr, lbl)
            cam_box.addWidget(cam_label_title)
            cam_box.addWidget(lbl)
            video_row.addLayout(cam_box)

        # ── 控制面板 Tabs ─────────────────────────────────────────────────────
        tabs = QTabWidget()
        tabs.addTab(
            AdvancedPanel(self.prop_map_0, "Camera 0"), "Camera 0 Controls"
        )
        tabs.addTab(
            AdvancedPanel(self.prop_map_1, "Camera 1"), "Camera 1 Controls"
        )

        # ── 錄影按鈕列 ────────────────────────────────────────────────────────
        btn_row        = QHBoxLayout()
        self._btn_record = QPushButton("⏺  Record")
        self._btn_stop   = QPushButton("⏹  Stop")
        self._status_lbl = QLabel("Ready")
        self._status_lbl.setAlignment(QtCore.Qt.AlignCenter)

        self._btn_record.clicked.connect(self._record_video)
        self._btn_stop.clicked.connect(self._stop_recording)
        btn_row.addWidget(self._btn_record)
        btn_row.addWidget(self._btn_stop)
        btn_row.addWidget(self._status_lbl)

        root_layout.addLayout(video_row,  stretch=3)
        root_layout.addWidget(tabs,       stretch=2)
        root_layout.addLayout(btn_row,    stretch=0)

    @staticmethod
    def _make_video_label() -> QLabel:
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

    def _render_frame(self, label: QLabel, frame):
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

        name_0 = f"video_{self._inc}_cam0.mp4"
        name_1 = f"video_{self._inc}_cam1.mp4"
        self._inc += 1

        # 錄影開始前重新讀取目前 frame rate（使用者可能已調整）
        self._frame_rate = float(
            self.prop_map_0[ic4.PropId.ACQUISITION_FRAME_RATE].value
        )

        self._writer_0.begin_file(
            name_0, self._sink_0.output_image_type, self._frame_rate
        )
        self._writer_1.begin_file(
            name_1, self._sink_1.output_image_type, self._frame_rate
        )
        self._listener_0.enable_recording(True)
        self._listener_1.enable_recording(True)
        self._recording = True

        msg = f"Recording → {name_0}, {name_1}"
        self._status_lbl.setText(f"⏺ {msg}")
        print(msg)

    def _stop_recording(self):
        if not self._recording:
            return
        self._listener_0.enable_recording(False)
        self._listener_1.enable_recording(False)
        self._writer_0.finish_file()
        self._writer_1.finish_file()
        self._recording = False

        msg = (
            f"Saved. "
            f"Cam0: {self._listener_0.frames_written} frames, "
            f"Cam1: {self._listener_1.frames_written} frames."
        )
        self._status_lbl.setText(f"⏹ {msg}")
        print(msg)

    # ── Shutdown ──────────────────────────────────────────────────────────────
    def closeEvent(self, ev: QCloseEvent):
        self._ocv = False
        if self._recording:
            self._stop_recording()
        for grabber in (self.grabber_0, self.grabber_1):
            if grabber.is_streaming:
                grabber.stream_stop()
        ev.accept()


# ─────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────
if __name__ == "__main__":
    ic4.Library.init(
        api_log_level=ic4.LogLevel.INFO,
        log_targets=ic4.LogTarget.STDERR,
    )
    try:
        app = QApplication(sys.argv)
        app.setApplicationName("ic4-dual-cam")
        app.setStyle("fusion")
        app.setStyleSheet("""
            QMainWindow  { background-color: #2E3440; }
            QWidget      { background-color: #2E3440; }
            QLabel       { color: #ECEFF4; font-size: 13px; }
            QPushButton  { background-color: #5E81AC; color: white;
                           border-radius: 6px; padding: 5px 15px;
                           font-weight: bold; }
            QPushButton:hover { background-color: #81A1C1; }
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
            QTabBar::tab {
                background: #4C566A; color: #D8DEE9;
                padding: 8px 15px;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
            }
            QTabBar::tab:selected { background: #5E81AC; }
            QGroupBox {
                border: 2px solid #88C0D0; border-radius: 8px;
                margin-top: 20px; color: #ECEFF4; font-weight: bold;
            }
        """)
        w = MainWindow()
        w.show()
        app.exec()
    finally:
        ic4.Library.exit()
